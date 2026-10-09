from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.transaction import atomic
from django.utils.timezone import localdate
from django.views.decorators.debug import sensitive_variables

from api_auth.enums import VerificationPurposes
from api_auth.models import ApiUser
from api_auth.services.account import ensure_strong_password, invalid_code_error
from api_auth.services.verification import check_code_sync
from api_catalogs.models import Language, ServiceType
from api_exceptions.enums import RequestScopes
from api_exceptions.errors import ConflictError, NotFoundError
from api_moderation.enums import VerificationProcedures, VerificationStates
from api_moderation.models import (
    VerificationRequest,
    VerificationResolution,
    VerificationStatus,
)
from api_profiles.enums import (
    LEVEL_BY_API_NAME,
    CredentialStates,
    ProviderStates,
)
from api_profiles.models import (
    Credential,
    ProviderLanguage,
    ProviderProfile,
    ProviderService,
)
from api_profiles.services.documents import (
    check_documents,
    create_credentials,
    credential_state,
    field_error,
    is_usable,
    latest_by_type,
    provider_state,
    required_of,
    required_types,
)
from api_territory.models import City

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date
    from uuid import UUID

    from api_catalogs.models import CredentialType
    from api_profiles.schemas.application import (
        ProfileData,
        ProviderApplicationPost,
        ProviderRenewalPost,
        ProviderResubmitPost,
    )

########################################################################################


@dataclass(frozen=True, slots=True)
class Registered:
    user: ApiUser
    request: VerificationRequest


def submitted_state() -> VerificationStatus:
    return VerificationStatus.objects.get(code=VerificationStates.SUBMITTED)


########################################################################################
# Lo que hay que resolver antes de abrir la transacción


def find_city(city_id: UUID | None) -> City | None:
    if city_id is None:
        return None

    city: City | None = City.objects.filter(pk=city_id).first()

    if city is None:
        raise field_error("city_id", "Esa ciudad no existe.")

    return city


def find_services(codes: Sequence[str]) -> list[ServiceType]:
    found: list[ServiceType] = list(
        ServiceType.objects.filter(active=True, code__in=codes)
    )

    if len(found) != len(codes):
        raise field_error("services", "Ese servicio no existe.")

    return found


def find_languages(data: ProfileData) -> dict[str, Language]:
    codes: list[str] = [item.code for item in data.languages]
    found: dict[str, Language] = {
        str(row.code): row
        for row in Language.objects.filter(active=True, code__in=codes)
    }

    for index, code in enumerate(codes):
        if code not in found:
            raise field_error(f"languages.{index}.code", "Ese idioma no existe.")

    return found


def allowed_types(data: ProfileData) -> dict[str, CredentialType]:
    required = required_types(data.services, carries_tourists=data.carries_tourists)

    return {str(item.code): item for item in required}


def save_profile_relations(
    *,
    data: ProfileData,
    languages: dict[str, Language],
    profile: ProviderProfile,
    services: list[ServiceType],
) -> None:
    ProviderService.objects.filter(provider=profile).delete()
    ProviderService.objects.bulk_create(
        ProviderService(provider=profile, service=service) for service in services
    )

    ProviderLanguage.objects.filter(provider=profile).delete()
    ProviderLanguage.objects.bulk_create(
        ProviderLanguage(
            language=languages[item.code],
            level=LEVEL_BY_API_NAME[item.level],
            provider=profile,
        )
        for item in data.languages
    )


########################################################################################
# Postularse


# Crea la cuenta del prestador, su perfil, sus documentos y el expediente, todo en una
# transacción: si algo falla, el código del correo vuelve a servir. La cuenta nace sin
# papel: el de guía o traductor llega con la aprobación (una cuenta, un papel).
def register_sync(data: ProviderApplicationPost) -> Registered:
    city: City | None = find_city(data.city_id)
    services: list[ServiceType] = find_services(data.services)
    languages: dict[str, Language] = find_languages(data)
    allowed: dict[str, CredentialType] = allowed_types(data)

    missing: list[str] = [
        str(item.label)
        for code, item in allowed.items()
        if code not in {document.type for document in data.documents}
    ]

    if missing:
        raise field_error("documents", f"Falta: {', '.join(missing)}.")

    check_documents(data.documents, allowed)

    # primero se comprueba aparte: un código equivocado suma un intento, y ese intento
    # tiene que quedar guardado aunque la petición termine en error
    if not check_code_sync(
        code=data.code,
        consume=False,
        destination=data.email,
        purpose=VerificationPurposes.EMAIL,
    ):
        raise invalid_code_error()

    def persist() -> Registered:
        with atomic():
            if not check_code_sync(
                code=data.code,
                consume=True,
                destination=data.email,
                purpose=VerificationPurposes.EMAIL,
            ):
                raise invalid_code_error()

            user: ApiUser = ApiUser.objects.create_user(
                birth_date=data.birth_date,
                email=data.email,
                first_name=data.first_name,
                last_name=data.last_name,
                nationality=data.nationality,
                password=data.password,
            )

            profile: ProviderProfile = ProviderProfile.objects.create(
                carries_tourists=data.carries_tourists,
                city=city,
                phone=data.phone,
                presentation=data.presentation,
                status=provider_state(ProviderStates.IN_REVIEW),
                user=user,
            )

            save_profile_relations(
                data=data,
                languages=languages,
                profile=profile,
                services=services,
            )

            request: VerificationRequest = VerificationRequest.objects.create(
                procedure=VerificationProcedures.APPLICATION,
                provider=profile,
                status=submitted_state(),
            )

            create_credentials(
                allowed=allowed,
                documents=data.documents,
                profile=profile,
                request=request,
            )

            return Registered(request=request, user=user)

    try:
        return persist()
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i


@sensitive_variables()
async def register(data: ProviderApplicationPost) -> Registered:
    # primero la contraseña, para no gastar el código de quien la eligió mal
    await sync_to_async(ensure_strong_password)(
        data.password,
        user=ApiUser(
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
        ),
    )

    return await sync_to_async(register_sync)(data)


########################################################################################
# Lo que ve quien se postuló


def own_profile_sync(user: ApiUser, *, lock: bool = False) -> ProviderProfile:
    profiles: Any = ProviderProfile.objects.select_related("city", "status", "user")

    if lock:
        profiles = profiles.select_for_update(of=("self",))

    profile: ProviderProfile | None = profiles.filter(user=user).first()

    if profile is None:
        raise NotFoundError(detail="Tu cuenta no es de un guía o traductor.")

    return profile


def latest_request_of(profile: ProviderProfile) -> VerificationRequest | None:
    return (
        VerificationRequest.objects
        .select_related("provider__city", "provider__status", "status")
        .filter(provider=profile)
        .order_by("-submitted_at")
        .first()
    )


def latest_application_sync(user: ApiUser) -> VerificationRequest:
    request: VerificationRequest | None = latest_request_of(own_profile_sync(user))

    if request is None:
        raise NotFoundError(detail="Tu cuenta no tiene una solicitud.")

    return request


########################################################################################
# Corregir y volver a enviar


def ensure_rejected(latest: VerificationRequest | None) -> None:
    if latest is None:
        raise NotFoundError(detail="Tu cuenta no tiene una solicitud.")

    found: Any = latest

    if found.resolved_at is None:
        raise ConflictError(detail="Tu solicitud todavía está en revisión.")

    resolution: Any = VerificationResolution.objects.filter(request=latest).first()

    if resolution is None or resolution.approved:
        raise ConflictError(detail="Tu solicitud ya fue aprobada.")


# Quien se postuló corrige lo que el equipo rechazó y lo manda de nuevo: abre otro
# expediente. Lo aceptado pasa tal cual; lo rechazado, lo vencido y lo que falta se
# sube otra vez. Un prestador ya aprobado no se postula de nuevo: renueva.
def resubmit_sync(user: ApiUser, data: ProviderResubmitPost) -> VerificationRequest:
    city: City | None = find_city(data.city_id)
    services: list[ServiceType] = find_services(data.services)
    languages: dict[str, Language] = find_languages(data)
    allowed: dict[str, CredentialType] = allowed_types(data)

    check_documents(data.documents, allowed)

    today: date = localdate()

    def persist() -> VerificationRequest:
        with atomic():
            profile: Any = own_profile_sync(user, lock=True)

            if profile.approved_at is not None:
                raise ConflictError(
                    detail="Tu perfil ya fue aprobado: renueva tus documentos."
                )

            ensure_rejected(latest_request_of(profile))

            latest: dict[str, Credential] = latest_by_type(profile)
            replaced: set[str] = {document.type for document in data.documents}

            lacking: list[str] = [
                str(item.label)
                for code, item in allowed.items()
                if code not in replaced
                and (code not in latest or not is_usable(latest[code], today))
            ]

            if lacking:
                raise field_error("documents", f"Sube de nuevo: {', '.join(lacking)}.")

            # lo que se sube otra vez reemplaza a lo que todavía no se resolvía
            Credential.objects.filter(
                credential_type__code__in=replaced,
                provider=profile,
                status__code__in=(
                    CredentialStates.IN_REVIEW,
                    CredentialStates.UPLOADED,
                ),
            ).update(status=credential_state(CredentialStates.REPLACED))

            profile.carries_tourists = data.carries_tourists
            profile.city = city
            profile.phone = data.phone
            profile.presentation = data.presentation
            profile.status = provider_state(ProviderStates.IN_REVIEW)
            profile.save()

            save_profile_relations(
                data=data,
                languages=languages,
                profile=profile,
                services=services,
            )

            request: VerificationRequest = VerificationRequest.objects.create(
                procedure=VerificationProcedures.APPLICATION,
                provider=profile,
                status=submitted_state(),
            )

            create_credentials(
                allowed=allowed,
                documents=data.documents,
                profile=profile,
                request=request,
            )

            return request

    try:
        return persist()
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i


########################################################################################
# Renovar


# Un prestador aprobado sube la versión nueva de uno o más documentos. Mientras se
# revisa, lo anterior sigue en vigor: no deja de trabajar (RF-P-04).
def renew_sync(user: ApiUser, data: ProviderRenewalPost) -> VerificationRequest:
    profile: Any = own_profile_sync(user)
    allowed: dict[str, CredentialType] = {
        str(item.code): item for item in required_of(profile)
    }

    check_documents(data.documents, allowed)

    def persist() -> VerificationRequest:
        with atomic():
            locked: Any = own_profile_sync(user, lock=True)

            if locked.approved_at is None or str(locked.status.code) not in {
                ProviderStates.ACTIVE,
                ProviderStates.SUSPENDED,
            }:
                raise ConflictError(
                    detail="Solo un guía o traductor aprobado renueva documentos."
                )

            if VerificationRequest.objects.filter(
                provider=locked,
                resolved_at__isnull=True,
            ).exists():
                raise ConflictError(detail="Ya tienes una solicitud en revisión.")

            request: VerificationRequest = VerificationRequest.objects.create(
                procedure=VerificationProcedures.RENEWAL,
                provider=locked,
                status=submitted_state(),
            )

            create_credentials(
                allowed=allowed,
                documents=data.documents,
                profile=locked,
                request=request,
            )

            return request

    try:
        return persist()
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i
