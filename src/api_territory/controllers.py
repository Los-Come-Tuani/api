from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.mixins import PublicEndpointMixin
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_territory.schemas.circuit import (
    CircuitGet,
    CircuitInlineGet,
    CircuitPost,
    CircuitPut,
    CircuitQuery,
    PublicCircuitQuery,
)
from api_territory.schemas.place import (
    PlaceGet,
    PlaceOwnerPut,
    PlacePatch,
    PlacePost,
    PlaceProfileGet,
    PlaceProfilePut,
    PlaceQuery,
    PostGet,
    PostPatch,
    PostPost,
    PostQuery,
    StopDetailGet,
    StopGet,
    StopQuery,
)
from api_territory.services import circuits, places
from api_territory.services.access import actor_sync

if TYPE_CHECKING:
    from collections.abc import Callable

    from api_auth.models import ApiUser

########################################################################################


# Resuelve quién actúa y corre el servicio, todo en el mismo hilo síncrono.
async def as_actor[R](user: ApiUser, service: Callable[..., R], *args: object) -> R:
    def run() -> R:
        return service(actor_sync(user), *args)

    return await sync_to_async(run)()


########################################################################################
# Lo que ve la app: público, solo lo activo y lo publicado


class StopController(PublicEndpointMixin, BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_query: StrictQuery[StopQuery]) -> Paginated[StopGet]:  # ruff: ignore[no-self-use]
        return await sync_to_async(places.public_stops_sync)(parsed_query)


class StopDetailController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> StopDetailGet:  # ruff: ignore[no-self-use]
        return await sync_to_async(places.public_stop_sync)(parsed_path.id)


class CircuitController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(  # ruff: ignore[no-self-use]
        self,
        parsed_query: StrictQuery[PublicCircuitQuery],
    ) -> list[CircuitInlineGet]:
        return await sync_to_async(circuits.public_circuits_sync)(parsed_query)


class CircuitDetailController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> CircuitGet:  # ruff: ignore[no-self-use]
        return await sync_to_async(circuits.public_circuit_sync)(parsed_path.id)


########################################################################################
# Lugares (portal): el equipo con `places.view|manage` y el dueño de cada uno


class PlaceController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_query: StrictQuery[PlaceQuery]) -> Paginated[PlaceGet]:
        return await as_actor(self.request.user, places.places_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[PlacePost]) -> PlaceGet:
        return await as_actor(self.request.user, places.create_place_sync, parsed_body)


class PlaceDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> PlaceGet:
        return await as_actor(self.request.user, places.place_sync, parsed_path.id)

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[PlacePatch],
        parsed_path: Path[UuidInstancePath],
    ) -> PlaceGet:
        return await as_actor(
            self.request.user,
            places.update_place_sync,
            parsed_path.id,
            parsed_body,
        )

    # retirarlo lo saca de la app sin borrarlo
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[UuidInstancePath]) -> None:
        await as_actor(self.request.user, places.retire_place_sync, parsed_path.id)


class PlaceOwnerController(BaseController[CustomPydanticFastSerializer]):
    # qué organización administra el lugar; nula, el equipo
    @modify(status_code=HTTPStatus.OK)
    async def put(
        self,
        parsed_body: Body[PlaceOwnerPut],
        parsed_path: Path[UuidInstancePath],
    ) -> PlaceGet:
        return await as_actor(
            self.request.user,
            places.set_owner_sync,
            parsed_path.id,
            parsed_body,
        )


class PlaceProfileController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> PlaceProfileGet:
        return await as_actor(
            self.request.user,
            places.place_profile_sync,
            parsed_path.id,
        )

    # la ficha completa: lo que no llega se vacía
    @modify(status_code=HTTPStatus.OK)
    async def put(
        self,
        parsed_body: Body[PlaceProfilePut],
        parsed_path: Path[UuidInstancePath],
    ) -> PlaceProfileGet:
        return await as_actor(
            self.request.user,
            places.put_place_profile_sync,
            parsed_path.id,
            parsed_body,
        )


class PostController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_query: StrictQuery[PostQuery]) -> Paginated[PostGet]:
        return await as_actor(self.request.user, places.posts_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[PostPost]) -> PostGet:
        return await as_actor(self.request.user, places.create_post_sync, parsed_body)


class PostDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[PostPatch],
        parsed_path: Path[UuidInstancePath],
    ) -> PostGet:
        return await as_actor(
            self.request.user,
            places.update_post_sync,
            parsed_path.id,
            parsed_body,
        )

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[UuidInstancePath]) -> None:
        await as_actor(self.request.user, places.delete_post_sync, parsed_path.id)


########################################################################################
# Circuitos oficiales (portal): el equipo con `circuits.view|manage` y la alcaldía de
# cada ciudad


class OfficialCircuitController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[CircuitQuery],
    ) -> Paginated[CircuitInlineGet]:
        return await as_actor(self.request.user, circuits.circuits_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[CircuitPost]) -> CircuitGet:
        return await as_actor(
            self.request.user,
            circuits.create_circuit_sync,
            parsed_body,
        )


class OfficialCircuitDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> CircuitGet:
        return await as_actor(self.request.user, circuits.circuit_sync, parsed_path.id)

    @modify(status_code=HTTPStatus.OK)
    async def put(
        self,
        parsed_body: Body[CircuitPut],
        parsed_path: Path[UuidInstancePath],
    ) -> CircuitGet:
        return await as_actor(
            self.request.user,
            circuits.update_circuit_sync,
            parsed_path.id,
            parsed_body,
        )

    # retirarlo es definitivo (RF-A-09)
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[UuidInstancePath]) -> None:
        await as_actor(self.request.user, circuits.retire_circuit_sync, parsed_path.id)
