from http import HTTPStatus
from typing import TYPE_CHECKING

from dmr.negotiation import request_renderer
from dmr.response import build_response

from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_exceptions.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from api_exceptions.schemas import ApiErrorResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest, HttpResponse
    from dmr.serializer import BaseSerializer

########################################################################################


def build_4xx_handler(
    http_code: HTTPStatus,
    serializer: type[BaseSerializer] = CustomPydanticFastSerializer,
) -> Callable[[HttpRequest, Exception, str], HttpResponse]:
    def factory(
        request: HttpRequest,
        exception: Exception,  # ruff: ignore[unused-function-argument]
        template_name: str = "",  # ruff: ignore[unused-function-argument]
    ) -> HttpResponse:
        match http_code:
            case NotFoundError.default_http_status:
                model = ApiErrorResponse.from_exc(NotFoundError)
            case ForbiddenError.default_http_status:
                model = ApiErrorResponse.from_exc(ForbiddenError)
            case UnauthorizedError.default_http_status:
                model = ApiErrorResponse.from_exc(UnauthorizedError)
            case _:
                model = ApiErrorResponse.from_exc(BadRequestError)

        return build_response(
            raw_data=model.model_construct(),
            renderer=request_renderer(request),
            serializer=serializer,
            status_code=http_code,
        )

    return factory


########################################################################################


def build_500_handler(
    serializer: type[BaseSerializer] = CustomPydanticFastSerializer,
) -> Callable[[HttpRequest, str], HttpResponse]:
    def factory(
        request: HttpRequest,
        template_name: str = "",  # ruff: ignore[unused-function-argument]
    ) -> HttpResponse:
        return build_response(
            raw_data=ApiErrorResponse.model_construct(),
            renderer=request_renderer(request),
            serializer=serializer,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    return factory
