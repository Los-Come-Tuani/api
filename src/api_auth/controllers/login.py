from http import HTTPStatus
from typing import override

from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from dmr import Body, CookieSpec, ResponseSpec, modify, validate

from api_auth.enums import TokenTypes
from api_auth.models import ApiUser
from api_auth.schemas.login import (
    MobileLoginPost,
    MobileLoginResponse,
    WebLoginPost,
    WebLoginResponse,
)
from api_auth.schemas.user import ApiUserInlineGet
from api_auth.services.cookies import build_cookied_response
from api_auth.services.jwt import EncodedJwtPair, build_jwt_pair
from api_auth.services.user import authenticate_user
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.services.mappers import instance_mapper

from .base import MobileAuthController, WebAuthController

########################################################################################


class MobileLoginController(MobileAuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    @sensitive_variables()
    async def post(self, parsed_body: Body[MobileLoginPost]) -> MobileLoginResponse:
        user: ApiUser = await authenticate_user(parsed_body, self.request)

        tokens: EncodedJwtPair = build_jwt_pair(user)

        return MobileLoginResponse(
            access=tokens.access,
            refresh=tokens.refresh,
            user=instance_mapper(user, ApiUserInlineGet),
        )


########################################################################################


class WebLoginController(WebAuthController[CustomPydanticFastSerializer]):
    @override
    @sensitive_variables()
    @validate(
        ResponseSpec(
            cookies={
                TokenTypes.ACCESS: CookieSpec(skip_validation=True),
                TokenTypes.REFRESH: CookieSpec(skip_validation=True),
            },
            return_type=WebLoginResponse,
            status_code=HTTPStatus.OK,
        ),
        validate_responses=False,
    )
    async def post(self, parsed_body: Body[WebLoginPost]) -> HttpResponse:
        await super().post()

        user: ApiUser = await authenticate_user(parsed_body, self.request)

        return build_cookied_response(
            ctrl=self,
            data=WebLoginResponse(user=instance_mapper(user, ApiUserInlineGet)),
            tokens=build_jwt_pair(user),
        )
