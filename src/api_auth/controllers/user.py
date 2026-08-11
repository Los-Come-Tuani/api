from typing import ClassVar, override

from django.views.decorators.debug import sensitive_variables
from dmr import Body

from api_auth.filtersets.user import ApiUserFilterSet
from api_auth.models import ApiUser, ApiUserGroups, ApiUserPermissions
from api_auth.schemas.through import ApiUserGroupsLinkGet, ApiUserPermissionsLinkGet
from api_auth.schemas.user import (
    ApiStaffPost,
    ApiUserFilterAllQuery,
    ApiUserFilterQuery,
    ApiUserGet,
    ApiUserGroupsGet,
    ApiUserGroupsPatch,
    ApiUserGroupsPut,
    ApiUserInlineGet,
    ApiUserPatch,
    ApiUserPermissionsGet,
    ApiUserPermissionsPatch,
    ApiUserPermissionsPut,
    ApiUserPut,
)
from api_auth.services.user import UserCreateOperation
from api_core.controllers.models import (
    ModelDetailController,
    ModelListAllController,
    ModelManyToManyListController,
)
from api_core.controllers.models.link import ModelLinkController
from api_core.controllers.models.relation import ModelRelationController
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.services.operations import CreateOperation

from .mixins import (
    ApiUserGroupsLinkMixin,
    ApiUserGroupsMixin,
    ApiUserPermissionsLinkMixin,
    ApiUserPermissionsMixin,
    ApiUserRelationsMixin,
)

########################################################################################


class ApiUserDetailController(
    ApiUserRelationsMixin,
    ModelDetailController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserGet,
        ApiUserPut,
        ApiUserPatch,
    ],
):
    pass


########################################################################################


class ApiUserGroupsController(
    ApiUserGroupsMixin,
    ModelRelationController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserGroupsGet,
        ApiUserGroupsPut,
        ApiUserGroupsPatch,
    ],
):
    pass


########################################################################################


class ApiUserGroupsLinkController(
    ApiUserGroupsLinkMixin,
    ModelLinkController[
        CustomPydanticFastSerializer,
        ApiUserGroups,
        ApiUserGroupsLinkGet,
    ],
):
    parent: ClassVar[str] = "api_user"
    related: ClassVar[str] = "group"
    relation: ClassVar[str] = "groups"


########################################################################################


class ApiUserPermissionsController(
    ApiUserPermissionsMixin,
    ModelRelationController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserPermissionsGet,
        ApiUserPermissionsPut,
        ApiUserPermissionsPatch,
    ],
):
    pass


########################################################################################


class ApiUserPermissionsLinkController(
    ApiUserPermissionsLinkMixin,
    ModelLinkController[
        CustomPydanticFastSerializer,
        ApiUserPermissions,
        ApiUserPermissionsLinkGet,
    ],
):
    parent: ClassVar[str] = "api_user"
    related: ClassVar[str] = "permission"
    relation: ClassVar[str] = "permissions"


########################################################################################


class ApiUserListController(
    ApiUserRelationsMixin,
    ModelManyToManyListController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserFilterSet,
        ApiUserFilterQuery,
        ApiUserGet,
        ApiStaffPost,
        Paginated[ApiUserGet],
    ],
):
    create_operation: ClassVar[type[CreateOperation]] = UserCreateOperation

    @override
    @sensitive_variables()
    async def post(self, parsed_body: Body[ApiStaffPost]) -> ApiUserGet:
        return await self.build_operation(self.create_operation).run(parsed_body)


########################################################################################


class ApiUserListAllController(
    ModelListAllController[
        CustomPydanticFastSerializer,
        ApiUser,
        ApiUserFilterSet,
        ApiUserFilterAllQuery,
        ApiUserInlineGet,
        list[ApiUserInlineGet],
    ],
):
    pass
