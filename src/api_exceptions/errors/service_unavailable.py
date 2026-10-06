from http import HTTPStatus
from typing import TYPE_CHECKING

from .base import ApiError

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class ServiceUnavailableError(ApiError):
    default_detail: Final[str] = "El servicio no está disponible por ahora."

    default_http_status: Final[HTTPStatus] = HTTPStatus.SERVICE_UNAVAILABLE
