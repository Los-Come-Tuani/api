from math import ceil
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.services.mail import send_application_decision
from api_catalogs.models import Reason, ReasonContext
from api_catalogs.seeder import CONTEXT_VERIFICATION_REJECTION
from api_core.schemas.pagination import Paginated
from api_core.services.uploads import read_url
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from api_moderation.enums import API_STATUS, VerificationStates
from api_moderation.models import (
    VerificationRequest,
    VerificationResolution,
    VerificationStatus,
)
from api_moderation.schemas import (
    BusinessDetailGet,
    CityRef,
    DocumentGet,
    HistoryItem,
    HoursGet,
    InstitutionDetailGet,
    MunicipalityDetailGet,
    OptionRef,
    PersonRef,
    RejectionReasonGet,
    SignatureDishGet,
    VerificationQuery,
    VerificationRequestGet,
    VerificationRequestInlineGet,
)
from api_organizations.models import Business, SignatureDish
from api_organizations.schemas.application import ReasonGet, ResolutionGet
from api_organizations.services.application import organization_record
from api_roles.models import RoleAssignment

if TYPE_CHECKING:
    from typing import Final
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser

########################################################################################

# - el estado que corresponde a cada filtro de la bandeja
OPEN_STATES: Final[tuple[str, ...]] = (
    VerificationStates.SUBMITTED,
    VerificationStates.IN_REVIEW,
)

STATE_BY_API_NAME: Final[dict[str, str]] = {
    name: code for code, name in API_STATUS.items()
}

RELATED: Final[tuple[str, ...]] = (
    "business__city",
    "business__business_type",
    "institution__city",
    "institution__institution_type",
    "municipality__city",
    "status",
    "taken_by",
)

OPEN_FIELDS: Final[dict[str, str]] = {
    "business": "business",
    "institution": "institution",
    "municipality": "municipality",
}


def person(user: ApiUser | None) -> PersonRef | None:
    if user is None:
        return None

    account: Any = user

    return PersonRef(id=account.pk, name=account.display_name, email=str(account.email))


########################################################################################
# Lectura


def kind_of(request: VerificationRequest) -> str:
    return organization_record(request)[0]


def inline_payload(request: VerificationRequest) -> VerificationRequestInlineGet:
    found: Any = request
    kind, record = organization_record(request)

    return VerificationRequestInlineGet(
        city=CityRef(
            code=str(record.city.code),
            id=record.city.pk,
            name=str(record.city.name),
        ),
        id=found.pk,
        kind=kind,  # ty: ignore[invalid-argument-type]
        organization_id=record.pk,
        organization_name=str(record.name),
        resolved_at=found.resolved_at,
        status=API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        submitted_at=found.submitted_at,
        taken_by=person(found.taken_by),
    )


def organization_requests() -> QuerySet:
    # la cola de las organizaciones: los expedientes de los prestadores van por la suya
    # (`provider-request/`), con otros permisos
    return VerificationRequest.objects.select_related(*RELATED).filter(
        provider__isnull=True
    )


def queue_sync(query: VerificationQuery) -> Paginated[VerificationRequestInlineGet]:
    requests = organization_requests()

    if query.status == "open":
        requests = requests.filter(status__code__in=OPEN_STATES)
    elif query.status != "all":
        requests = requests.filter(status__code=STATE_BY_API_NAME[query.status])

    if query.kind is not None:
        requests = requests.filter(**{f"{OPEN_FIELDS[query.kind]}__isnull": False})

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

    return Paginated[VerificationRequestInlineGet](
        current=query.page,
        elements=total,
        next=query.page < pages,
        pages=pages,
        previous=query.page > 1,
        results=[
            inline_payload(item) for item in ordered[start : start + query.page_size]
        ],
    )


def applicant_of_sync(request: VerificationRequest) -> ApiUser | None:
    kind, record = organization_record(request)

    assignment: Any = (
        RoleAssignment.objects
        .select_related("user")
        .filter(revoked_at__isnull=True, **{OPEN_FIELDS[kind]: record})
        .order_by("granted_at")
        .first()
    )

    return None if assignment is None else assignment.user


def business_detail(record: Business) -> tuple[BusinessDetailGet, list[DocumentGet]]:
    # los atributos de los modelos de Django no tienen tipos para ty: se leen sin ellos
    business: Any = record

    dish: Any = (
        SignatureDish.objects
        .select_related("currency", "photo")
        .filter(business=record, withdrawn_at__isnull=True)
        .first()
    )

    documents: list[DocumentGet] = []

    if dish is not None and dish.photo is not None:
        documents.append(
            DocumentGet(
                kind="signature_dish_photo",
                url=read_url(str(dish.photo.file_key)),
            )
        )

    return (
        BusinessDetailGet(
            address=str(business.address),
            alternate_phone=str(business.alternate_phone),
            business_type=OptionRef(
                code=str(business.business_type.code),
                label=str(business.business_type.label),
            ),
            hours=[
                HoursGet(
                    closed=bool(row.closed),
                    closes=row.closes,
                    opens=row.opens,
                    weekday=int(row.weekday),
                )
                for row in business.hours.order_by("weekday")
            ],
            latitude=float(business.latitude),
            longitude=float(business.longitude),
            phone=str(business.phone),
            ruc=str(business.ruc),
            signature_dish=(
                None
                if dish is None
                else SignatureDishGet(
                    currency=str(dish.currency.code),
                    description=str(dish.description),
                    name=str(dish.name),
                    reference_price=float(dish.reference_price),
                )
            ),
        ),
        documents,
    )


def history_of(request: VerificationRequest) -> list[HistoryItem]:
    kind, record = organization_record(request)

    previous = (
        VerificationRequest.objects
        .select_related("status")
        .filter(**{OPEN_FIELDS[kind]: record})
        .exclude(pk=request.pk)
        .order_by("-submitted_at")
    )

    items: list[HistoryItem] = []

    for item in previous:
        found: Any = item
        resolution: Any = (
            VerificationResolution.objects
            .select_related("reason")
            .filter(request=item)
            .first()
        )

        items.append(
            HistoryItem(
                id=found.pk,
                note="" if resolution is None else str(resolution.note),
                reason=(
                    None
                    if resolution is None or resolution.reason is None
                    else ReasonGet(
                        code=str(resolution.reason.code),
                        label=str(resolution.reason.label),
                    )
                ),
                resolved_at=found.resolved_at,
                status=API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
                submitted_at=found.submitted_at,
            )
        )

    return items


def fetch_request(request_id: UUID, *, lock: bool = False) -> VerificationRequest:
    requests = organization_requests()

    found: VerificationRequest | None = (
        requests.select_for_update(of=("self",)).filter(pk=request_id).first()
        if lock
        else requests.filter(pk=request_id).first()
    )

    if found is None:
        raise NotFoundError(detail="No encontramos esa solicitud.")

    return found


def detail_sync(request_id: UUID) -> VerificationRequestGet:
    request: VerificationRequest = fetch_request(request_id)
    inline = inline_payload(request)
    kind, record = organization_record(request)

    business = institution = municipality = None
    documents: list[DocumentGet] = []

    if kind == "business":
        business, documents = business_detail(record)
    elif kind == "institution":
        institution = InstitutionDetailGet(
            contact_email=str(record.contact_email),
            institution_type=OptionRef(
                code=str(record.institution_type.code),
                label=str(record.institution_type.label),
            ),
            phone=str(record.phone),
        )
        documents = [
            DocumentGet(kind="legal_document", url=read_url(str(record.document_key)))
        ]
    else:
        municipality = MunicipalityDetailGet(
            contact_email=str(record.contact_email),
            phone=str(record.phone),
        )
        documents = [
            DocumentGet(kind="legal_document", url=read_url(str(record.document_key)))
        ]

    resolution: Any = (
        VerificationResolution.objects
        .select_related("reason")
        .filter(request=request)
        .first()
    )

    return VerificationRequestGet(
        **dict(inline),
        applicant=person(applicant_of_sync(request)),
        business=business,
        documents=documents,
        history=history_of(request),
        institution=institution,
        municipality=municipality,
        resolution=(
            None
            if resolution is None
            else ResolutionGet(
                approved=bool(resolution.approved),
                note=str(resolution.note),
                reason=(
                    None
                    if resolution.reason is None
                    else ReasonGet(
                        code=str(resolution.reason.code),
                        label=str(resolution.reason.label),
                    )
                ),
                resolved_at=resolution.resolved_at,
            )
        ),
    )


def rejection_reasons_sync() -> list[RejectionReasonGet]:
    offered = (
        ReasonContext.objects
        .select_related("reason")
        .filter(context=CONTEXT_VERIFICATION_REJECTION, reason__active=True)
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


########################################################################################
# Atender el expediente


def state(code: VerificationStates) -> VerificationStatus:
    return VerificationStatus.objects.get(code=code)


def ensure_open(request: VerificationRequest) -> None:
    if request.resolved_at is not None:
        raise ConflictError(detail="Esta solicitud ya se resolvió.")


def ensure_not_taken_by_someone_else(
    request: VerificationRequest,
    actor: ApiUser,
    *,
    can_manage: bool,
) -> None:
    holder: Any = request.taken_by

    if holder is not None and holder.pk != actor.pk and not can_manage:
        raise ConflictError(
            detail=f"{holder.display_name} ya tiene esta solicitud en revisión.",
        )


# El moderador toma la solicitud: queda en revisión y a su nombre.
def take_sync(request_id: UUID, actor: ApiUser) -> VerificationRequestGet:
    with atomic():
        request: VerificationRequest = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_not_taken_by_someone_else(request, actor, can_manage=False)

        VerificationRequest.objects.filter(pk=request.pk).update(
            status=state(VerificationStates.IN_REVIEW),
            taken_by=actor,
        )

    return detail_sync(request_id)


# Devolverla a la cola: la suelta quien la tiene, o quien administra las organizaciones.
def release_sync(
    request_id: UUID,
    actor: ApiUser,
    *,
    can_manage: bool,
) -> VerificationRequestGet:
    with atomic():
        request: VerificationRequest = fetch_request(request_id, lock=True)
        holder: Any = request.taken_by

        ensure_open(request)

        if holder is None:
            raise ConflictError(detail="Esta solicitud no está en revisión.")

        if holder.pk != actor.pk and not can_manage:
            raise ForbiddenError(
                detail="Solo quien la tiene en revisión puede devolverla."
            )

        VerificationRequest.objects.filter(pk=request.pk).update(
            status=state(VerificationStates.SUBMITTED),
            taken_by=None,
        )

    return detail_sync(request_id)


def offered_reason(code: str, note: str) -> Reason:
    reason: Reason | None = Reason.objects.filter(
        Q(contexts__context=CONTEXT_VERIFICATION_REJECTION),
        active=True,
        code=code,
    ).first()

    if reason is None:
        raise BadRequestError(
            field_errors={"reason": "Ese motivo no se ofrece para rechazar."},
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


# Cierra el expediente. La resolución es de solo inserción y, si aprueba, la base marca
# el objeto como verificado: eso es lo único que lo hace visible.
def resolve_sync(  # ruff: ignore[too-many-arguments]
    request_id: UUID,
    actor: ApiUser,
    *,
    approved: bool,
    can_manage: bool,
    note: str,
    reason_code: str | None,
) -> VerificationRequestGet:
    reason: Reason | None = (
        None if approved or reason_code is None else offered_reason(reason_code, note)
    )

    with atomic():
        request: VerificationRequest = fetch_request(request_id, lock=True)

        ensure_open(request)
        ensure_not_taken_by_someone_else(request, actor, can_manage=can_manage)

        resolved_at = now()

        VerificationResolution.objects.create(
            approved=approved,
            note=note.strip(),
            reason=reason,
            request=request,
            resolved_by=actor,
        )

        VerificationRequest.objects.filter(pk=request.pk).update(
            resolved_at=resolved_at,
            status=state(
                VerificationStates.APPROVED if approved else VerificationStates.REJECTED
            ),
            taken_by=actor,
        )

    return detail_sync(request_id)


async def notify_applicant(detail: VerificationRequestGet) -> None:
    # le avisa a quien se postuló lo que se decidió, con el motivo si se rechazó
    request = await sync_to_async(fetch_request)(detail.id)
    applicant = await sync_to_async(applicant_of_sync)(request)

    if applicant is None or detail.resolution is None:
        return

    await send_application_decision(
        approved=detail.resolution.approved,
        name=applicant.display_name,
        note=detail.resolution.note,
        organization=detail.organization_name,
        reason=""
        if detail.resolution.reason is None
        else detail.resolution.reason.label,
        to=str(applicant.email),
    )
