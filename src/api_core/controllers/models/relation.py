from typing import override

from dmr import Body, Path
from dmr.serializer import BaseSerializer

from api_core.schemas.base import DTO
from api_core.schemas.path import InstancePath, UuidInstancePath
from api_utils.types import DatabaseModel

from .detail import ModelManyToManyDetailController

########################################################################################


class ModelRelationController[
    Serializer: BaseSerializer,
    Model: DatabaseModel,
    Get: DTO,
    Put: DTO,
    Patch: DTO,
    PathSchema: InstancePath = UuidInstancePath,
](ModelManyToManyDetailController[Serializer, Model, Get, Put, Patch, PathSchema]):
    delete = None

    @override
    async def put(  # ty: ignore[invalid-method-override]
        self,
        parsed_body: Body[Put],
        parsed_path: Path[PathSchema],
    ) -> Get:
        return await self.build_operation(
            self.update_operation,
            overwrite=True,
            partial=False,
        ).run(body=parsed_body, path=parsed_path)

    @override
    async def patch(  # ty: ignore[invalid-method-override]
        self,
        parsed_body: Body[Patch],
        parsed_path: Path[PathSchema],
    ) -> Get:
        return await self.build_operation(
            self.update_operation,
            overwrite=False,
            partial=True,
        ).run(body=parsed_body, path=parsed_path)
