from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async
from django.db.models import Max
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.models import ApiLoginAttempt, ApiLoginLock
from api_core.config import CONFIG
from api_core.controllers.throttles import ForwardedAddr
from api_exceptions.errors import ThrottleExceededError

if TYPE_CHECKING:
    from typing import Final

    from django.http import HttpRequest

########################################################################################

LOCKED_DETAIL: Final[str] = (
    "Se bloqueó el acceso por demasiados intentos fallidos. "
    "Intenta de nuevo en unos minutos."
)

EPOCH: Final[datetime] = datetime.fromtimestamp(0, tz=UTC)

MAX_IDENTIFIER_LENGTH: Final[int] = 254

########################################################################################


def build_key(identifier: str) -> str:
    # con esta forma se cuentan los intentos: `Ana@x.com ` y `ana@x.com` suman juntos
    return identifier.strip().lower()[:MAX_IDENTIFIER_LENGTH]


def client_address(request: HttpRequest) -> str | None:
    return ForwardedAddr.resolve_addr(request)


########################################################################################


def ensure_unlocked_sync(key: str) -> None:
    lock: Any = ApiLoginLock.objects.filter(key=key).first()

    if lock is None or lock.locked_until <= now():
        return

    remaining: int = max(1, int((lock.locked_until - now()).total_seconds()))

    raise ThrottleExceededError(detail=LOCKED_DETAIL, retry_after=remaining)


def record_sync(
    *,
    identifier: str,
    key: str,
    request_address: str | None,
    succeeded: bool,
) -> None:
    with atomic():
        ApiLoginAttempt.objects.create(
            identifier=identifier[:MAX_IDENTIFIER_LENGTH],
            ip_address=request_address,
            key=key,
            succeeded=succeeded,
        )

        if succeeded:
            ApiLoginLock.objects.filter(key=key).delete()

            return

        lock: Any = ApiLoginLock.objects.filter(key=key).first()

        # los fallos se cuentan desde el último acierto, desde que venció el bloqueo
        # anterior y, en todo caso, solo dentro de la ventana del bloqueo
        last_success: datetime | None = ApiLoginAttempt.objects.filter(
            key=key,
            succeeded=True,
        ).aggregate(latest=Max("created_at"))["latest"]

        since: datetime = max(
            now() - CONFIG.LOGIN_LOCKOUT,
            last_success or EPOCH,
            lock.locked_until if lock is not None else EPOCH,
        )

        failures: int = ApiLoginAttempt.objects.filter(
            created_at__gt=since,
            key=key,
            succeeded=False,
        ).count()

        if failures < CONFIG.LOGIN_MAX_FAILURES:
            return

        ApiLoginLock.objects.update_or_create(
            key=key,
            defaults={"locked_until": now() + CONFIG.LOGIN_LOCKOUT},
        )


########################################################################################


async def ensure_unlocked(identifier: str) -> None:
    # lanza 429 si el identificador está bloqueado, exista o no la cuenta
    await sync_to_async(ensure_unlocked_sync)(build_key(identifier))


async def record_attempt(
    *,
    identifier: str,
    request: HttpRequest,
    succeeded: bool,
) -> None:
    await sync_to_async(record_sync)(
        identifier=identifier,
        key=build_key(identifier),
        request_address=client_address(request),
        succeeded=succeeded,
    )
