from datetime import datetime
from http import HTTPStatus
from typing import ClassVar

from django.views.decorators.debug import sensitive_variables
from dmr import Body, modify

from api_auth.schemas.account import AccountClosePost, AccountRestorePost
from api_auth.schemas.closing import AccountClosingGet
from api_auth.services.account import close_account, restore_account, revoke_sessions
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import AuthController, PrivateAuthController

########################################################################################


class AccountCloseController(PrivateAuthController[CustomPydanticFastSerializer]):
    allows_pending_two_factor: ClassVar[bool] = True

    @modify(status_code=HTTPStatus.OK)
    @sensitive_variables()
    async def post(self, parsed_body: Body[AccountClosePost]) -> AccountClosingGet:
        effective: datetime = await close_account(
            password=parsed_body.password,
            user=self.request.user,
        )

        return AccountClosingGet(effective_at=effective)


class AccountRestoreController(AuthController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[AccountRestorePost]) -> None:
        await restore_account(
            email=parsed_body.email,
            password=parsed_body.password,
            request=self.request,
        )


class SessionRevokeController(PrivateAuthController[CustomPydanticFastSerializer]):
    allows_pending_two_factor: ClassVar[bool] = True

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self) -> None:
        # cierra la sesión en todos los dispositivos, incluido este
        await revoke_sessions(self.request.user)
