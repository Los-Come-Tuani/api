from http import HTTPStatus
from typing import TYPE_CHECKING, Final

from django.core.exceptions import BadRequest, TooManyFilesSent
from django.http.multipartparser import MultiPartParserError
from dmr.exceptions import DataParsingError
from dmr.negotiation import request_parser

from api_exceptions.enums import UnsupportedMediaErrorTypes

from .typed import TypedApiError

if TYPE_CHECKING:
    from typing import Self

    from dmr import Controller
    from dmr.exceptions import RequestSerializationError

########################################################################################


class UnsupportedMediaError(TypedApiError[UnsupportedMediaErrorTypes]):
    BODY_ERRORS: Final[tuple[type[Exception], ...]] = (
        BadRequest,
        DataParsingError,
        MultiPartParserError,
        TooManyFilesSent,
    )

    ENCODING_MARKER: Final[str] = "UTF-8"
    FILES_MARKER: Final[str] = "SupportsFileParsing"

    default_detail: Final[str] = "No se pudo interpretar la solicitud."

    default_http_status: Final[HTTPStatus] = HTTPStatus.UNSUPPORTED_MEDIA_TYPE

    @classmethod
    def from_serialization_error(
        cls,
        controller: Controller,
        exc: RequestSerializationError,
    ) -> Self:
        if isinstance(exc.__context__, cls.BODY_ERRORS):
            return cls(http_status=HTTPStatus.BAD_REQUEST)

        msg = str(exc)

        if cls.ENCODING_MARKER in msg:
            return cls(
                http_status=HTTPStatus.BAD_REQUEST,
                type=UnsupportedMediaErrorTypes.UNSUPPORTED_ENCODING,
            )

        if cls.FILES_MARKER in msg:
            return cls(type=UnsupportedMediaErrorTypes.UNSUPPORTED_FILES)

        if request_parser(controller.request) is None:
            return cls(type=UnsupportedMediaErrorTypes.UNSUPPORTED_MEDIA)

        return cls(http_status=HTTPStatus.BAD_REQUEST)
