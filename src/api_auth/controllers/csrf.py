from http import HTTPStatus

from django.http import HttpResponse
from dmr import HeaderSpec, ResponseSpec, validate
from dmr.negotiation import request_renderer
from dmr.response import build_response

from api_auth.services.csrf import attach_csrf
from api_core.config import CONFIG
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import AuthController

########################################################################################


class CsrfController(AuthController[CustomPydanticFastSerializer]):
    @validate(
        ResponseSpec(
            headers={CONFIG.csrf_header: HeaderSpec(skip_validation=True)},
            return_type=None,
            status_code=HTTPStatus.NO_CONTENT,
        ),
        validate_responses=False,
    )
    async def get(self) -> HttpResponse:
        return attach_csrf(
            response=build_response(
                raw_data=None,
                renderer=request_renderer(self.request),
                serializer=CustomPydanticFastSerializer,
                status_code=HTTPStatus.NO_CONTENT,
            ),
            request=self.request,
        )
