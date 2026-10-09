from math import ceil
from typing import TYPE_CHECKING, Any

from api_core.schemas.pagination import Paginated

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models.query import QuerySet

    from api_core.schemas.base import DTO
    from api_core.schemas.pagination import PageQuery

########################################################################################


# Una página de una consulta ya ordenada, con cada fila convertida por `build`. El
# esquema va explícito: `Paginated` se construye con la clase concreta, no con el tipo
# genérico, para que cada resultado se serialice con todos sus campos.
def paginate[Get: DTO](
    ordered: QuerySet,
    query: PageQuery,
    build: Callable[..., Get],
    schema: type[Get],
) -> Paginated[Get]:
    total: int = ordered.count()
    start: int = (query.page - 1) * query.page_size
    pages: int = max(1, ceil(total / query.page_size))

    page: Any = Paginated[schema]  # ty: ignore[invalid-type-form]

    return page(
        current=query.page,
        elements=total,
        next=query.page < pages,
        pages=pages,
        previous=query.page > 1,
        results=[build(item) for item in ordered[start : start + query.page_size]],
    )
