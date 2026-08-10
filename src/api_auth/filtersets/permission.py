from typing import TYPE_CHECKING

from django.contrib.auth.models import Permission
from django_filters.filters import OrderingFilter
from django_filters.filterset import FilterSet

from api_auth.enums import PermissionTypes
from api_core.filters import (
    IntFilter,
    LoweredFilter,
    LoweredSearchFilter,
    TypedLoweredFilter,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models.base import Model

########################################################################################


class PermissionFilterSet(FilterSet):
    id = IntFilter()

    action = TypedLoweredFilter(
        enum=PermissionTypes,
        field_name="codename",
    )

    model = LoweredFilter(field_name="content_type__model")

    search = LoweredSearchFilter("codename", "content_type__model")

    order = OrderingFilter(fields=("codename",))

    class Meta:
        fields: Sequence[str] = ()
        model: type[Model] = Permission
