from typing import override

from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from dmr import Body, validate
from dmr.security.jwt.auth import set_request_attrs

from api_auth.enums import Surfaces
from api_auth.models import ApiUser
from api_auth.schemas.google import GooglePost
from api_auth.services.google import sign_in_with_google
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import MobileAuthController, WebAuthController
from .login import (
    MOBILE_SESSION_RESPONSES,
    WEB_SESSION_RESPONSES,
    mobile_session_response,
    web_session_response,
)

########################################################################################


class MobileGoogleController(MobileAuthController[CustomPydanticFastSerializer]):
    @sensitive_variables()
    @validate(*MOBILE_SESSION_RESPONSES, validate_responses=False)
    async def post(self, parsed_body: Body[GooglePost]) -> HttpResponse:
        user: ApiUser = await sign_in_with_google(parsed_body, Surfaces.MOBILE)

        set_request_attrs(self.request, user)

        return await mobile_session_response(self, user)


########################################################################################


class WebGoogleController(WebAuthController[CustomPydanticFastSerializer]):
    @override
    @sensitive_variables()
    @validate(*WEB_SESSION_RESPONSES, validate_responses=False)
    async def post(self, parsed_body: Body[GooglePost]) -> HttpResponse:
        await super().post()

        user: ApiUser = await sign_in_with_google(parsed_body, Surfaces.WEB)

        set_request_attrs(self.request, user)

        return await web_session_response(self, user)
