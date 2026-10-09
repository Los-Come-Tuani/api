from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_core.controllers.base import BaseController
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.path import UuidInstancePath
from api_itineraries.schemas import ItineraryGet, ItineraryPatch, ItineraryPost
from api_itineraries.services import (
    create_itinerary_sync,
    delete_itinerary_sync,
    itineraries_sync,
    itinerary_sync,
    update_itinerary_sync,
)

########################################################################################
# Los itinerarios de quien está dentro ("Mi circuito" de la app): cada quien ve y
# cambia solo los suyos; el de otra persona responde 404.


class ItineraryController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[ItineraryGet]:
        return await sync_to_async(itineraries_sync)(self.request.user)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[ItineraryPost]) -> ItineraryGet:
        return await sync_to_async(create_itinerary_sync)(
            self.request.user, parsed_body
        )


class ItineraryDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> ItineraryGet:
        return await sync_to_async(itinerary_sync)(self.request.user, parsed_path.id)

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[ItineraryPatch],
        parsed_path: Path[UuidInstancePath],
    ) -> ItineraryGet:
        return await sync_to_async(update_itinerary_sync)(
            self.request.user,
            parsed_path.id,
            parsed_body,
        )

    # baja lógica: la fila se conserva para las métricas del circuito
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[UuidInstancePath]) -> None:
        await sync_to_async(delete_itinerary_sync)(self.request.user, parsed_path.id)
