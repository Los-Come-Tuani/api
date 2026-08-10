from http import HTTPStatus
from typing import TYPE_CHECKING

from .base import ApiError

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class ThrottleExceededError(ApiError):
    default_detail: Final[str] = (
        "Ha superado el límite de uso establecido para este recurso."
    )

    default_http_status: Final[HTTPStatus] = HTTPStatus.TOO_MANY_REQUESTS
