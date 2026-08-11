from django.contrib.auth.models import Permission

from api_auth.filtersets.permission import PermissionFilterSet
from api_auth.schemas.permission import (
    PermissionFilterAllQuery,
    PermissionFilterQuery,
    PermissionGet,
)
from api_core.controllers.mixins import DefaultOrderMixin
from api_core.controllers.models import (
    ModelDetailController,
    ModelListAllController,
    ModelListController,
)
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.get import DTO
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import IntInstancePath

########################################################################################


class PermissionDetailController(
    DefaultOrderMixin,
    ModelDetailController[
        CustomPydanticFastSerializer,
        Permission,
        PermissionGet,
        DTO,
        DTO,
        IntInstancePath,
    ],
):
    put = None
    patch = None
    delete = None


########################################################################################


class PermissionListController(
    DefaultOrderMixin,
    ModelListController[
        CustomPydanticFastSerializer,
        Permission,
        PermissionFilterSet,
        PermissionFilterQuery,
        PermissionGet,
        DTO,
        Paginated[PermissionGet],
    ],
):
    post = None


########################################################################################


class PermissionListAllController(
    DefaultOrderMixin,
    ModelListAllController[
        CustomPydanticFastSerializer,
        Permission,
        PermissionFilterSet,
        PermissionFilterAllQuery,
        PermissionGet,
        list[PermissionGet],
    ],
):
    pass
