from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

import jwt

from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db.transaction import atomic
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables
from jwt import PyJWKClient, PyJWKClientConnectionError, PyJWTError

from api_auth.enums import ApiUserTypes, IdentityProviders
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
from .session_user import PUBLIC_ROLES, resolve_role

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

# - tolerancia al desfase de reloj entre Google y este servidor
CLOCK_LEEWAY_SECONDS: Final[int] = 10

DISABLED_DETAIL: Final[str] = "El inicio de sesión con Google no está habilitado."
INVALID_TOKEN_DETAIL: Final[str] = "El token de Google no es válido."  # ruff: ignore[hardcoded-password-string]
UNVERIFIED_DETAIL: Final[str] = "Google no ha verificado el correo de esta cuenta."

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
        raise ApiError(
            detail="No se pudo validar con Google. Intenta de nuevo en un momento.",
        ) from c
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


def resolve_account_sync(profile: GoogleProfile, data: GooglePost) -> ApiUser:
    identity: ApiExternalIdentity | None = (
        ApiExternalIdentity.objects
        .select_related("user")
        .filter(provider=IdentityProviders.GOOGLE, subject=profile.subject)
        .first()
    )

    if identity is not None:
        return identity.user  # ty: ignore[invalid-return-type]

    existing: ApiUser | None = ApiUser.objects.filter(email=profile.email).first()

    if existing is not None:
        return link_account_sync(profile, existing)

    return create_account_sync(profile, data)


def ensure_public_role_sync(user: ApiUser) -> None:
    # Google es para turistas, guías y traductores. El equipo y las organizaciones
    # entran con correo, contraseña y segundo factor.
    if resolve_role(user, list(user.groups.all())) in PUBLIC_ROLES:  # ty: ignore[unresolved-attribute]
        return

    raise ForbiddenError(
        detail="Esta cuenta debe iniciar sesión con su correo y su contraseña.",
    )


########################################################################################


@sensitive_variables()
async def sign_in_with_google(data: GooglePost) -> ApiUser:
    if not CONFIG.GOOGLE_OAUTH_CLIENT_IDS:
        raise NotFoundError(detail=DISABLED_DETAIL)

    profile: GoogleProfile = await sync_to_async(verify_token_sync)(data.id_token)

    user: ApiUser = await sync_to_async(resolve_account_sync)(profile, data)

    await sync_to_async(ensure_public_role_sync)(user)

    ensure_can_operate(user)

    return user
