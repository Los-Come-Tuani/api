from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.utils.timezone import localdate

from api_core.services.uploads import read_url
from api_moderation.enums import API_STATUS, PROCEDURE_API_NAMES, VerificationProcedures
from api_moderation.models import VerificationRequest, VerificationResolution
from api_moderation.schemas import CityRef
from api_organizations.schemas.application import ReasonGet, ResolutionGet
from api_profiles.enums import (
    CREDENTIAL_API_STATUS,
    LEVEL_API_NAMES,
    PROVIDER_API_STATUS,
    Verdicts,
)
from api_profiles.models import (
    Credential,
    ProviderLanguage,
    ProviderProfile,
)
from api_profiles.schemas.application import (
    CredentialGet,
    FileGet,
    LanguageLevelGet,
    OptionRef,
    ProfileDataGet,
    ProviderApplicationGet,
    ProviderSummaryGet,
    ReviewGet,
)
from api_profiles.schemas.profile import LanguageGet, ProviderProfileGet
from api_profiles.services.documents import (
    in_force_by_type,
    latest_by_type,
    missing_in_force,
    missing_while_applying,
    required_of,
    services_of,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date
    from uuid import UUID

    from api_auth.models import ApiUser
    from api_catalogs.models import CredentialType, Reason
    from api_territory.models import City

########################################################################################


# El perfil de prestador de una persona, como lo muestra la sesión.
@dataclass(frozen=True, slots=True)
class ProviderRef:
    id: UUID
    status: str
    services: tuple[str, ...]


def provider_of_sync(user: ApiUser) -> ProviderProfile | None:
    found: ProviderProfile | None = (
        ProviderProfile.objects
        .select_related("city", "status")
        .filter(user=user)
        .first()
    )

    return found


def provider_ref_sync(user: ApiUser) -> ProviderRef | None:
    profile: Any = provider_of_sync(user)

    if profile is None:
        return None

    return ProviderRef(
        id=profile.pk,
        services=tuple(services_of(profile)),
        status=PROVIDER_API_STATUS[str(profile.status.code)],
    )


########################################################################################
# Piezas


def option(credential_type: CredentialType) -> OptionRef:
    found: Any = credential_type

    return OptionRef(code=str(found.code), label=str(found.label))


def file_payload(key: str) -> FileGet:
    return FileGet(key=key, url=read_url(key))


def reason_payload(reason: Reason | None) -> ReasonGet | None:
    if reason is None:
        return None

    return ReasonGet(code=str(reason.code), label=str(reason.label))


def credential_payload(credential: Credential) -> CredentialGet:
    found: Any = credential

    return CredentialGet(
        expires_on=found.expires_on,
        file=file_payload(str(found.file_key)),
        id=found.pk,
        issued_on=found.issued_on,
        number=str(found.number),
        review=(
            None
            if not found.verdict
            else ReviewGet(
                accepted=found.verdict == Verdicts.ACCEPTED,
                note=str(found.note),
                reason=reason_payload(found.reason),
                reviewed_at=found.reviewed_at,
            )
        ),
        status=CREDENTIAL_API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        type=option(found.credential_type),
        uploaded_at=found.uploaded_at,
    )


def languages_of(profile: ProviderProfile) -> list[Any]:
    return list(
        ProviderLanguage.objects
        .select_related("language")
        .filter(provider=profile)
        .order_by("language__name")
    )


def language_payloads(profile: ProviderProfile) -> list[LanguageGet]:
    return [
        LanguageGet(
            code=str(row.language.code),
            label=str(row.language.name),
            level=LEVEL_API_NAMES[str(row.level)],  # ty: ignore[invalid-argument-type]
        )
        for row in languages_of(profile)
    ]


def city_payload(city: City | None) -> CityRef | None:
    if city is None:
        return None

    return CityRef(code=str(city.code), id=city.pk, name=str(city.name))


def profile_data(profile: ProviderProfile) -> ProfileDataGet:
    found: Any = profile

    return ProfileDataGet(
        carries_tourists=bool(found.carries_tourists),
        city_id=found.city_id,
        languages=[
            LanguageLevelGet(
                code=str(row.language.code),
                level=LEVEL_API_NAMES[str(row.level)],  # ty: ignore[invalid-argument-type]
            )
            for row in languages_of(profile)
        ],
        phone=str(found.phone),
        presentation=str(found.presentation),
        services=services_of(profile),
    )


def summary(profile: ProviderProfile) -> ProviderSummaryGet:
    found: Any = profile

    return ProviderSummaryGet(
        approved_at=found.approved_at,
        id=found.pk,
        services=services_of(profile),
        status=PROVIDER_API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
    )


def resolution_of(request: VerificationRequest) -> ResolutionGet | None:
    resolution: Any = (
        VerificationResolution.objects
        .select_related("reason")
        .filter(request=request)
        .first()
    )

    if resolution is None:
        return None

    return ResolutionGet(
        approved=bool(resolution.approved),
        note=str(resolution.note),
        reason=reason_payload(resolution.reason),
        resolved_at=resolution.resolved_at,
    )


########################################################################################
# Los documentos de un expediente


@dataclass(frozen=True, slots=True)
class Expediente:
    # los documentos que se muestran, con si se subieron en este expediente
    documents: list[tuple[Credential, bool]]
    required: list[CredentialType]
    missing: list[CredentialType]


# En la postulación, lo vigente de cada tipo (lo de este expediente y lo aceptado que
# viene de uno anterior). En una renovación, lo que se subió en ella y lo que ya está en
# vigor, para compararlos.
def expediente_of(request: VerificationRequest, today: date) -> Expediente:
    found: Any = request
    profile: ProviderProfile = found.provider
    required: list[CredentialType] = required_of(profile)

    if found.procedure == VerificationProcedures.RENEWAL:
        uploaded: list[Credential] = list(
            Credential.objects
            .select_related("credential_type", "reason", "status")
            .filter(request=request)
            .order_by("credential_type__order")
        )
        in_force = in_force_by_type(profile, today)
        renewed: set[str] = {
            str(item.credential_type.code)  # ty: ignore[unresolved-attribute]
            for item in uploaded
        }

        return Expediente(
            documents=[(item, True) for item in uploaded]
            + [
                (item, False)
                for item in sorted(
                    in_force.values(),
                    key=lambda credential: int(credential.credential_type.order),  # ty: ignore[unresolved-attribute]
                )
            ],
            missing=[
                item
                for item in missing_in_force(required, in_force)
                if str(item.code) not in renewed
            ],
            required=required,
        )

    latest = latest_by_type(profile)

    return Expediente(
        documents=[
            (item, item.request_id == found.pk)  # ty: ignore[unresolved-attribute]
            for item in latest.values()
        ],
        missing=missing_while_applying(required, latest, today),
        required=required,
    )


########################################################################################
# Lo que ve el prestador


def mine_payload(request: VerificationRequest) -> ProviderApplicationGet:
    found: Any = request
    profile: ProviderProfile = found.provider
    expediente = expediente_of(request, localdate())

    return ProviderApplicationGet(
        documents=[credential_payload(item) for item, _ in expediente.documents],
        id=found.pk,
        missing=[option(item) for item in expediente.missing],
        procedure=PROCEDURE_API_NAMES[str(found.procedure)],  # ty: ignore[invalid-argument-type]
        profile=profile_data(profile),
        provider=summary(profile),
        resolution=resolution_of(request),
        resolved_at=found.resolved_at,
        status=API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        submitted_at=found.submitted_at,
    )


def profile_payload(profile: ProviderProfile) -> ProviderProfileGet:
    found: Any = profile
    today: date = localdate()
    required: Sequence[CredentialType] = required_of(profile)
    in_force = in_force_by_type(profile, today)
    latest = latest_by_type(profile)

    # uno por tipo: el que está en vigor o, si no hay, el más reciente
    shown: dict[str, Credential] = {**latest, **in_force}

    return ProviderProfileGet(
        approved_at=found.approved_at,
        carries_tourists=bool(found.carries_tourists),
        city=city_payload(found.city),
        documents=[
            credential_payload(item)
            for item in sorted(
                shown.values(),
                key=lambda credential: int(credential.credential_type.order),  # ty: ignore[unresolved-attribute]
            )
        ],
        id=found.pk,
        languages=language_payloads(profile),
        missing=[option(item) for item in missing_in_force(required, in_force)],
        phone=str(found.phone),
        photo=file_payload(str(found.photo_key)) if found.photo_key else None,
        presentation=str(found.presentation),
        rating=None if found.rating_average is None else float(found.rating_average),
        reviews=int(found.reviews_count),
        services=services_of(profile),
        status=PROVIDER_API_STATUS[str(found.status.code)],  # ty: ignore[invalid-argument-type]
    )
