from typing import TYPE_CHECKING

from django_filters.filters import OrderingFilter
from django_filters.filterset import FilterSet

from api_auth.enums import ApiUserTypes
from api_auth.models import ApiUser
from api_core.filters import (
    IntFilter,
    LoweredFilter,
    LoweredSearchFilter,
    TypedChoiceFilter,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models.base import Model

########################################################################################


class ApiUserFilterSet(FilterSet):
    first_name = LoweredFilter()
    last_name = LoweredFilter()
    email = LoweredFilter()
    username = LoweredFilter()

    group_id = IntFilter(field_name="groups__id")
    permission_id = IntFilter(field_name="permissions__id")

    group = TypedChoiceFilter(enum=ApiUserTypes, field_name="groups__name")

    search = LoweredSearchFilter("username", "email", "first_name", "last_name")

    order = OrderingFilter(fields=("username", "email", "created_at"))

    class Meta:
        fields: Sequence[str] = ("id", "is_active")
        model: type[Model] = ApiUser
