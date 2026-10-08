from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_agenda import services
from api_agenda.schemas import (
    CancelPost,
    ClonePost,
    EventGet,
    EventPatch,
    EventPost,
    EventQuery,
    HidePost,
    ManagedEventGet,
    PublicEventQuery,
)
from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.mixins import PublicEndpointMixin
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_territory.controllers import as_actor

########################################################################################
# La agenda de la app: pública, lo próximo y lo que está en curso


class EventController(
    PublicEndpointMixin, BaseController[CustomPydanticFastSerializer]
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(  # ruff: ignore[no-self-use]
        self,
        parsed_query: StrictQuery[PublicEventQuery],
    ) -> Paginated[EventGet]:
        return await sync_to_async(services.public_events_sync)(parsed_query)


class EventDetailController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> EventGet:  # ruff: ignore[no-self-use]
        return await sync_to_async(services.public_event_sync)(parsed_path.id)


########################################################################################
# La agenda del portal: la institución o la alcaldía, lo suyo; el equipo con
# `content.moderate`, todo y la moderación


class CulturalEventController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[EventQuery],
    ) -> Paginated[ManagedEventGet]:
        return await as_actor(self.request.user, services.events_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[EventPost]) -> ManagedEventGet:
        return await as_actor(
            self.request.user,
            services.create_event_sync,
            parsed_body,
        )


class CulturalEventDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> ManagedEventGet:
        return await as_actor(self.request.user, services.event_sync, parsed_path.id)

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[EventPatch],
        parsed_path: Path[UuidInstancePath],
    ) -> ManagedEventGet:
        return await as_actor(
            self.request.user,
            services.update_event_sync,
            parsed_path.id,
            parsed_body,
        )


class CulturalEventCancelController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[CancelPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ManagedEventGet:
        return await as_actor(
            self.request.user,
            services.cancel_event_sync,
            parsed_path.id,
            parsed_body.reason,
        )


class CulturalEventCloneController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[ClonePost],
        parsed_path: Path[UuidInstancePath],
    ) -> ManagedEventGet:
        return await as_actor(
            self.request.user,
            services.clone_event_sync,
            parsed_path.id,
            parsed_body,
        )


class CulturalEventHideController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[HidePost],
        parsed_path: Path[UuidInstancePath],
    ) -> ManagedEventGet:
        return await as_actor(
            self.request.user,
            services.hide_event_sync,
            parsed_path.id,
            parsed_body.reason,
        )


class CulturalEventShowController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> ManagedEventGet:
        return await as_actor(
            self.request.user, services.show_event_sync, parsed_path.id
        )
