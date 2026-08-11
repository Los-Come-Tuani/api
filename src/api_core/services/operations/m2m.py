from typing import TYPE_CHECKING, override

from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.transaction import atomic as raw_atomic
from pgtransaction import (
    REPEATABLE_READ,
    atomic as retry_atomic,
)

from api_core.services.locks import RETRIES, lock_instance
from api_core.services.operations import ModelOperation
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError, ConflictError
from api_utils.db import set_immediate_constraints

from .base import CreateOperation, UpdateOperation, split_payload

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from django.db.models.fields.related_descriptors import ManyToManyDescriptor
    from django.db.models.query import QuerySet

    from api_core.controllers.models.base import ModelController
    from api_core.schemas.get import DTO
    from api_core.services.mappers import ModelMapper
    from api_utils.types import DatabaseModel

########################################################################################


class ManyToManyOperation[Get: DTO](ModelOperation[Get]):
    __slots__ = ()

    @staticmethod
    @override
    def resolve_fields(ctrl: ModelController) -> frozenset[str]:
        return ctrl.resolver.m2m_names


########################################################################################


class ManyToManyCreateOperation[
    Get: DTO,
    Post: DTO,
](ManyToManyOperation[Get], CreateOperation[Get, Post]):
    __slots__ = ()

    @override
    async def execute(self, data: dict) -> DatabaseModel:
        return await sync_to_async(func=exec_m2m_post)(
            *self.fields,
            data=data,
            qs=self.qs,
        )


########################################################################################


class ManyToManyUpdateOperation[
    Get: DTO,
    Post: DTO,
](ManyToManyOperation[Get], UpdateOperation[Get, Post]):
    __slots__ = ("overwrite",)

    @override
    def __init__(
        self,
        *fields: str,
        mapper: ModelMapper[Get],
        overwrite: bool = False,
        partial: bool = False,
        schema: type[Get],
        qs: QuerySet,
    ) -> None:
        super().__init__(
            *fields,
            mapper=mapper,
            partial=partial,
            schema=schema,
            qs=qs,
        )

        self.overwrite: bool = overwrite

    @override
    async def execute(self, data: dict, lookup: dict) -> DatabaseModel:
        return await sync_to_async(func=exec_m2m_update)(
            *self.fields,
            data=data,
            lookup=lookup,
            overwrite=self.overwrite,
            qs=self.qs,
        )


########################################################################################


@retry_atomic(retry=RETRIES)
def exec_m2m_post(
    *attrs: str,
    data: dict,
    qs: QuerySet,
    user: bool = False,
) -> DatabaseModel:
    payload, extracted = split_payload(data, attrs)

    m2m_inputs: dict[str, Sequence] = {
        name: value or () for name, value in extracted.items()
    }

    set_immediate_constraints()

    validate_existing_ids(m2m_inputs, qs.model)  # ty:ignore[invalid-argument-type]

    method = qs.create if not user else qs.model.objects.create_user  # ty: ignore[unresolved-attribute]

    obj: DatabaseModel = method(**payload)

    m2m_handler(m2m_inputs=m2m_inputs, obj=obj)

    return qs.get(pk=obj.pk)


########################################################################################


@retry_atomic(isolation_level=REPEATABLE_READ, retry=RETRIES)
def exec_m2m_update(
    *attrs: str,
    data: dict,
    lookup: dict,
    overwrite: bool,
    qs: QuerySet,
) -> DatabaseModel:
    payload, extracted = split_payload(data, attrs)

    m2m_inputs: dict[str, Sequence] = {
        name: value or () for name, value in extracted.items()
    }

    set_immediate_constraints()

    obj: DatabaseModel = lock_instance(lookup=lookup, model=qs.model)  # ty:ignore[invalid-argument-type]

    validate_existing_ids(m2m_inputs, qs.model)  # ty:ignore[invalid-argument-type]

    if payload:
        qs.filter(**lookup).update(**payload)

    m2m_handler(m2m_inputs=m2m_inputs, obj=obj, overwrite=overwrite)

    return qs.get(**lookup)


########################################################################################


def m2m_handler(
    *,
    m2m_inputs: dict,
    obj: DatabaseModel,
    overwrite: bool = False,
) -> None:
    for attr, id_set in m2m_inputs.items():
        try:
            with raw_atomic():
                if overwrite:
                    getattr(obj, attr).set(id_set)
                else:
                    getattr(obj, attr).add(*id_set)
        except IntegrityError as i:
            raise ConflictError.from_integrity_error(i).scoped(
                RequestScopes.BODY,
                attr,
            ) from i


########################################################################################


def validate_existing_ids(m2m_inputs: dict, model: type[DatabaseModel]) -> None:
    for attr, id_set in m2m_inputs.items():
        if not id_set:
            continue

        descriptor: ManyToManyDescriptor = getattr(model, attr)

        related: type[DatabaseModel] = (
            descriptor.rel.related_model if descriptor.reverse else descriptor.rel.model
        )

        provided: frozenset[UUID] = frozenset(id_set)
        existing: frozenset[UUID] = frozenset(
            related._default_manager.filter(
                id__in=provided,
            ).values_list("id", flat=True)
        )

        missing: frozenset[UUID] = provided - existing

        if missing:
            raise BadRequestError(
                field_errors={
                    index: f"No existe un registro relacionado con el valor '{uid}'."
                    for index, uid in enumerate(id_set)
                    if uid in missing
                },
                type=BadRequestErrorTypes.FAILED_VALIDATION,
            ).scoped(RequestScopes.BODY, attr)
