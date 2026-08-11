from http import HTTPStatus
from typing import override

from django.views.decorators.debug import sensitive_variables
from dmr import Body, Cookies, modify

from api_auth.schemas.verify import MobileVerifyPost, WebVerifyPost, WebVerifyResponse
from api_auth.services.session import inspect_session, verify_jwt
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import MobileAuthController, WebAuthController

########################################################################################


class MobileVerifyController(MobileAuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[MobileVerifyPost]) -> None:  # ruff: ignore[no-self-use]
        await verify_jwt(
            encoded=parsed_body.token,
            expected_type=parsed_body.type,
        )


########################################################################################


class WebVerifyController(WebAuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    @override
    @sensitive_variables()
    async def post(self, parsed_cookies: Cookies[WebVerifyPost]) -> WebVerifyResponse:
        await super().post()

        access, refresh = await inspect_session(**parsed_cookies.model_dump())

        return WebVerifyResponse(access=access, refresh=refresh)
