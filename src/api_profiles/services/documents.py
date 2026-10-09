from typing import TYPE_CHECKING, Any

from django.db.models import Q

from api_catalogs.models import CredentialType
from api_core.services.uploads import UploadKinds, verify_upload
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError
from api_profiles.enums import CredentialStates, ProviderStates, Verdicts
from api_profiles.models import (
    Credential,
    CredentialStatus,
    ProviderProfile,
    ProviderService,
    ProviderStatus,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from datetime import date

    from api_moderation.models import VerificationRequest
    from api_profiles.schemas.application import DocumentPost

########################################################################################

CREDENTIAL_RELATED: tuple[str, ...] = ("credential_type", "reason", "status")


def field_error(field: str, message: str) -> BadRequestError:
    return BadRequestError(
        field_errors={field: message},
        type=BadRequestErrorTypes.FAILED_VALIDATION,
    ).scoped(RequestScopes.BODY)


def provider_state(code: ProviderStates) -> ProviderStatus:
    return ProviderStatus.objects.get(code=code)


def credential_state(code: CredentialStates) -> CredentialStatus:
    return CredentialStatus.objects.get(code=code)


########################################################################################
# Qué se le pide a cada quien


def services_of(profile: ProviderProfile) -> list[str]:
    return list(
        ProviderService.objects
        .filter(provider=profile)
        .order_by("service__code")
        .values_list("service__code", flat=True)
    )


# Los documentos que se le piden: los de todos, los del servicio que ofrece y los de
# vehículo si lleva turistas en el suyo. En el orden en que se muestran.
def required_types(
    services: Iterable[str],
    *,
    carries_tourists: bool,
) -> list[CredentialType]:
    offered: set[str] = set(services)
    rows: Any = (
        CredentialType.objects
        .select_related("service")
        .filter(active=True)
        .order_by("order", "label")
    )

    return [
        row
        for row in rows
        if (row.service is None or row.service.code in offered)
        and (not row.requires_vehicle or carries_tourists)
    ]


def required_of(profile: ProviderProfile) -> list[CredentialType]:
    found: Any = profile

    return required_types(
        services_of(profile),
        carries_tourists=bool(found.carries_tourists),
    )


########################################################################################
# Los documentos de un perfil


# El más reciente de cada tipo, sin contar los que ya se reemplazaron.
def latest_by_type(profile: ProviderProfile) -> dict[str, Credential]:
    rows: Any = (
        Credential.objects
        .select_related(*CREDENTIAL_RELATED)
        .filter(provider=profile)
        .exclude(status__code=CredentialStates.REPLACED)
        .order_by("credential_type__order", "-uploaded_at")
    )
    latest: dict[str, Credential] = {}

    for row in rows:
        latest.setdefault(str(row.credential_type.code), row)

    return latest


# Los que están en vigor: aprobados y sin vencer. Hay a lo sumo uno por tipo.
def in_force_by_type(profile: ProviderProfile, today: date) -> dict[str, Credential]:
    rows: Any = (
        Credential.objects
        .select_related(*CREDENTIAL_RELATED)
        .filter(provider=profile, status__code=CredentialStates.APPROVED)
        .filter(Q(expires_on__isnull=True) | Q(expires_on__gte=today))
    )

    return {str(row.credential_type.code): row for row in rows}


def is_expired(credential: Credential, today: date) -> bool:
    found: Any = credential

    return found.expires_on is not None and found.expires_on < today


# Todavía puede quedar en vigor: no hay que volver a subirlo.
def is_usable(credential: Credential, today: date) -> bool:
    found: Any = credential

    return (
        str(found.status.code)
        in {
            CredentialStates.APPROVED,
            CredentialStates.IN_REVIEW,
            CredentialStates.UPLOADED,
        }
        and found.verdict != Verdicts.REJECTED
        and not is_expired(credential, today)
    )


# Lo que falta mientras se postula: un tipo sin documento, o con uno que se rechazó o
# venció. Un documento con veredicto de rechazo en un expediente abierto no falta: está
# rechazado, y se cuenta así.
def missing_while_applying(
    required: Sequence[CredentialType],
    latest: dict[str, Credential],
    today: date,
) -> list[CredentialType]:
    missing: list[CredentialType] = []

    for credential_type in required:
        found: Any = latest.get(str(credential_type.code))

        if (
            found is None
            or str(found.status.code)
            in {CredentialStates.EXPIRED, CredentialStates.REJECTED}
            or is_expired(found, today)
        ):
            missing.append(credential_type)

    return missing


# Lo que le falta a un prestador ya aprobado: un tipo sin documento en vigor.
def missing_in_force(
    required: Sequence[CredentialType],
    in_force: dict[str, Credential],
) -> list[CredentialType]:
    return [item for item in required if str(item.code) not in in_force]


# Listo para decidir: cada tipo que se pide tiene un documento aceptado y sin vencer.
def accepted_for_decision(
    required: Sequence[CredentialType],
    latest: dict[str, Credential],
    today: date,
) -> bool:
    for credential_type in required:
        found: Any = latest.get(str(credential_type.code))

        if (
            found is None
            or found.verdict != Verdicts.ACCEPTED
            or not is_usable(found, today)
        ):
            return False

    return True


########################################################################################
# Lo que se sube


# Comprueba los documentos que se mandan contra los tipos que se aceptan: ninguno de
# más, ninguno repetido, la fecha de vencimiento donde se exige y el archivo ya subido.
def check_documents(
    documents: Sequence[DocumentPost],
    allowed: dict[str, CredentialType],
) -> None:
    seen: set[str] = set()

    for index, document in enumerate(documents):
        credential_type: Any = allowed.get(document.type)

        if credential_type is None:
            raise field_error(f"documents.{index}.type", "Ese documento no se pide.")

        if document.type in seen:
            raise field_error(
                f"documents.{index}.type", "Ese documento ya va en la lista."
            )

        seen.add(document.type)

        if credential_type.requires_expiry and document.expires_on is None:
            raise field_error(
                f"documents.{index}.expires_on",
                "Ese documento vence: escribe la fecha de vencimiento.",
            )

    # una consulta al almacenamiento por archivo: fuera de cualquier transacción
    for index, document in enumerate(documents):
        verify_upload(
            UploadKinds.PROVIDER_DOCUMENT,
            document.file_key,
            field=f"documents.{index}.file_key",
        )


def create_credentials(
    *,
    allowed: dict[str, CredentialType],
    documents: Sequence[DocumentPost],
    profile: ProviderProfile,
    request: VerificationRequest,
) -> list[Credential]:
    uploaded: CredentialStatus = credential_state(CredentialStates.UPLOADED)

    return [
        Credential.objects.create(
            credential_type=allowed[document.type],
            expires_on=document.expires_on,
            file_key=document.file_key,
            issued_on=document.issued_on,
            number=document.number,
            provider=profile,
            request=request,
            status=uploaded,
        )
        for document in documents
    ]
