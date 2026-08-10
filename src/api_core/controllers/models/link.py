from collections.abc import Sequence
from http import HTTPMethod, HTTPStatus
from typing import ClassVar, override

from dmr import Path, modify
from dmr.serializer import BaseSerializer

from api_auth.services.permissions import T_ADD_PERM, T_DELETE_PERM, T_VIEW_PERM
from api_core.schemas.base import DTO
from api_core.schemas.path import RelatedInstancePath, UuidToUuidRelatedPath
from api_core.services.operations import (
    FlatLinkAttachOperation,
    FlatLinkDetachOperation,
    FlatLinkInspectOperation,
    LinkAttachOperation,
    LinkDetachOperation,
    LinkInspectOperation,
    ModelOperation,
)
from api_utils.types import DatabaseModel

from .base import ModelController

########################################################################################


class ModelLinkController[
    Serializer: BaseSerializer,
    Model: DatabaseModel,
    Get: DTO,
    PathSchema: RelatedInstancePath = UuidToUuidRelatedPath,
](ModelController[Serializer, Model, Get]):
    attach_operation: ClassVar[type[LinkAttachOperation]] = FlatLinkAttachOperation
    detach_operation: ClassVar[type[LinkDetachOperation]] = FlatLinkDetachOperation
    inspect_operation: ClassVar[type[LinkInspectOperation]] = FlatLinkInspectOperation

    permissions: ClassVar[dict[HTTPMethod, Sequence[str]]] = {
        HTTPMethod.GET: (T_VIEW_PERM,),
        HTTPMethod.PUT: (T_ADD_PERM,),
        HTTPMethod.DELETE: (T_DELETE_PERM,),
    }

    parent: ClassVar[str]
    related: ClassVar[str]
    relation: ClassVar[str]

    @classmethod
    def parent_model(cls) -> type[DatabaseModel]:
        return cls.model._meta.get_field(cls.parent).related_model

    @classmethod
    def related_model(cls) -> type[DatabaseModel]:
        return cls.model._meta.get_field(cls.related).related_model

    @override
    def build_operation[Operation: ModelOperation](
        self,
        operation: type[Operation],
        **kwargs,  # ruff: ignore[missing-type-kwargs]
    ) -> Operation:
        return super().build_operation(
            operation,
            parent=self.parent,
            related=self.related,
            **kwargs,
        )

    async def get(self, parsed_path: Path[PathSchema]) -> Get:
        return await self.build_operation(self.inspect_operation).run(parsed_path)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def put(self, parsed_path: Path[PathSchema]) -> None:
        await self.build_operation(self.attach_operation).run(parsed_path)

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[PathSchema]) -> None:
        await self.build_operation(self.detach_operation).run(parsed_path)
