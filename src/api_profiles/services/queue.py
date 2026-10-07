from math import ceil
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import Group
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.timezone import localdate, now

from api_auth.services.mail import send_provider_decision
from api_catalogs.models import Reason, ReasonContext
from api_catalogs.seeder import (
    CHANGES_REQUESTED_REASON,
    CONTEXT_DOCUMENT_REJECTION,
    CONTEXT_PROVIDER_REJECTION,
    SERVICE_GUIDE,
)
from api_core.schemas.pagination import Paginated
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from api_moderation.enums import (
    API_STATUS,
    PROCEDURE_API_NAMES,
    VerificationProcedures,
    VerificationStates,
)
from api_moderation.models import (
    VerificationRequest,
    VerificationResolution,
    VerificationStatus,
)
from api_moderation.schemas import PersonRef, RejectionReasonGet
from api_moderation.services import person
from api_profiles.enums import (
    PROVIDER_API_STATUS,
    CredentialStates,
    ProviderStates,
    Verdicts,
)
from api_profiles.models import Credential, ProviderProfile
from api_profiles.schemas.queue import (
    DocumentCountsGet,
    ProviderDetailGet,
    ProviderHistoryItem,
    ProviderQueueQuery,
    ProviderReasonsGet,
    ProviderRequestGet,
    ProviderRequestInlineGet,
    RequestCredentialGet,
)
from api_profiles.services.documents import (
    accepted_for_decision,
    credential_state,
    in_force_by_type,
    missing_in_force,
    provider_state,
    required_of,
    services_of,
)
from api_profiles.services.payloads import (
    Expediente,
    city_payload,
    credential_payload,
    expediente_of,
    file_payload,
    language_payloads,
    option,
    reason_payload,
    resolution_of,
)
from api_roles.models import RoleAssignment
from api_roles.services import grant_role_sync

if TYPE_CHECKING:
    from datetime import date
    from typing import Final
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_profiles.schemas.queue import DocumentReviewPost

########################################################################################

OPEN_STATES: Final[tuple[str, ...]] = (
    VerificationStates.SUBMITTED,
    VerificationStates.IN_REVIEW,
)

STATE_BY_API_NAME: Final[dict[str, str]] = {
    name: code for code, name in API_STATUS.items()
}

PROCEDURE_BY_API_NAME: Final[dict[str, str]] = {
    name: code for code, name in PROCEDURE_API_NAMES.items()
}

# - el grupo (rol público) que da cada servicio al aprobar
ROLE_BY_SERVICE: Final[dict[str, str]] = {
    SERVICE_GUIDE: "Guía",
    "traductor": "Traductor",
}

RELATED: Final[tuple[str, ...]] = (
    "provider__city",
    "provider__status",
    "provider__user",
    "status",
    "taken_by",
)

########################################################################################
# Lectura


def provider_requests() -> QuerySet:
    return VerificationRequest.objects.select_related(*RELATED).filter(
        provider__isnull=False
    )


def fetch_request(request_id: UUID, *, lock: bool = False) -> VerificationRequest:
    requests: Any = provider_requests()

    if lock:
        requests = requests.select_for_update(of=("self",))

    found: VerificationRequest | None = requests.filter(pk=request_id).first()

    if found is None:
        raise NotFoundError(detail="No encontramos esa solicitud.")

    return found


def is_renewal(request: VerificationRequest) -> bool:
    found: Any = request

    return found.procedure == VerificationProcedures.RENEWAL


# Lo que se revisa en el expediente: en la postulación, lo vigente de cada tipo que se
# pide; en una renovación, lo que se subió en ella.
def considered(
    request: VerificationRequest, expediente: Expediente
) -> list[Credential]:
    if is_renewal(request):
        return [item for item, in_this in expediente.documents if in_this]

    required: set[str] = {str(item.code) for item in expediente.required}

    return [
        item
        for item, _ in expediente.documents
        if str(item.credential_type.code) in required  # ty: ignore[unresolved-attribute]
    ]


def counts_of(documents: list[Credential]) -> DocumentCountsGet:
    verdicts: list[str] = [str(item.verdict) for item in documents]

    return DocumentCountsGet(
        accepted=verdicts.count(Verdicts.ACCEPTED),
        pending=verdicts.count(""),
        rejected=verdicts.count(Verdicts.REJECTED),
        total=len(verdicts),
    )


def ready_to_decide(expediente: Expediente, today: date) -> bool:
    latest: dict[str, Credential] = {
        str(item.credential_type.code): item  # ty: ignore[unresolved-attribute]
        for item, _ in expediente.documents
    }

    return accepted_for_decision(expediente.required, latest, today)


def stage_of(
    request: VerificationRequest,
    expediente: Expediente,
    today: date,
) -> str | None:
    found: Any = request

    if found.resolved_at is not None:
        return None

    if not is_renewal(request) and ready_to_decide(expediente, today):
        return "decision"

    return "documents"


def applicant_of(request: VerificationRequest) -> PersonRef:
    found: Any = request
    applicant: PersonRef | None = person(found.provider.user)

    if applicant is None:
        raise ValueError("Un perfil de prestador siempre tiene cuenta.")

    return applicant


def inline_payload(
    request: VerificationRequest,
    expediente: Expediente,
    today: date,
) -> ProviderRequestInlineGet:
    found: Any = request

    return ProviderRequestInlineGet(
        applicant=applicant_of(request),
        city=city_payload(found.provider.city),
        counts=counts_of(considered(request, expediente)),
        id=found.pk,
        procedure=PROCEDURE_API_NAMES[str(found.procedure)],  # ty: ignore[invalid-argument-type]
        resolved_at=found.resolved_at,
        services=services_of(found.provider),
        stage=stage_of(request, expediente, today),  # ty: ignore[invalid-argument-type]
        status=API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        submitted_at=found.submitted_at,
        taken_by=person(found.taken_by),
    )


def queue_sync(query: ProviderQueueQuery) -> Paginated[ProviderRequestInlineGet]:
    requests: Any = provider_requests()

    if query.status == "open":
        requests = requests.filter(status__code__in=OPEN_STATES)
    elif query.status != "all":
        requests = requests.filter(status__code=STATE_BY_API_NAME[query.status])

    if query.service is not None:
        requests = requests.filter(
            provider__services__service__code=query.service
        ).distinct()

    if query.procedure is not None:
        requests = requests.filter(procedure=PROCEDURE_BY_API_NAME[query.procedure])

    # la bandeja se atiende por orden de llegada; lo cerrado, lo más reciente primero
    ordering = (
        "submitted_at"
        if query.status in {"open", "submitted", "in_review"}
        else "-submitted_at"
    )
    ordered = requests.order_by(ordering, "id")

    total: int = ordered.count()
    start: int = (query.page - 1) * query.page_size
    pages: int = max(1, ceil(total / query.page_size))
    today: date = localdate()

    return Paginated[ProviderRequestInlineGet](
        current=query.page,
        elements=total,
        next=query.page < pages,
        pages=pages,
        previous=query.page > 1,
        results=[
            inline_payload(item, expediente_of(item, today), today)
            for item in ordered[start : start + query.page_size]
        ],
    )


def history_of(request: VerificationRequest) -> list[ProviderHistoryItem]:
    found: Any = request
    previous: Any = (
        VerificationRequest.objects
        .select_related("status")
        .filter(provider=found.provider)
        .exclude(pk=request.pk)
        .order_by("-submitted_at")
    )

    items: list[ProviderHistoryItem] = []

    for item in previous:
        resolution: Any = (
            VerificationResolution.objects
            .select_related("reason")
            .filter(request=item)
            .first()
        )

        items.append(
            ProviderHistoryItem(
                id=item.pk,
                note="" if resolution is None else str(resolution.note),
                procedure=PROCEDURE_API_NAMES[str(item.procedure)],  # ty: ignore[invalid-argument-type]
                reason=None
                if resolution is None
                else reason_payload(resolution.reason),
                resolved_at=item.resolved_at,
                status=API_STATUS[str(item.status.code)],  # ty: ignore[invalid-argument-type]
                submitted_at=item.submitted_at,
            )
        )

    return items


def detail_sync(request_id: UUID) -> ProviderRequestGet:
    request: Any = fetch_request(request_id)
    profile: Any = request.provider
    today: date = localdate()
    expediente: Expediente = expediente_of(request, today)
    required: set[str] = {str(item.code) for item in expediente.required}

    return ProviderRequestGet(
        **dict(inline_payload(request, expediente, today)),
        documents=[
            RequestCredentialGet(
                **dict(credential_payload(item)),
                in_this_request=in_this,
                required=str(item.credential_type.code) in required,  # ty: ignore[unresolved-attribute]
            )
            for item, in_this in expediente.documents
        ],
        history=history_of(request),
        missing=[option(item) for item in expediente.missing],
        profile=ProviderDetailGet(
            approved_at=profile.approved_at,
            carries_tourists=bool(profile.carries_tourists),
            created_at=profile.created_at,
            id=profile.pk,
            languages=language_payloads(profile),
            phone=str(profile.phone),
            photo=file_payload(str(profile.photo_key)) if profile.photo_key else None,
            presentation=str(profile.presentation),
            status=PROVIDER_API_STATUS[str(profile.status.code)],  # ty: ignore[invalid-argument-type]
        ),
        resolution=resolution_of(request),
    )


def reasons_in(context: str) -> list[RejectionReasonGet]:
    offered: Any = (
        ReasonContext.objects
        .select_related("reason")
        .filter(context=context, reason__active=True)
        .order_by("order")
    )

    return [
        RejectionReasonGet(
            code=str(item.reason.code),
            label=str(item.reason.label),
            requires_text=bool(item.reason.requires_text),
        )
        for item in offered
    ]


def reasons_sync() -> ProviderReasonsGet:
    return ProviderReasonsGet(
        decision=reasons_in(CONTEXT_PROVIDER_REJECTION),
        document=reasons_in(CONTEXT_DOCUMENT_REJECTION),
    )


########################################################################################
# Atender el expediente


def state(code: VerificationStates) -> VerificationStatus:
    return VerificationStatus.objects.get(code=code)


def ensure_open(request: VerificationRequest) -> None:
    found: Any = request

    if found.resolved_at is not None:
        raise ConflictError(detail="Esta solicitud ya se resolvió.")


def ensure_application(request: VerificationRequest) -> None:
    if is_renewal(request):
        raise ConflictError(
            detail="Una renovación se resuelve al revisar sus documentos."
        )


def ensure_not_taken_by_someone_else(
    request: VerificationRequest,
    actor: ApiUser,
) -> None:
    holder: Any = request.taken_by

    if holder is not None and holder.pk != actor.pk:
        raise ConflictError(
            detail=f"{holder.display_name} ya tiene esta solicitud en revisión.",
        )


def offered_reason(code: str, note: str, context: str) -> Reason:
    reason: Reason | None = Reason.objects.filter(
        Q(contexts__context=context),
        active=True,
        code=code,
    ).first()

    if reason is None:
        raise BadRequestError(
            field_errors={"reason": "Ese motivo no se ofrece aquí."},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    if reason.requires_text and not note.strip():
        raise BadRequestError(
            field_errors={
                "note": "Con ese motivo hay que explicarle a la persona qué pasó."
            },
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    return reason


def set_documents(documents: list[Credential], *, old: str, new: str) -> None:
    Credential.objects.filter(
        pk__in=[item.pk for item in documents],
        status__code=old,
    ).update(status=credential_state(new))  # ty: ignore[invalid-argument-type]


def hold(request: VerificationRequest, actor: ApiUser) -> None:
    # queda en revisión, a su nombre, y sus documentos también
    VerificationRequest.objects.filter(pk=request.pk).update(
        status=state(VerificationStates.IN_REVIEW),
        taken_by=actor,
    )
    set_documents(
        considered(request, expediente_of(request, localdate())),
        new=CredentialStates.IN_REVIEW,
        old=CredentialStates.UPLOADED,
    )


def take_sync(request_id: UUID, actor: ApiUser) -> ProviderRequestGet:
    with atomic():
        request: VerificationRequest = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_not_taken_by_someone_else(request, actor)
        hold(request, actor)

    return detail_sync(request_id)


# Devolverla a la cola: la suelta quien la tiene, o quien decide.
def release_sync(
    request_id: UUID,
    actor: ApiUser,
    *,
    can_decide: bool,
) -> ProviderRequestGet:
    with atomic():
        request: VerificationRequest = fetch_request(request_id, lock=True)
        holder: Any = request.taken_by

        ensure_open(request)

        if holder is None:
            raise ConflictError(detail="Esta solicitud no está en revisión.")

        if holder.pk != actor.pk and not can_decide:
            raise ForbiddenError(
                detail="Solo quien la tiene en revisión puede devolverla."
            )

        VerificationRequest.objects.filter(pk=request.pk).update(
            status=state(VerificationStates.SUBMITTED),
            taken_by=None,
        )
        set_documents(
            considered(request, expediente_of(request, localdate())),
            new=CredentialStates.UPLOADED,
            old=CredentialStates.IN_REVIEW,
        )

    return detail_sync(request_id)


# Cierra el expediente: la resolución es de solo inserción. Lo rechazado por quien
# revisó queda rechazado; lo demás vuelve a «cargada» con su veredicto, para pasar tal
# cual al expediente siguiente.
def close(  # ruff: ignore[too-many-arguments]
    request: VerificationRequest,
    actor: ApiUser,
    *,
    approved: bool,
    note: str,
    reason: Reason | None,
    documents: list[Credential],
) -> None:
    rejected: list[Credential] = [
        item for item in documents if item.verdict == Verdicts.REJECTED
    ]
    Credential.objects.filter(pk__in=[item.pk for item in rejected]).update(
        status=credential_state(CredentialStates.REJECTED)
    )
    set_documents(
        documents,
        new=CredentialStates.UPLOADED,
        old=CredentialStates.IN_REVIEW,
    )

    VerificationResolution.objects.create(
        approved=approved,
        note=note.strip(),
        reason=reason,
        request=request,
        resolved_by=actor,
    )
    VerificationRequest.objects.filter(pk=request.pk).update(
        resolved_at=now(),
        status=state(
            VerificationStates.APPROVED if approved else VerificationStates.REJECTED
        ),
        taken_by=actor,
    )


def put_in_force(documents: list[Credential]) -> None:
    # el aceptado entra en vigor y deja reemplazado al anterior del mismo tipo
    approved = credential_state(CredentialStates.APPROVED)
    replaced = credential_state(CredentialStates.REPLACED)

    for item in documents:
        found: Any = item
        Credential.objects.filter(
            credential_type=found.credential_type,
            provider=found.provider,
            status=approved,
        ).exclude(pk=item.pk).update(status=replaced)
        Credential.objects.filter(pk=item.pk).update(status=approved)


def grant_provider_roles(profile: ProviderProfile, actor: ApiUser) -> None:
    found: Any = profile

    for code in services_of(profile):
        group: Group = Group.objects.get(name=ROLE_BY_SERVICE[code])

        if not RoleAssignment.objects.filter(
            revoked_at__isnull=True,
            role=group,
            user=found.user,
        ).exists():
            grant_role_sync(
                granted_by=actor,
                role=group,
                scope_object=None,
                user=found.user,
            )


# Una renovación no pasa por la decisión: cuando su último documento queda revisado,
# se resuelve sola. Lo aceptado entra en vigor; si estaba suspendido y ya no le falta
# nada, vuelve a estar activo.
def settle_renewal(request: VerificationRequest, actor: ApiUser) -> None:
    found: Any = request
    uploaded: list[Credential] = list(
        Credential.objects.select_related("credential_type").filter(request=request)
    )

    if any(not item.verdict for item in uploaded):
        return

    accepted: list[Credential] = [
        item for item in uploaded if item.verdict == Verdicts.ACCEPTED
    ]
    approved: bool = len(accepted) == len(uploaded)

    put_in_force(accepted)
    close(
        request,
        actor,
        approved=approved,
        documents=uploaded,
        note="",
        reason=None if approved else Reason.objects.get(code=CHANGES_REQUESTED_REASON),
    )

    profile: Any = ProviderProfile.objects.select_related("status").get(
        pk=found.provider_id
    )

    if str(profile.status.code) == ProviderStates.SUSPENDED and not missing_in_force(
        required_of(profile),
        in_force_by_type(profile, localdate()),
    ):
        ProviderProfile.objects.filter(pk=profile.pk).update(
            status=provider_state(ProviderStates.ACTIVE)
        )


# Quien revisa acepta o rechaza un documento. Revisar sin tomar antes la toma; mientras
# el expediente está abierto, el veredicto se puede cambiar.
def review_document_sync(
    request_id: UUID,
    actor: ApiUser,
    data: DocumentReviewPost,
) -> ProviderRequestGet:
    reason: Reason | None = (
        None
        if data.accepted or data.reason is None
        else offered_reason(data.reason, data.note, CONTEXT_DOCUMENT_REJECTION)
    )

    with atomic():
        request: Any = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_not_taken_by_someone_else(request, actor)

        if request.taken_by is None:
            hold(request, actor)

        documents: list[Credential] = considered(
            request, expediente_of(request, localdate())
        )
        document: Any = next(
            (item for item in documents if item.pk == data.document_id),
            None,
        )

        if document is None:
            raise NotFoundError(detail="Ese documento no es de esta solicitud.")

        if document.request_id != request.pk and document.verdict:
            raise ConflictError(
                detail="Ese documento ya se aceptó en una solicitud anterior."
            )

        Credential.objects.filter(pk=document.pk).update(
            note=data.note.strip(),
            reason=reason,
            reviewed_at=now(),
            reviewed_by=actor,
            status=credential_state(CredentialStates.IN_REVIEW),
            verdict=Verdicts.ACCEPTED if data.accepted else Verdicts.REJECTED,
        )

        if is_renewal(request):
            settle_renewal(request, actor)

    return detail_sync(request_id)


# Quien revisa encontró algo mal: cierra el expediente para que el prestador lo corrija.
def request_changes_sync(
    request_id: UUID,
    actor: ApiUser,
    note: str,
) -> ProviderRequestGet:
    with atomic():
        request: Any = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_application(request)
        ensure_not_taken_by_someone_else(request, actor)

        documents: list[Credential] = considered(
            request, expediente_of(request, localdate())
        )

        if not any(item.verdict == Verdicts.REJECTED for item in documents):
            raise ConflictError(
                detail="Rechaza al menos un documento antes de pedir correcciones."
            )

        close(
            request,
            actor,
            approved=False,
            documents=documents,
            note=note,
            reason=Reason.objects.get(code=CHANGES_REQUESTED_REASON),
        )
        ProviderProfile.objects.filter(pk=request.provider_id).update(
            status=provider_state(ProviderStates.UNACCREDITED)
        )

    return detail_sync(request_id)


# La decisión final. Aprobar es lo único que hace visible al prestador y le da su rol.
def approve_sync(request_id: UUID, actor: ApiUser, note: str) -> ProviderRequestGet:
    with atomic():
        request: Any = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_application(request)

        today: date = localdate()
        expediente: Expediente = expediente_of(request, today)

        if not ready_to_decide(expediente, today):
            raise ConflictError(
                detail=(
                    "Cada documento que se pide tiene que estar aceptado y vigente "
                    "antes de aprobar."
                )
            )

        documents: list[Credential] = considered(request, expediente)

        put_in_force(documents)
        close(
            request,
            actor,
            approved=True,
            documents=documents,
            note=note,
            reason=None,
        )

        profile: Any = ProviderProfile.objects.get(pk=request.provider_id)
        profile.status = provider_state(ProviderStates.ACTIVE)

        if profile.approved_at is None:
            profile.approved_at = now()

        profile.save(update_fields=["approved_at", "status"])
        grant_provider_roles(profile, actor)

    return detail_sync(request_id)


def reject_sync(
    request_id: UUID,
    actor: ApiUser,
    *,
    note: str,
    reason_code: str,
) -> ProviderRequestGet:
    reason: Reason = offered_reason(reason_code, note, CONTEXT_PROVIDER_REJECTION)

    with atomic():
        request: Any = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_application(request)

        close(
            request,
            actor,
            approved=False,
            documents=considered(request, expediente_of(request, localdate())),
            note=note,
            reason=reason,
        )
        ProviderProfile.objects.filter(pk=request.provider_id).update(
            status=provider_state(ProviderStates.UNACCREDITED)
        )

    return detail_sync(request_id)


########################################################################################
# Avisar


async def notify_provider(detail: ProviderRequestGet) -> None:
    # le avisa al prestador lo que se decidió y, si hay algo que corregir, qué y por qué
    if detail.resolution is None:
        return

    rejected: list[tuple[str, str, str]] = [
        (
            item.type.label,
            "" if item.review.reason is None else item.review.reason.label,
            item.review.note,
        )
        for item in detail.documents
        if item.review is not None
        and not item.review.accepted
        and item.status == "rejected"
    ]

    await send_provider_decision(
        approved=detail.resolution.approved,
        documents=rejected,
        name=detail.applicant.name,
        note=detail.resolution.note,
        reason=""
        if detail.resolution.reason is None
        else detail.resolution.reason.label,
        renewal=detail.procedure == "renewal",
        to=detail.applicant.email,
    )
