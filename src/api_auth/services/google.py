import json

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import jwt

from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db.transaction import atomic
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWTError

from api_auth.enums import AccountRoles, ApiUserTypes, IdentityProviders, Surfaces
from api_auth.models import ApiExternalIdentity, ApiUser
from api_core.config import CONFIG
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import (
    ApiError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)

from .account import ensure_can_operate
from .roles import PUBLIC_ROLES, role_of_sync

if TYPE_CHECKING:
    from typing import Final

    from api_auth.schemas.google import GooglePost

########################################################################################

GOOGLE_ISSUERS: Final[frozenset[str]] = frozenset({
    "accounts.google.com",
    "https://accounts.google.com",
})

# - las llaves públicas con las que Google firma sus tokens de identidad
GOOGLE_JWKS_URL: Final[str] = "https://www.googleapis.com/oauth2/v3/certs"

# - dice para qué cliente y para qué cuenta emitió Google un token de acceso
GOOGLE_TOKENINFO_URL: Final[str] = "https://oauth2.googleapis.com/tokeninfo"

GOOGLE_TIMEOUT_SECONDS: Final[int] = 5

# - tolerancia al desfase de reloj entre Google y este servidor
CLOCK_LEEWAY_SECONDS: Final[int] = 10

DISABLED_DETAIL: Final[str] = "El inicio de sesión con Google no está habilitado."
UNREACHABLE_DETAIL: Final[str] = (
    "No se pudo validar con Google. Intenta de nuevo en un momento."
)
TOKEN_FIELD_DETAIL: Final[str] = "Manda el token de identidad o el de acceso de Google."  # ruff: ignore[hardcoded-password-string]
INVALID_TOKEN_DETAIL: Final[str] = "El token de Google no es válido."  # ruff: ignore[hardcoded-password-string]
UNVERIFIED_DETAIL: Final[str] = "Google no ha verificado el correo de esta cuenta."
WRONG_SURFACE_DETAIL: Final[str] = (
    "Esta cuenta debe usar la forma de acceso indicada para su tipo."
)

WEB_ROLES: Final[frozenset[str]] = frozenset({
    AccountRoles.ADMIN.value,
    AccountRoles.ALCALDIA.value,
    AccountRoles.INSTITUCION.value,
    AccountRoles.NEGOCIO.value,
})

########################################################################################


@dataclass(frozen=True, slots=True)
class GoogleProfile:
    email: str
    first_name: str
    last_name: str
    subject: str


########################################################################################


@cache
def jwks_client() -> PyJWKClient:
    # PyJWKClient guarda las llaves en memoria y vuelve a pedirlas si llega un `kid`
    # que no conoce, que es como Google rota las suyas
    return PyJWKClient(GOOGLE_JWKS_URL, timeout=5)


def signing_key_for(token: str) -> object:
    return jwks_client().get_signing_key_from_jwt(token).key


def split_name(claims: dict) -> tuple[str, str]:
    first: str = str(claims.get("given_name") or "").strip()
    last: str = str(claims.get("family_name") or "").strip()

    if first or last:
        return first[:100], last[:100]

    full: str = str(claims.get("name") or "").strip()
    head, _, tail = full.partition(" ")

    return head[:100], tail.strip()[:100]


@sensitive_variables()
def verify_token_sync(token: str) -> GoogleProfile:
    try:
        claims: dict = jwt.decode(
            token,
            key=signing_key_for(token),  # ty: ignore[invalid-argument-type]
            algorithms=["RS256"],
            audience=list(CONFIG.GOOGLE_OAUTH_CLIENT_IDS),
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": ["aud", "exp", "iat", "iss", "sub"]},
        )
    except PyJWKClientConnectionError as c:
        # el problema es de Google o de la red, no de quien inicia sesión
        raise ApiError(detail=UNREACHABLE_DETAIL) from c
    except PyJWTError as e:
        raise UnauthorizedError(detail=INVALID_TOKEN_DETAIL) from e

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise UnauthorizedError(detail=INVALID_TOKEN_DETAIL)

    email: str = str(claims.get("email") or "").strip().lower()

    if not email or str(claims.get("email_verified")).lower() != "true":
        raise UnauthorizedError(detail=UNVERIFIED_DETAIL)

    first_name, last_name = split_name(claims)

    return GoogleProfile(
        email=email,
        first_name=first_name,
        last_name=last_name,
        subject=str(claims["sub"]),
    )


def tokeninfo(token: str) -> dict:
    query: str = urlencode({"access_token": token})

    with urlopen(  # ruff: ignore[suspicious-url-open-usage]
        f"{GOOGLE_TOKENINFO_URL}?{query}",
        timeout=GOOGLE_TIMEOUT_SECONDS,
    ) as response:
        return json.load(response)


@sensitive_variables()
def verify_access_token_sync(token: str) -> GoogleProfile:
    # El token de acceso no está firmado para nosotros como el de identidad: Google dice
    # a qué cliente se lo dio. Sin revisar `aud`, el token que otra app obtuvo de esa
    # persona serviría para entrar aquí.
    try:
        claims: dict = tokeninfo(token)
    except HTTPError as e:
        # Google responde 400 a un token vencido, revocado o inventado
        raise UnauthorizedError(detail=INVALID_TOKEN_DETAIL) from e
    except (URLError, TimeoutError, ValueError) as e:
        raise ApiError(detail=UNREACHABLE_DETAIL) from e

    if claims.get("aud") not in CONFIG.GOOGLE_OAUTH_CLIENT_IDS or not claims.get("sub"):
        raise UnauthorizedError(detail=INVALID_TOKEN_DETAIL)

    try:
        expires_in = int(claims.get("expires_in") or 0)
    except ValueError:
        expires_in = 0

    if expires_in <= 0:
        raise UnauthorizedError(detail=INVALID_TOKEN_DETAIL)

    email: str = str(claims.get("email") or "").strip().lower()

    if not email or str(claims.get("email_verified")).lower() != "true":
        raise UnauthorizedError(detail=UNVERIFIED_DETAIL)

    # el token de acceso no trae el nombre: en el portal Google no crea cuentas
    return GoogleProfile(
        email=email,
        first_name="",
        last_name="",
        subject=str(claims["sub"]),
    )


########################################################################################


def missing_profile_error() -> BadRequestError:
    msg = "Este campo es requerido para crear tu cuenta."

    return BadRequestError(
        detail="Faltan datos para crear tu cuenta.",
        field_errors={"birth_date": msg, "nationality": msg},
        type=BadRequestErrorTypes.MISSING_FIELDS,
    ).scoped(RequestScopes.BODY)


def create_account_sync(profile: GoogleProfile, data: GooglePost) -> ApiUser:
    if data.birth_date is None or data.nationality is None:
        raise missing_profile_error()

    try:
        with atomic():
            user: ApiUser = ApiUser.objects.create_user(
                birth_date=data.birth_date,
                email=profile.email,
                first_name=profile.first_name,
                last_name=profile.last_name,
                nationality=data.nationality,
                password=None,
                verified_at=now(),
            )

            user.groups.add(Group.objects.get(name=ApiUserTypes.CLIENT))  # ty: ignore[unresolved-attribute]

            ApiExternalIdentity.objects.create(
                email=profile.email,
                provider=IdentityProviders.GOOGLE,
                subject=profile.subject,
                user=user,
            )

            return user
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i


def link_account_sync(profile: GoogleProfile, user: ApiUser) -> ApiUser:
    # Vincular por correo solo es seguro si la cuenta existente ya probó que controla
    # ese correo. Si no, quien la creó (con una contraseña que solo él conoce) se
    # quedaría con la cuenta de quien después entre con Google.
    if user.verified_at is None:
        raise ForbiddenError(
            detail="Confirma tu correo antes de entrar con Google.",
        )

    try:
        with atomic():
            ApiExternalIdentity.objects.create(
                email=profile.email,
                provider=IdentityProviders.GOOGLE,
                subject=profile.subject,
                user=user,
            )
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i

    return user


def ensure_google_surface_sync(user: ApiUser, surface: str) -> None:
    role: str | None = role_of_sync(user)

    if surface == Surfaces.WEB.value and role in WEB_ROLES:
        return

    if surface == Surfaces.MOBILE.value and (
        role in PUBLIC_ROLES
        or ApiUser.objects.filter(
            pk=user.pk,
            provider_profile__isnull=False,
        ).exists()
    ):
        return

    raise ForbiddenError(detail=WRONG_SURFACE_DETAIL)


def resolve_account_sync(
    profile: GoogleProfile,
    data: GooglePost,
    surface: str,
) -> ApiUser:
    identity: ApiExternalIdentity | None = (
        ApiExternalIdentity.objects
        .select_related("user")
        .filter(provider=IdentityProviders.GOOGLE, subject=profile.subject)
        .first()
    )

    if identity is not None:
        user: ApiUser = identity.user  # ty: ignore[invalid-assignment]
        ensure_google_surface_sync(user, surface)
        return user

    existing: ApiUser | None = ApiUser.objects.filter(email=profile.email).first()

    if existing is not None:
        ensure_google_surface_sync(existing, surface)
        return link_account_sync(profile, existing)

    # El alta con Google existe solo en la app. En el portal primero se acepta una
    # invitación o se completa la postulación de la organización; Google únicamente
    # enlaza esa cuenta ya verificada.
    if surface == Surfaces.WEB.value:
        raise ForbiddenError(detail=WRONG_SURFACE_DETAIL)

    return create_account_sync(profile, data)


########################################################################################


@sensitive_variables()
def profile_from(data: GooglePost, surface: str) -> GoogleProfile:
    # uno de los dos tokens, y el de acceso solo desde el portal, que no crea cuentas
    one_token: bool = (data.id_token is None) != (data.access_token is None)
    access_from_app: bool = (
        data.access_token is not None and surface != Surfaces.WEB.value
    )

    if not one_token or access_from_app:
        raise BadRequestError(
            field_errors={"id_token": TOKEN_FIELD_DETAIL},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    if data.access_token is not None:
        return verify_access_token_sync(data.access_token)

    return verify_token_sync(str(data.id_token))


@sensitive_variables()
async def sign_in_with_google(data: GooglePost, surface: str) -> ApiUser:
    if not CONFIG.GOOGLE_OAUTH_CLIENT_IDS:
        raise NotFoundError(detail=DISABLED_DETAIL)

    profile: GoogleProfile = await sync_to_async(profile_from)(data, surface)

    user: ApiUser = await sync_to_async(resolve_account_sync)(profile, data, surface)

    ensure_can_operate(user)

    return user
