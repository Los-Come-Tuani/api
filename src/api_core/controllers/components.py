from typing import Annotated, TypeVar, override

from django.http import QueryDict
from dmr import Controller
from dmr.components import QueryComponent
from dmr.endpoint import Endpoint

from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError

########################################################################################


class StrictQueryComponent(QueryComponent):
    __slots__ = ()

    @override
    def provide_context_data(
        self,
        endpoint: Endpoint,
        controller: Controller,
        *,
        field_model,  # ruff: ignore[missing-type-function-argument]
    ) -> dict:
        params: QueryDict = controller.request.GET

        force_list: frozenset[str] = getattr(
            field_model,
            "__dmr_force_list__",
            frozenset(),
        )

        repeated: dict[str, str] = {
            name: "Este parámetro solo puede especificarse una vez."
            for name in params
            if name not in force_list and len(params.getlist(name)) > 1
        }

        if repeated:
            raise BadRequestError(
                field_errors=repeated,
                type=BadRequestErrorTypes.FAILED_VALIDATION,
            ).scoped(RequestScopes.QUERY)

        return super().provide_context_data(
            endpoint,
            controller,
            field_model=field_model,
        )


########################################################################################

# mantener con sintaxis de python 3.12 pq si no todo explota y morimos
T = TypeVar("T")

StrictQuery = Annotated[T, StrictQueryComponent()]
