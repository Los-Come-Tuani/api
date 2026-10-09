from http import HTTPStatus
from typing import ClassVar

from dmr import Body, modify

from api_auth.schemas.account import ProfilePatch
from api_auth.schemas.session import SessionUserGet
from api_auth.services.account import update_profile
from api_auth.services.session_user import build_session_user
from api_core.controllers.serializers import CustomPydanticFastSerializer

from .base import PrivateAuthController

########################################################################################


class ProfileController(PrivateAuthController[CustomPydanticFastSerializer]):
    allows_pending_two_factor: ClassVar[bool] = True

    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> SessionUserGet:
        return await build_session_user(self.request.user)

    @modify(status_code=HTTPStatus.OK)
    async def patch(self, parsed_body: Body[ProfilePatch]) -> SessionUserGet:
        return await build_session_user(
            await update_profile(self.request.user, parsed_body),
        )
