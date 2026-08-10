from http import HTTPStatus
from typing import TYPE_CHECKING

from .base import ApiError

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class UnauthorizedError(ApiError):
    default_detail: Final[str] = (
        "No se proporcionaron credenciales de autenticación válidas."
    )

    default_http_status: Final[HTTPStatus] = HTTPStatus.UNAUTHORIZED
