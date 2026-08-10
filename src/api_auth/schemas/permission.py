from typing import Annotated

from pydantic import AfterValidator, AliasPath, ConfigDict, Field, PositiveInt

from api_auth.filtersets.permission import PermissionFilterSet
from api_core.schemas.factories import build_filter_query
from api_core.schemas.filters import PaginatedFilterQuery, UnpaginatedFilterQuery
from api_core.schemas.get import BaseGet

########################################################################################


class PermissionGet(BaseGet[PositiveInt]):
    model_config = ConfigDict(loc_by_alias=True)

    content_type: Annotated[BaseGet[PositiveInt], Field(exclude=True)]

    action: Annotated[
        str,
        AfterValidator(func=(lambda s: s.split("_")[0])),
        Field(validation_alias=AliasPath("codename")),
    ]

    model: Annotated[
        str,
        Field(validation_alias=AliasPath("content_type", "model")),
    ]


########################################################################################

PermissionFilterQuery = build_filter_query(
    PaginatedFilterQuery,
    PermissionFilterSet,
)

PermissionFilterAllQuery = build_filter_query(
    UnpaginatedFilterQuery,
    PermissionFilterSet,
)
