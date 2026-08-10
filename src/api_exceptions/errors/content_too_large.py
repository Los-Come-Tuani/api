from http import HTTPStatus
from typing import TYPE_CHECKING, Final

from django.core.exceptions import TooManyFieldsSent, TooManyFilesSent
from dmr.exceptions import RequestSerializationError

from api_exceptions.enums import ContentTooLargeErrorTypes
from api_exceptions.types import UploadLimitError

from .typed import TypedApiError

if TYPE_CHECKING:
    from typing import Self

########################################################################################


class ContentTooLargeError(TypedApiError[ContentTooLargeErrorTypes]):
    default_detail: Final[str] = "La solicitud excede los límites permitidos."

    default_http_status: Final[HTTPStatus] = HTTPStatus.CONTENT_TOO_LARGE

    @classmethod
    def from_upload_error(cls, exc: UploadLimitError) -> Self:
        if isinstance(exc, TooManyFieldsSent):
            return cls(type=ContentTooLargeErrorTypes.FIELDS)
        if isinstance(exc, TooManyFilesSent):
            return cls(type=ContentTooLargeErrorTypes.FILES)

        return cls(type=ContentTooLargeErrorTypes.BODY)

    @classmethod
    def unwrap(cls, exc: Exception) -> Self | None:
        if isinstance(exc, UploadLimitError):
            return cls.from_upload_error(exc)

        if isinstance(exc, RequestSerializationError) and isinstance(
            exc.__context__,
            UploadLimitError,
        ):
            return cls.from_upload_error(exc.__context__)

        return None
