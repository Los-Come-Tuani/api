from http import HTTPStatus
from typing import override

from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from dmr import Body, Cookies, ResponseSpec, modify, validate

from api_auth.schemas.logout import MobileLogoutPost, WebLogoutPost
from api_auth.services.cookies import build_cookieless_response
from api_auth.services.session import close_session
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import MobileAuthController, WebAuthController

########################################################################################


class MobileLogoutController(MobileAuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[MobileLogoutPost]) -> None:  # ruff: ignore[no-self-use]
        await close_session(**parsed_body.model_dump())


########################################################################################


class WebLogoutController(WebAuthController[CustomPydanticFastSerializer]):
    @override
    @sensitive_variables()
    @validate(
        ResponseSpec(return_type=None, status_code=HTTPStatus.NO_CONTENT),
        validate_responses=False,
    )
    async def post(self, parsed_cookies: Cookies[WebLogoutPost]) -> HttpResponse:
        await super().post()

        await close_session(**parsed_cookies.model_dump())

        return build_cookieless_response(self.request)
