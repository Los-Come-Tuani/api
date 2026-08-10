from http import HTTPStatus
from typing import TYPE_CHECKING

from .base import ApiError

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class ForbiddenError(ApiError):
    default_detail: Final[str] = "No tiene permiso para realizar esta acción."

    default_http_status: Final[HTTPStatus] = HTTPStatus.FORBIDDEN
