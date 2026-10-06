from http import HTTPStatus
from typing import ClassVar

from django.views.decorators.debug import sensitive_variables
from dmr import Body, modify

from api_auth.schemas.account import (
    PasswordChangePost,
    PasswordForgotPost,
    PasswordResetPost,
)
from api_auth.services.account import (
    change_password,
    request_password_reset,
    reset_password,
)
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import AuthController, PrivateAuthController

########################################################################################


class PasswordForgotController(AuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self, parsed_body: Body[PasswordForgotPost]) -> None:  # ruff: ignore[no-self-use]
        # responde igual exista o no la cuenta, para no revelar quién está registrado
        await request_password_reset(parsed_body.email)


class PasswordResetController(AuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[PasswordResetPost]) -> None:  # ruff: ignore[no-self-use]
        await reset_password(
            code=parsed_body.code,
            email=parsed_body.email,
            password=parsed_body.password,
        )


class PasswordChangeController(PrivateAuthController[CustomPydanticFastSerializer]):
    allows_pending_two_factor: ClassVar[bool] = True

    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[PasswordChangePost]) -> None:
        await change_password(
            current=parsed_body.current_password,
            new=parsed_body.password,
            user=self.request.user,
        )
