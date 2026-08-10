from typing import TYPE_CHECKING

from dmr.exceptions import (
    NotAcceptableError,
    NotAuthenticatedError,
    RequestSerializationError,
    TooManyRequestsError,
)

from .errors import (
    ApiError,
    BadRequestError,
    ConflictError,
    ContentTooLargeError,
    ThrottleExceededError,
    UnacceptableHeaderError,
    UnauthorizedError,
    UnsupportedMediaError,
)
from .schemas import ApiErrorResponse
from .types import GenericConflictError, GenericValidationError

if TYPE_CHECKING:
    from django.http import HttpResponse
    from dmr import Controller
    from dmr.endpoint import Endpoint

########################################################################################


def exc_handler(
    endpoint: Endpoint,  # ruff: ignore[unused-function-argument]
    controller: Controller,
    exc: Exception,
) -> HttpResponse:
    parsed = None

    if isinstance(exc, ApiError):
        parsed = exc
    elif isinstance(exc, NotAcceptableError):
        parsed = UnacceptableHeaderError()
    elif isinstance(exc, NotAuthenticatedError):
        parsed = UnauthorizedError()
    elif oversized := ContentTooLargeError.unwrap(exc):
        parsed = oversized
    elif isinstance(exc, RequestSerializationError):
        parsed = UnsupportedMediaError.from_serialization_error(controller, exc)
    elif isinstance(exc, TooManyRequestsError):
        parsed = ThrottleExceededError()
    elif isinstance(exc, GenericConflictError):
        parsed = ConflictError.from_integrity_error(exc)
    elif isinstance(exc, GenericValidationError):
        parsed = BadRequestError.from_validation_error(exc)

    if parsed is not None:
        return controller.to_error(
            cookies=getattr(exc, "cookies", None),
            headers=getattr(exc, "headers", None),
            raw_data=(
                ApiErrorResponse
                .from_exc(type(parsed))
                .model_validate(obj=parsed)
                .model_dump()
            ),
            renderer=getattr(exc, "renderer", None),
            status_code=parsed.default_http_status,
        )

    raise exc
