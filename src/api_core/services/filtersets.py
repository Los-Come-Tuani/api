from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django_filters.filterset import FilterSet


########################################################################################


@sync_to_async
def apply_filterset(data: dict, filterset: type[FilterSet], qs: QuerySet) -> QuerySet:
    fs = filterset(data=data, queryset=qs)

    if not fs.is_valid():
        raise BadRequestError(
            field_errors={
                field: (
                    (" ".join(e.message.replace(".", ";") for e in errors.data))
                    .removesuffix(";")
                    .capitalize()
                    + "."
                )
                for field, errors in fs.errors.items()
            },
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.QUERY)

    return fs.qs
