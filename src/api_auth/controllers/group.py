from django.contrib.auth.models import Group

from api_auth.filtersets.group import GroupFilterSet
from api_auth.schemas.group import (
    GroupFilterAllQuery,
    GroupFilterQuery,
    GroupGet,
    GroupInlineGet,
    GroupPatch,
    GroupPost,
    GroupPut,
)
from api_core.controllers.mixins import DefaultOrderMixin
from api_core.controllers.models import (
    ModelListAllController,
    ModelManyToManyDetailController,
    ModelManyToManyListController,
)
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import IntInstancePath

########################################################################################


class GroupDetailController(
    DefaultOrderMixin,
    ModelManyToManyDetailController[
        CustomPydanticFastSerializer,
        Group,
        GroupGet,
        GroupPut,
        GroupPatch,
        IntInstancePath,
    ],
):
    pass


########################################################################################


class GroupListController(
    DefaultOrderMixin,
    ModelManyToManyListController[
        CustomPydanticFastSerializer,
        Group,
        GroupFilterSet,
        GroupFilterQuery,
        GroupGet,
        GroupPost,
        Paginated[GroupGet],
    ],
):
    pass


########################################################################################


class GroupListAllController(
    DefaultOrderMixin,
    ModelListAllController[
        CustomPydanticFastSerializer,
        Group,
        GroupFilterSet,
        GroupFilterAllQuery,
        GroupInlineGet,
        list[GroupInlineGet],
    ],
):
    pass
