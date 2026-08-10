from collections.abc import Sequence
from functools import cached_property
from typing import ClassVar, Final, override

from django.db.models.query import QuerySet
from dmr.endpoint import Endpoint
from dmr.serializer import BaseSerializer

from api_core.controllers.base import BaseController
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.schemas.base import DTO
from api_core.services.mappers import ModelMapper, instance_mapper
from api_core.services.operations import (
    CreateOperation,
    DestroyOperation,
    LinkAttachOperation,
    LinkDetachOperation,
    LinkInspectOperation,
    ModelOperation,
    RetrieveOperation,
    UpdateOperation,
)
from api_core.services.relations import QuerySetProvider, RelationResolver
from api_utils.generics import resolve_type_args
from api_utils.types import DatabaseModel

########################################################################################

OPERATIONS: Final[dict[str, type[ModelOperation]]] = {
    "attach_operation": LinkAttachOperation,
    "create_operation": CreateOperation,
    "destroy_operation": DestroyOperation,
    "detach_operation": LinkDetachOperation,
    "inspect_operation": LinkInspectOperation,
    "retrieve_operation": RetrieveOperation,
    "update_operation": UpdateOperation,
}

########################################################################################


class ModelController[
    Serializer: BaseSerializer,
    Model: DatabaseModel,
    Get: DTO,
](BaseController[Serializer], QuerySetProvider):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    mapper: ModelMapper[Get] = staticmethod(instance_mapper)

    model: type[Model]

    schema: type[Get]

    def __init_subclass__(cls, **kwargs) -> None:  # ruff: ignore[missing-type-kwargs]
        super().__init_subclass__(**kwargs)

        for attr, tier in OPERATIONS.items():
            declared: type | None = cls.__dict__.get(attr)

            if declared is None:
                continue

            if not isinstance(declared, type) or not issubclass(declared, tier):
                name: str = getattr(declared, "__name__", str(declared))

                raise TypeError(
                    f"{cls.__name__}.{attr} debe derivar de {tier.__name__}, no {name}."
                )

            if abc_methods := getattr(declared, "__abstractmethods__", frozenset()):
                pending: str = ", ".join(sorted(abc_methods))

                raise TypeError(
                    f"{cls.__name__}.{attr} es abstracta; falta implementar: {pending}."
                )

        resolved, expected = resolve_type_args(cls, ModelController)

        for attr, value in resolved.items():
            if attr not in cls.__dict__:
                setattr(cls, attr, value)

        if cls.is_abstract:
            return

        missing: Sequence[str] = tuple(
            sorted(attr for attr in expected if not hasattr(cls, attr))
        )

        if missing:
            raise TypeError(
                f"{cls.__name__} no resuelve los atributos: {', '.join(missing)}.",
            )

    def build_operation[Operation: ModelOperation](
        self,
        operation: type[Operation],
        **kwargs,  # ruff: ignore[missing-type-kwargs]
    ) -> Operation:
        return operation(
            *operation.resolve_fields(self),
            mapper=self.mapper,
            schema=self.schema,
            qs=self.qs,
            **kwargs,
        )

    @override
    def build_qs(self) -> QuerySet:
        return self.resolver.build_qs()

    @cached_property
    def resolver(self) -> RelationResolver[Model, Get]:
        return RelationResolver.build(self.__class__.model, self.__class__.schema)

    @cached_property
    def qs(self) -> QuerySet:
        return self.build_qs()
