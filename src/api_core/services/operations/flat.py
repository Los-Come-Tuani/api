from typing import TYPE_CHECKING, override

from api_exceptions.enums import RequestScopes
from api_exceptions.errors import NotFoundError

from .base import (
    CreateOperation,
    DestroyOperation,
    RetrieveOperation,
    UpdateOperation,
)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet

    from api_core.schemas.base import DTO
    from api_utils.types import DatabaseModel

########################################################################################


class FlatCreateOperation[Get: DTO, Post: DTO](CreateOperation[Get, Post]):
    __slots__ = ()

    @override
    async def execute(self, data: dict) -> DatabaseModel:
        obj: DatabaseModel = await self.qs.acreate(**data)

        return await self.qs.aget(pk=obj.pk)


########################################################################################


class FlatDestroyOperation[Get: DTO](DestroyOperation[Get]):
    __slots__ = ()

    @override
    async def execute(self, lookup: dict) -> int:
        target: QuerySet = (
            self.qs.prefetch_related(None).select_related(None).filter(**lookup)
        )

        deleted, _ = await target.adelete()

        return deleted


########################################################################################


class FlatRetrieveOperation[Get: DTO](RetrieveOperation[Get]):
    __slots__ = ()

    @override
    async def execute(self, lookup: dict) -> DatabaseModel:
        return await self.qs.aget(**lookup)


########################################################################################


class FlatUpdateOperation[Get: DTO, Post: DTO](UpdateOperation[Get, Post]):
    __slots__ = ()

    @override
    async def execute(self, data: dict, lookup: dict) -> DatabaseModel:
        if data and not await self.qs.filter(**lookup).aupdate(**data):
            raise NotFoundError(field_errors=lookup).scoped(RequestScopes.PATH)

        return await self.qs.aget(**lookup)
