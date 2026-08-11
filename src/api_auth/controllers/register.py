from typing import ClassVar

from django.views.decorators.debug import sensitive_variables
from dmr import Body

from api_auth.models import ApiUser
from api_auth.schemas.user import ApiClientPost, ApiUserGet
from api_auth.services.user import UserCreateOperation
from api_core.controllers.models import ModelController
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.services.operations import CreateOperation

from .base import AuthController

########################################################################################


class RegisterController(
    AuthController,
    ModelController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserGet,
    ],
):
    create_operation: ClassVar[type[CreateOperation]] = UserCreateOperation

    @sensitive_variables()
    async def post(self, parsed_body: Body[ApiClientPost]) -> ApiUserGet:
        return await self.build_operation(self.create_operation).run(parsed_body)
