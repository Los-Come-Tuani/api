from http import HTTPStatus
from typing import override

from django.http import HttpResponse
from django.views.decorators.debug import sensitive_variables
from dmr import Body, CookieSpec, ResponseSpec, validate

from api_auth.enums import Surfaces, TokenTypes
from api_auth.models import ApiUser
from api_auth.schemas.login import (
    MobileLoginPost,
    MobileLoginResponse,
    WebLoginPost,
    WebLoginResponse,
)
from api_auth.schemas.two_factor import MobileChallengeResponse, WebChallengeResponse
from api_auth.services.cookies import build_challenged_response, build_cookied_response
from api_auth.services.jwt import EncodedJwtPair
from api_auth.services.session import open_session
from api_auth.services.session_user import build_session_user
from api_auth.services.user import authenticate_user
from api_core.config import CONFIG
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import MobileAuthController, WebAuthController

########################################################################################

# - la respuesta de iniciar sesión (200 con la sesión, 202 si falta el segundo factor)
#   es la misma con contraseña, con Google o al terminar el 2FA; vive aquí para no
#   repetirla en cada controlador

MOBILE_SESSION_RESPONSES = (
    ResponseSpec(return_type=MobileLoginResponse, status_code=HTTPStatus.OK),
    ResponseSpec(
        return_type=MobileChallengeResponse,
        status_code=HTTPStatus.ACCEPTED,
    ),
)

WEB_SESSION_RESPONSES = (
    ResponseSpec(
        cookies={
            TokenTypes.ACCESS: CookieSpec(skip_validation=True),
            TokenTypes.REFRESH: CookieSpec(skip_validation=True),
        },
        return_type=WebLoginResponse,
        status_code=HTTPStatus.OK,
    ),
    ResponseSpec(
        cookies={TokenTypes.CHALLENGE: CookieSpec(skip_validation=True)},
        return_type=WebChallengeResponse,
        status_code=HTTPStatus.ACCEPTED,
    ),
)


async def mobile_session_response(
    ctrl: MobileAuthController[CustomPydanticFastSerializer],
    user: ApiUser,
) -> HttpResponse:
    session: EncodedJwtPair | str = await open_session(user)

    if isinstance(session, EncodedJwtPair):
        return ctrl.to_response(
            raw_data=MobileLoginResponse(
                access=session.access,
                refresh=session.refresh,
                user=await build_session_user(user),
            ),
            status_code=HTTPStatus.OK,
        )

    return ctrl.to_response(
        raw_data=MobileChallengeResponse(
            challenge=session,
            expires_in=int(CONFIG.JWT_CHALLENGE_LIFETIME.total_seconds()),
        ),
        status_code=HTTPStatus.ACCEPTED,
    )


async def web_session_response(
    ctrl: WebAuthController[CustomPydanticFastSerializer],
    user: ApiUser,
) -> HttpResponse:
    session: EncodedJwtPair | str = await open_session(user)

    if isinstance(session, EncodedJwtPair):
        return build_cookied_response(
            ctrl=ctrl,
            data=WebLoginResponse(user=await build_session_user(user)),
            tokens=session,
        )

    return build_challenged_response(
        challenge=session,
        ctrl=ctrl,
        data=WebChallengeResponse(
            expires_in=int(CONFIG.JWT_CHALLENGE_LIFETIME.total_seconds()),
        ),
    )


########################################################################################


class MobileLoginController(MobileAuthController[CustomPydanticFastSerializer]):
    @sensitive_variables()
    @validate(*MOBILE_SESSION_RESPONSES, validate_responses=False)
    async def post(self, parsed_body: Body[MobileLoginPost]) -> HttpResponse:
        user: ApiUser = await authenticate_user(
            parsed_body, self.request, Surfaces.MOBILE
        )

        return await mobile_session_response(self, user)


########################################################################################


class WebLoginController(WebAuthController[CustomPydanticFastSerializer]):
    @override
    @sensitive_variables()
    @validate(*WEB_SESSION_RESPONSES, validate_responses=False)
    async def post(self, parsed_body: Body[WebLoginPost]) -> HttpResponse:
        await super().post()

        user: ApiUser = await authenticate_user(parsed_body, self.request, Surfaces.WEB)

        return await web_session_response(self, user)
