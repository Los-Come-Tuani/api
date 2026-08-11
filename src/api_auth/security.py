from typing import TYPE_CHECKING, override

from dmr.exceptions import NotAuthenticatedError
from dmr.openapi.objects import SecurityScheme
from dmr.security.jwt import JWTAsyncAuth

from api_auth.enums import TokenTypes
from api_auth.services.blocklist import find_blocklisted_jtis
from api_auth.services.csrf import ensure_csrf
from api_auth.services.jwt import jwt_lookup_keys
from api_auth.services.permissions import ensure_model_permissions
from api_core.config import CONFIG
from api_middlewares.history import build_user_context

if TYPE_CHECKING:
    from typing import Self

    from django.contrib.auth.base_user import AbstractBaseUser
    from django.http import HttpRequest
    from dmr import Controller
    from dmr.endpoint import Endpoint
    from dmr.openapi.objects import SecurityRequirement
    from dmr.security.jwt import JWToken

########################################################################################


class JwtRbacAsyncAuth(JWTAsyncAuth):
    __slots__ = ()

    @override
    async def __call__(
        self,
        endpoint: Endpoint,
        controller: Controller,
    ) -> Self | None:
        authed: Self | None = await super().__call__(
            endpoint,
            controller,
        )

        if authed is None:
            return None

        # user has been authenticated or rejected by now,
        # `controller.request` should be "usable" (see `api_utils.types`)
        await ensure_model_permissions(controller, controller.request)  # ty: ignore[invalid-argument-type]
        await build_user_context(controller.request)  # ty: ignore[invalid-argument-type]

        return authed

    @override
    async def check_auth(
        self,
        user: AbstractBaseUser,
        token: JWToken,
    ) -> None:
        await super().check_auth(user, token)

        if token.extras.get("type") != TokenTypes.ACCESS or await find_blocklisted_jtis(
            jtis=jwt_lookup_keys(token),
        ):
            raise NotAuthenticatedError


########################################################################################


class JwtCookieAsyncAuth(JwtRbacAsyncAuth):
    __slots__ = ()

    @override
    async def __call__(
        self,
        endpoint: Endpoint,
        controller: Controller,
    ) -> Self | None:
        authed: Self | None = await super().__call__(endpoint, controller)

        if authed is not None:
            ensure_csrf(controller.request)

        return authed

    @override
    def get_token_from_request(self, request: HttpRequest) -> str | None:
        return request.COOKIES.get(TokenTypes.ACCESS)

    @property
    @override
    def security_requirement(self) -> SecurityRequirement:
        return {"csrf": [], self.security_scheme_name: []}

    @property
    @override
    def security_schemes(self) -> dict[str, SecurityScheme]:
        return {
            "csrf": SecurityScheme(
                name=CONFIG.csrf_header,
                security_scheme_in="header",
                type="apiKey",
            ),
            self.security_scheme_name: SecurityScheme(
                name=TokenTypes.ACCESS,
                security_scheme_in="cookie",
                type="apiKey",
            ),
        }

    @override
    def split_encoded_token(self, header: str) -> str | None:
        return header


########################################################################################


class JwtHeaderAsyncAuth(JwtRbacAsyncAuth):
    __slots__ = ()

    @property
    @override
    def security_schemes(self) -> dict[str, SecurityScheme]:
        return {
            self.security_scheme_name: SecurityScheme(
                bearer_format="JWT",
                scheme="Bearer",
                type="http",
            ),
        }
