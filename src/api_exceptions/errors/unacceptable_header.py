from http import HTTPStatus
from typing import TYPE_CHECKING

from .base import ApiError

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class UnacceptableHeaderError(ApiError):
    default_detail: Final[str] = "Ha enviado un `Accept` header inválido."

    default_http_status: Final[HTTPStatus] = HTTPStatus.NOT_ACCEPTABLE
