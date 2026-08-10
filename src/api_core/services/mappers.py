from types import MethodType
from typing import TYPE_CHECKING

from django.core.paginator import AsyncPaginator, EmptyPage

from api_core.schemas.get import BaseGet
from api_core.schemas.pagination import Paginated
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError

from .relations import collect_m2m_names, unwrap_list_annotation

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import Final

    from django.core.paginator import AsyncPage
    from django.db.models.query import QuerySet

    from api_core.schemas.base import DTO
    from api_core.schemas.pagination import PageQuery
    from api_utils.types import DatabaseModel


########################################################################################

MAX_UNPAGINATED: Final[int] = 10_000

########################################################################################


type ModelMapper[Get: DTO] = Callable[[DatabaseModel, type[Get]], Get]


########################################################################################


class PrefetchedProxy:
    __slots__ = ("obj", "overrides")

    def __init__(self, obj: DatabaseModel, overrides: dict) -> None:
        self.obj: DatabaseModel = obj
        self.overrides: dict = overrides

    def __getattr__(self, name: str):  # ruff: ignore[missing-return-type-special-method]
        overrides: dict = object.__getattribute__(self, "overrides")

        if name in overrides:
            return overrides[name]

        return getattr(object.__getattribute__(self, "obj"), name)


########################################################################################


def instance_mapper[Get: DTO](obj: DatabaseModel, schema: type[Get]) -> Get:
    m2m: frozenset[str] = collect_m2m_names(schema)

    if not m2m:
        return schema.model_validate(obj)

    overrides: dict = {}

    for name in m2m:
        inner: type | None = unwrap_list_annotation(
            schema.model_fields[name].annotation,
        )

        value = getattr(obj, name, None)

        if value is None:
            overrides[name] = ()
            continue

        related = (
            value.all()
            if isinstance(getattr(value, "all", None), MethodType)
            else value
        )

        overrides[name] = (
            tuple(instance_mapper(child, inner) for child in related)
            if inner is not None and issubclass(inner, BaseGet)
            else tuple(related)
        )

    return schema.model_validate(PrefetchedProxy(obj, overrides))


########################################################################################


async def paginated_mapper[Get: DTO](
    *,
    mapper: ModelMapper[Get],
    schema: type[Get],
    qs: QuerySet,
    query: PageQuery,
) -> Paginated[Get]:
    paginator = AsyncPaginator(object_list=qs, per_page=query.page_size)

    try:
        page: AsyncPage = await paginator.apage(number=query.page)
    except EmptyPage as e:
        raise BadRequestError(
            field_errors={"page": "La página especificada no existe."},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.QUERY) from e

    return Paginated(
        next=(await page.ahas_next()),
        previous=(await page.ahas_previous()),
        elements=(await paginator.acount()),
        pages=(await paginator.anum_pages()),
        current=query.page,
        results=[mapper(obj, schema) async for obj in page],
    )


########################################################################################


async def queryset_mapper[Get: DTO](
    *,
    mapper: ModelMapper[Get],
    schema: type[Get],
    qs: QuerySet,
) -> list[Get]:
    objs: Sequence[DatabaseModel] = [obj async for obj in qs[: (MAX_UNPAGINATED + 1)]]

    if len(objs) > MAX_UNPAGINATED:
        raise BadRequestError(
            field_errors={
                "detail": (
                    "La consulta devuelve más de "
                    f"{MAX_UNPAGINATED:,} registros; refine los filtros."
                ),
            },
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.QUERY)

    return [mapper(obj, schema) for obj in objs]
