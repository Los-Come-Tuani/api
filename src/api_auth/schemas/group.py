from typing import Annotated

from pydantic import PositiveInt, StringConstraints

from api_auth.filtersets.group import GroupFilterSet
from api_core.schemas.factories import (
    build_filter_query,
    build_patch_schema,
    build_put_schema,
)
from api_core.schemas.filters import PaginatedFilterQuery, UnpaginatedFilterQuery
from api_core.schemas.get import DTO, BaseGet

from .permission import PermissionGet

########################################################################################


class GroupInlineGet(BaseGet[PositiveInt]):
    name: str


########################################################################################


class GroupGet(GroupInlineGet):
    permissions: tuple[PermissionGet, ...]


########################################################################################


class GroupPost(DTO):
    name: Annotated[str, StringConstraints(max_length=150, min_length=1)]
    permissions: tuple[PositiveInt, ...] | None = None


########################################################################################

GroupPut = build_put_schema(GroupPost)
GroupPatch = build_patch_schema(GroupPut)

########################################################################################

GroupFilterQuery = build_filter_query(PaginatedFilterQuery, GroupFilterSet)
GroupFilterAllQuery = build_filter_query(UnpaginatedFilterQuery, GroupFilterSet)
