from collections.abc import Sequence
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar, override

from django.db.models.query import QuerySet
from django.http import HttpResponse
from dmr import Controller
from dmr.negotiation import request_renderer
from dmr.response import build_response
from dmr.security import AsyncAuth
from dmr.throttling import AsyncThrottle, Rate

from api_exceptions.schemas import ApiErrorResponse

from .providers import HandleNotAllowedProvider, QuerySetProvider
from .throttles import build_throttle

########################################################################################


class DefaultOrderMixin(QuerySetProvider):
    @override
    def build_qs(self) -> QuerySet:
        return super().build_qs().order_by("pk")


########################################################################################


class HandleNotAllowedMixin(HandleNotAllowedProvider):
    @override
    def handle_method_not_allowed(self, method: str) -> HttpResponse:
        if TYPE_CHECKING:
            # gracias convenciones de python por:
            assert isinstance(self, Controller)

        allowed = ", ".join(sorted(self.api_endpoints.keys()))

        return self._maybe_wrap(
            build_response(
                headers={"Allow": allowed},
                raw_data=ApiErrorResponse(
                    detail=f"Este controlador no procesa peticiones {method}.",
                    field_errors={"method": f"Métodos permitidos: {allowed}."},
                ),
                renderer=request_renderer(self.request),
                serializer=self.serializer,
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
            )
        )


########################################################################################


class PublicEndpointMixin:
    auth: ClassVar[Sequence[AsyncAuth] | None] = None


########################################################################################


class StrictThrottlingMixin:
    throttling: ClassVar[Sequence[AsyncThrottle]] = (build_throttle(10, Rate.minute),)
