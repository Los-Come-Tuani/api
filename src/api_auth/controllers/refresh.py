from http import HTTPStatus
from typing import override

from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from dmr import Body, CookieSpec, Cookies, ResponseSpec, modify, validate
from dmr.security.jwt.auth import set_request_attrs

from api_auth.enums import TokenTypes
from api_auth.schemas.refresh import (
    MobileRefreshPost,
    MobileRefreshResponse,
    WebRefreshPost,
)
from api_auth.services.cookies import build_cookied_response
from api_auth.services.jwt import JwtSession
from api_auth.services.session import rotate_session
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import MobileAuthController, WebAuthController

########################################################################################


class MobileRefreshController(MobileAuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    @sensitive_variables()
    async def post(self, parsed_body: Body[MobileRefreshPost]) -> MobileRefreshResponse:  # ruff: ignore[no-self-use]
        session: JwtSession = await rotate_session(**parsed_body.model_dump())

        return MobileRefreshResponse(
            access=session.tokens.access,
            refresh=session.tokens.refresh,
        )


########################################################################################


class WebRefreshController(WebAuthController[CustomPydanticFastSerializer]):
    @override
    @sensitive_variables()
    @validate(
        ResponseSpec(
            cookies={
                TokenTypes.ACCESS: CookieSpec(skip_validation=True),
                TokenTypes.REFRESH: CookieSpec(skip_validation=True),
            },
            return_type=None,
            status_code=HTTPStatus.NO_CONTENT,
        ),
        validate_responses=False,
    )
    async def post(self, parsed_cookies: Cookies[WebRefreshPost]) -> HttpResponse:
        await super().post()

        session: JwtSession = await rotate_session(**parsed_cookies.model_dump())

        set_request_attrs(self.request, session.user)

        return build_cookied_response(
            ctrl=self,
            status=HTTPStatus.NO_CONTENT,
            tokens=session.tokens,
        )
