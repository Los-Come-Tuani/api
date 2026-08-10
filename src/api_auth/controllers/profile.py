from collections.abc import Sequence
from http import HTTPMethod
from typing import ClassVar

from api_auth.models import ApiUser
from api_auth.schemas.user import ApiUserGet
from api_core.controllers.models import ModelController
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.path import UuidInstancePath
from api_core.services.operations import FlatRetrieveOperation, RetrieveOperation

########################################################################################


class ProfileController(
    ModelController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserGet,
    ]
):
    permissions: ClassVar[dict[HTTPMethod, Sequence[str]]] = {HTTPMethod.GET: ()}

    retrieve_operation: ClassVar[type[RetrieveOperation]] = FlatRetrieveOperation

    async def get(self) -> ApiUserGet:
        return await self.build_operation(self.retrieve_operation).run(
            path=UuidInstancePath(id=self.request.user.pk),
        )
