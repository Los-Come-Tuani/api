from typing import TYPE_CHECKING, override

from asgiref.sync import sync_to_async
from django.db import IntegrityError
from django.db.transaction import atomic as raw_atomic
from pgbulk import (
    copy as bulk_copy,
    upsert as bulk_upsert,
)
from pgtransaction import (
    REPEATABLE_READ,
    atomic as retry_atomic,
)

from api_core.services.locks import RETRIES, lock_instance
from api_core.services.operations import ModelOperation
from api_core.services.relations import resolve_nested_relation, supports_copy
from api_exceptions.enums import RequestScopes
from api_exceptions.errors import ConflictError
from api_utils.db import set_immediate_constraints

from .base import CreateOperation, UpdateOperation, split_payload

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

    from django.db.models.fields.reverse_related import ManyToOneRel, OneToOneRel
    from django.db.models.query import QuerySet

    from api_core.controllers.models.base import ModelController
    from api_core.schemas.base import DTO
    from api_utils.types import DatabaseModel

########################################################################################

COPY_THRESHOLD: Final[int] = 32

MAX_CONFLICTS: Final[int] = COPY_THRESHOLD

########################################################################################


class NestedOperation[Get: DTO](ModelOperation[Get]):
    __slots__ = ()

    @staticmethod
    @override
    def resolve_fields(ctrl: ModelController) -> frozenset[str]:
        return ctrl.resolver.nested_names


########################################################################################


class NestedCreateOperation[
    Get: DTO,
    Post: DTO,
](NestedOperation[Get], CreateOperation[Get, Post]):
    __slots__ = ()

    @override
    async def execute(self, data: dict) -> DatabaseModel:
        return await sync_to_async(func=exec_nested_post)(
            *self.fields,
            data=data,
            qs=self.qs,
        )


########################################################################################


class NestedUpdateOperation[
    Get: DTO,
    Post: DTO,
](NestedOperation[Get], UpdateOperation[Get, Post]):
    __slots__ = ()

    @override
    async def execute(self, data: dict, lookup: dict) -> DatabaseModel:
        return await sync_to_async(func=exec_nested_update)(
            *self.fields,
            data=data,
            lookup=lookup,
            qs=self.qs,
        )


########################################################################################


@retry_atomic(retry=RETRIES)
def exec_nested_post[Model: DatabaseModel](
    *relations: str,
    data: dict,
    qs: QuerySet,
) -> Model:
    model: type[Model] = qs.model  # ty:ignore[invalid-assignment]

    payload, nested = split_payload(data, relations)

    set_immediate_constraints()

    obj: Model = qs.create(**payload)

    write_children(model=model, nested=nested, obj=obj, replace=False)

    return qs.get(pk=obj.pk)


########################################################################################


@retry_atomic(isolation_level=REPEATABLE_READ, retry=RETRIES)
def exec_nested_update[Model: DatabaseModel](
    *relations: str,
    data: dict,
    lookup: dict,
    qs: QuerySet,
) -> Model:
    model: type[Model] = qs.model  # ty:ignore[invalid-assignment]

    payload, nested = split_payload(data, relations)

    set_immediate_constraints()

    obj: Model = lock_instance(lookup=lookup, model=model)  # ty:ignore[invalid-assignment]

    if payload:
        qs.filter(**lookup).update(**payload)

    write_children(model=model, nested=nested, obj=obj, replace=True)

    return qs.get(**lookup)


########################################################################################


def match_conflict_index(*, exc: IntegrityError, items: Sequence[dict]) -> int | None:
    pairs: dict[str, str] = ConflictError.parse_pairs_from_psql_error(exc)

    if not pairs:
        return None

    for index, item in enumerate(items):
        if all(str(item.get(col)) == value for col, value in pairs.items()):
            return index

    return None


########################################################################################


def probe_conflict_index(
    *,
    back_ref: str,
    child: type[DatabaseModel],
    items: Sequence[dict],
    obj: DatabaseModel,
) -> int | None:
    for index, item in enumerate(items[:MAX_CONFLICTS]):
        try:
            with raw_atomic():
                child._default_manager.create(**item, **{back_ref: obj})
        except IntegrityError:
            return index

    return None


########################################################################################


def scope_child_conflict(  # ruff: ignore[too-many-arguments]
    *,
    back_ref: str,
    child: type[DatabaseModel],
    exc: IntegrityError,
    items: Sequence[dict] | None,
    name: str,
    obj: DatabaseModel,
) -> ConflictError:
    conflict: ConflictError = ConflictError.from_integrity_error(exc)

    if items is None:
        return conflict.scoped(RequestScopes.BODY, name)

    index: int | None = match_conflict_index(exc=exc, items=items)

    if index is None:
        index = probe_conflict_index(
            back_ref=back_ref,
            child=child,
            items=items,
            obj=obj,
        )

    if index is None:
        return conflict.scoped(RequestScopes.BODY, name)

    return conflict.scoped(RequestScopes.BODY, name, index)


########################################################################################


def write_children[Model: DatabaseModel](
    *,
    model: type[Model],
    nested: dict,
    obj: Model,
    replace: bool,
) -> None:
    for field, value in nested.items():
        if value is None:
            continue

        rel: ManyToOneRel | OneToOneRel | None = resolve_nested_relation(model, field)

        if rel is None:
            continue

        child: type[DatabaseModel] = rel.related_model

        back_ref: str = rel.field.name

        try:
            with raw_atomic():
                if rel.one_to_one:
                    write_child(
                        back_ref=back_ref,
                        child=child,
                        data=value,
                        obj=obj,
                        replace=replace,
                    )
                else:
                    write_collection(
                        back_ref=back_ref,
                        child=child,
                        items=value,
                        obj=obj,
                        replace=replace,
                    )
        except IntegrityError as i:
            raise scope_child_conflict(
                back_ref=back_ref,
                child=child,
                exc=i,
                items=(None if rel.one_to_one else value),
                name=field,
                obj=obj,
            ) from i


########################################################################################


def write_child(
    *,
    back_ref: str,
    child: type[DatabaseModel],
    data: dict,
    obj: DatabaseModel,
    replace: bool,
) -> None:
    if not replace:
        child._default_manager.create(**data, **{back_ref: obj})

        return

    bulk_upsert(
        model_objs=(child(**data, **{back_ref: obj}),),
        queryset=child._default_manager.all(),
        unique_fields=[back_ref],
        update_fields=list(data),
    )


########################################################################################


def write_collection(
    *,
    back_ref: str,
    child: type[DatabaseModel],
    items: Sequence[dict],
    obj: DatabaseModel,
    replace: bool,
) -> None:
    if replace:
        child._default_manager.filter(**{back_ref: obj}).delete()

    objs: Sequence[DatabaseModel] = tuple(
        child(**item, **{back_ref: obj}) for item in items
    )

    if not objs:
        return

    if len(objs) >= COPY_THRESHOLD and supports_copy(child):
        bulk_copy(child._default_manager.all(), objs)

        return

    child._default_manager.bulk_create(objs=objs)
