from http import HTTPStatus
from typing import TYPE_CHECKING, override

from .base import ApiError

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class ThrottleExceededError(ApiError):
    default_detail: Final[str] = (
        "Ha superado el límite de uso establecido para este recurso."
    )

    default_http_status: Final[HTTPStatus] = HTTPStatus.TOO_MANY_REQUESTS

    @override
    def __init__(
        self,
        detail: str | None = None,
        field_errors: dict[str, str] | None = None,
        http_status: HTTPStatus | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            detail=detail,
            field_errors=field_errors,
            http_status=http_status,
        )

        # `exc_handler` toma las cabeceras de la excepción y las pone en la respuesta
        self.headers: dict[str, str] | None = (
            {"Retry-After": str(retry_after)} if retry_after is not None else None
        )
