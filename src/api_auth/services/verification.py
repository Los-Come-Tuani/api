from hashlib import sha256
from hmac import (
    compare_digest,
    new as build_hmac,
)
from secrets import randbelow
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db.models import F
from django.db.transaction import atomic
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables

from api_auth.enums import VerificationPurposes
from api_auth.models import ApiVerificationCode
from api_core.config import CONFIG

if TYPE_CHECKING:
    from typing import Final

    from api_auth.models import ApiUser

########################################################################################

CODE_DIGITS: Final[int] = 6

########################################################################################


def generate_code() -> str:
    return f"{randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


@sensitive_variables()
def hash_code(purpose: str, destination: str, code: str) -> str:
    # el código solo sirve para su propósito y su destino; sin la llave no se puede
    # reconstruir el hash aunque se conozca el código de seis dígitos
    return build_hmac(
        CONFIG.SECRET_KEY.get_secret_value().encode(),
        f"{purpose}:{destination}:{code}".encode(),
        sha256,
    ).hexdigest()


def signup_code_reaches_people() -> bool:
    # Desplegado sin proveedor de correo, el API descarta los correos: el código de alta
    # nunca llega y el alta (registro y postulaciones) no lo pide. En desarrollo sale
    # por consola.
    return bool(CONFIG.EMAIL_HOST) or not CONFIG.DEPLOY


def accepts_any_code(purpose: VerificationPurposes) -> bool:
    # nunca para recuperar una contraseña ni aceptar una invitación: eso abriría
    # cuentas que ya existen, no solo crearía una nueva; y con un proveedor de correo
    # el código sí llega
    return (
        CONFIG.VERIFICATION_ACCEPT_ANY_SIGNUP_CODE
        and not CONFIG.EMAIL_HOST
        and purpose == VerificationPurposes.EMAIL
    )


########################################################################################


@sensitive_variables()
def issue_code_sync(
    *,
    destination: str,
    purpose: VerificationPurposes,
    user: ApiUser | None = None,
) -> str | None:
    # un solo código vigente por destino y propósito; y no se manda otro hasta que
    # pase el tiempo de espera, para que el endpoint no sirva de bombardeo de correos
    with atomic():
        latest: ApiVerificationCode | None = (
            ApiVerificationCode.objects
            .select_for_update()
            .filter(destination=destination, purpose=purpose)
            .order_by("-created_at")
            .first()
        )

        if (
            latest is not None
            and latest.created_at > now() - CONFIG.VERIFICATION_RESEND_AFTER
        ):
            return None

        ApiVerificationCode.objects.filter(
            consumed_at__isnull=True,
            destination=destination,
            purpose=purpose,
        ).update(consumed_at=now())

        code: str = generate_code()

        ApiVerificationCode.objects.create(
            code_hash=hash_code(purpose, destination, code),
            destination=destination,
            expires_at=now() + CONFIG.VERIFICATION_LIFETIME,
            purpose=purpose,
            user=user,
        )

        return code


@sensitive_variables()
def check_code_sync(
    *,
    code: str,
    consume: bool,
    destination: str,
    purpose: VerificationPurposes,
) -> bool:
    # solo el alta: recuperar una contraseña o aceptar una invitación abre una cuenta
    # que ya existe y siempre pide el código real
    if purpose == VerificationPurposes.EMAIL and not signup_code_reaches_people():
        return True

    with atomic():
        row: ApiVerificationCode | None = (
            ApiVerificationCode.objects
            .select_for_update()
            .filter(
                consumed_at__isnull=True,
                destination=destination,
                expires_at__gt=now(),
                purpose=purpose,
            )
            .order_by("-created_at")
            .first()
        )

        if row is None or row.attempts >= CONFIG.VERIFICATION_MAX_ATTEMPTS:
            return False

        expected: str = hash_code(purpose, destination, code)

        if not compare_digest(str(row.code_hash), expected) and not accepts_any_code(
            purpose,
        ):
            ApiVerificationCode.objects.filter(pk=row.pk).update(
                attempts=F("attempts") + 1,
            )

            return False

        if consume:
            ApiVerificationCode.objects.filter(pk=row.pk).update(consumed_at=now())

        return True


########################################################################################


@sensitive_variables()
async def issue_code(
    *,
    destination: str,
    purpose: VerificationPurposes,
    user: ApiUser | None = None,
) -> str | None:
    # el código nuevo, o `None` si hay que esperar para pedir otro
    return await sync_to_async(issue_code_sync)(
        destination=destination,
        purpose=purpose,
        user=user,
    )


@sensitive_variables()
async def check_code(
    *,
    code: str,
    consume: bool = False,
    destination: str,
    purpose: VerificationPurposes,
) -> bool:
    # dice si `code` es el vigente para ese destino; con `consume`, lo gasta
    return await sync_to_async(check_code_sync)(
        code=code,
        consume=consume,
        destination=destination,
        purpose=purpose,
    )
