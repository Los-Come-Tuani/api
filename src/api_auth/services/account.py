from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.transaction import atomic
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables

from api_auth.enums import ApiUserStatus, ApiUserTypes, VerificationPurposes
from api_auth.models import ApiUser
from api_core.config import CONFIG
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)

from .login_guard import ensure_unlocked, record_attempt
from .mail import (
    send_closing_notice,
    send_password_reset_code,
    send_verification_code,
)
from .verification import check_code_sync, issue_code

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Final

    from django.http import HttpRequest

    from api_auth.schemas.account import ProfilePatch, RegisterPost

########################################################################################

INVALID_CODE_DETAIL: Final[str] = "El código no es válido o ya venció."

INVALID_PASSWORD_DETAIL: Final[str] = "La contraseña actual no es válida."  # ruff: ignore[hardcoded-password-string]

# - por qué una cuenta con la contraseña correcta, aun así, no entra (RF-S-10)
STATUS_DETAILS: Final[dict[str, str]] = {
    ApiUserStatus.CLOSING: (
        "Tu cuenta está en proceso de baja. Puedes reactivarla antes de que "
        "termine el plazo."
    ),
    ApiUserStatus.EXPELLED: "Tu cuenta fue expulsada de K'Plan.",
    ApiUserStatus.PENDING: (
        "Tu cuenta todavía no está activa. Confirma tu correo para poder entrar."
    ),
    ApiUserStatus.SUSPENDED: "Tu cuenta está suspendida temporalmente.",
}

# - estados que cortan de inmediato las sesiones abiertas (RF-S-07, RF-S-10)
SESSION_REVOKING: Final[frozenset[str]] = frozenset({
    ApiUserStatus.CLOSING,
    ApiUserStatus.EXPELLED,
    ApiUserStatus.SUSPENDED,
})

########################################################################################


def ensure_can_operate(user: ApiUser) -> None:
    if user.status == ApiUserStatus.ACTIVE:
        return

    raise ForbiddenError(
        detail=STATUS_DETAILS.get(user.status, "Tu cuenta no puede operar."),
    )


@sensitive_variables()
def ensure_strong_password(
    password: str,
    *,
    field: str = "password",
    user: ApiUser | None = None,
) -> None:
    try:
        validate_password(password=password, user=user)
    except DjangoValidationError as v:
        errs: str = (
            "; ".join(msg.replace(".", ",").removesuffix(",") for msg in v)
        ).removesuffix(";").capitalize() + "."

        raise BadRequestError(
            field_errors={field: errs},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY) from v


def invalid_code_error() -> BadRequestError:
    return BadRequestError(
        field_errors={"code": INVALID_CODE_DETAIL},
        type=BadRequestErrorTypes.FAILED_VALIDATION,
    ).scoped(RequestScopes.BODY)


########################################################################################
# Estado y sesiones


def change_status_sync(
    user: ApiUser,
    status: ApiUserStatus,
    *,
    closing_effective_at: datetime | None = None,
) -> None:
    # Único camino para cambiar el estado de una cuenta: `is_active` se mantiene
    # alineado (la base lo exige) y los estados que cortan la sesión revocan las
    # credenciales ya emitidas.
    changes: dict[str, object] = {
        "closing_effective_at": (
            closing_effective_at if status == ApiUserStatus.CLOSING else None
        ),
        "is_active": status == ApiUserStatus.ACTIVE,
        "status": status,
    }

    if status in SESSION_REVOKING:
        changes["sessions_revoked_at"] = now()

    ApiUser.objects.filter(pk=user.pk).update(**changes)

    user.refresh_from_db(fields=list(changes))


async def change_status(
    user: ApiUser,
    status: ApiUserStatus,
    *,
    closing_effective_at: datetime | None = None,
) -> None:
    await sync_to_async(change_status_sync)(
        user,
        status,
        closing_effective_at=closing_effective_at,
    )


async def revoke_sessions(user: ApiUser) -> None:
    # invalida toda credencial emitida hasta este instante, en todos los dispositivos
    await ApiUser.objects.filter(pk=user.pk).aupdate(sessions_revoked_at=now())

    await user.arefresh_from_db(fields=["sessions_revoked_at"])


########################################################################################
# Registro


async def request_registration_code(email: str) -> None:
    # manda el código de alta; responde igual exista o no la cuenta (RF-S-06)
    if await ApiUser.objects.filter(email=email).aexists():
        return

    code: str | None = await issue_code(
        destination=email,
        purpose=VerificationPurposes.EMAIL,
    )

    if code is not None:
        await send_verification_code(code=code, to=email)


def register_sync(data: RegisterPost) -> ApiUser:
    # primero se comprueba aparte: un código equivocado suma un intento, y ese intento
    # tiene que quedar guardado aunque la petición termine en error
    if not check_code_sync(
        code=data.code,
        consume=False,
        destination=data.email,
        purpose=VerificationPurposes.EMAIL,
    ):
        raise invalid_code_error()

    try:
        with atomic():
            # el código se gasta en la misma transacción que crea la cuenta: si algo
            # falla después, vuelve a servir
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
                username=data.username,
            )

            user.groups.add(Group.objects.get(name=ApiUserTypes.CLIENT))  # ty: ignore[unresolved-attribute]

            return user
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i


@sensitive_variables()
async def register_account(data: RegisterPost) -> ApiUser:
    # primero la contraseña, para no gastar el código de quien la eligió mal
    await sync_to_async(ensure_strong_password)(
        data.password,
        user=ApiUser(
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            username=data.username,
        ),
    )

    return await sync_to_async(register_sync)(data)


########################################################################################
# Contraseña


async def request_password_reset(email: str) -> None:
    # manda el código de recuperación; responde igual exista o no la cuenta
    user: ApiUser | None = await ApiUser.objects.filter(
        email=email,
        status=ApiUserStatus.ACTIVE,
    ).afirst()

    if user is None:
        return

    code: str | None = await issue_code(
        destination=email,
        purpose=VerificationPurposes.PASSWORD_RESET,
        user=user,
    )

    if code is not None:
        await send_password_reset_code(code=code, to=email)


@sensitive_variables()
def reset_password_sync(*, code: str, email: str, password: str) -> None:
    user: ApiUser | None = ApiUser.objects.filter(
        email=email,
        status=ApiUserStatus.ACTIVE,
    ).first()

    # una cuenta que no puede recuperarse y un código incorrecto dan el mismo error; la
    # comprobación va aparte para que el intento fallido quede guardado
    if user is None or not check_code_sync(
        code=code,
        consume=False,
        destination=email,
        purpose=VerificationPurposes.PASSWORD_RESET,
    ):
        raise invalid_code_error()

    ensure_strong_password(password, user=user)

    with atomic():
        if not check_code_sync(
            code=code,
            consume=True,
            destination=email,
            purpose=VerificationPurposes.PASSWORD_RESET,
        ):
            raise invalid_code_error()

        user.set_password(password)
        user.sessions_revoked_at = now()
        user.save(update_fields=["password", "sessions_revoked_at"])


@sensitive_variables()
async def reset_password(*, code: str, email: str, password: str) -> None:
    await sync_to_async(reset_password_sync)(code=code, email=email, password=password)


@sensitive_variables()
def change_password_sync(*, current: str, new: str, user: ApiUser) -> None:
    if not user.check_password(current):
        raise BadRequestError(
            field_errors={"current_password": INVALID_PASSWORD_DETAIL},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    ensure_strong_password(new, user=user)

    user.set_password(new)
    # cambiar la contraseña cierra las sesiones, incluida esta: hay que volver a entrar
    user.sessions_revoked_at = now()
    user.save(update_fields=["password", "sessions_revoked_at"])


@sensitive_variables()
async def change_password(*, current: str, new: str, user: ApiUser) -> None:
    await sync_to_async(change_password_sync)(current=current, new=new, user=user)


########################################################################################
# Perfil


async def update_profile(user: ApiUser, patch: ProfilePatch) -> ApiUser:
    changes: dict[str, object] = patch.model_dump(exclude_unset=True)

    if not changes:
        return user

    try:
        await ApiUser.objects.filter(pk=user.pk).aupdate(**changes)
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i

    await user.arefresh_from_db(fields=list(changes))

    return user


########################################################################################
# Baja de la cuenta


@sensitive_variables()
async def close_account(*, password: str, user: ApiUser) -> datetime:
    # pide la baja: la cuenta queda inactiva y se destruye pasado el plazo (RF-S-11)
    if not await sync_to_async(user.check_password)(password):
        raise BadRequestError(
            field_errors={"password": INVALID_PASSWORD_DETAIL},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    effective: datetime = now() + CONFIG.ACCOUNT_CLOSING_DELAY

    await change_status(
        user,
        ApiUserStatus.CLOSING,
        closing_effective_at=effective,
    )

    await send_closing_notice(
        days=CONFIG.ACCOUNT_CLOSING_DELAY.days,
        to=str(user.email),
    )

    return effective


@sensitive_variables()
async def restore_account(*, email: str, password: str, request: HttpRequest) -> None:
    # Cancela una baja pendiente; cualquier otro caso responde como credenciales malas.
    # Cuenta para el bloqueo por intentos, igual que el inicio de sesión.
    await ensure_unlocked(email)

    user: ApiUser | None = await ApiUser.objects.filter(
        closing_effective_at__gt=now(),
        email=ApiUser.objects.normalize_email(email),
        status=ApiUserStatus.CLOSING,
    ).afirst()

    valid: bool = user is not None and await sync_to_async(user.check_password)(
        password
    )

    await record_attempt(identifier=email, request=request, succeeded=valid)

    if user is None or not valid:
        raise UnauthorizedError(
            detail="Las credenciales proporcionadas no son válidas.",
        )

    await change_status(user, ApiUserStatus.ACTIVE)
