from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_notifications.schemas import (
    DeviceTokenPost,
    DeviceTokenRemovePost,
    NotificationGet,
    NotificationQuery,
    PreferenceGet,
    PreferencePut,
    UnreadCountGet,
)
from api_notifications.services import (
    mark_all_read_sync,
    mark_read_sync,
    notifications_sync,
    preferences_sync,
    register_token_sync,
    remove_token_sync,
    unread_count_sync,
    update_preferences_sync,
)

########################################################################################
# La bandeja de avisos de quien está dentro, sus teléfonos y sus preferencias.


class NotificationController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[NotificationQuery],
    ) -> Paginated[NotificationGet]:
        return await sync_to_async(notifications_sync)(self.request.user, parsed_query)


class NotificationReadController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> NotificationGet:
        return await sync_to_async(mark_read_sync)(self.request.user, parsed_path.id)


class NotificationUnreadController(BaseController[CustomPydanticFastSerializer]):
    # el punto de la campana: se puede preguntar seguido
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> UnreadCountGet:
        return await sync_to_async(unread_count_sync)(self.request.user)


class NotificationReadAllController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self) -> None:
        await sync_to_async(mark_all_read_sync)(self.request.user)


class DeviceTokenController(BaseController[CustomPydanticFastSerializer]):
    # la app lo manda al iniciar sesión y cuando Firebase le da otro
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self, parsed_body: Body[DeviceTokenPost]) -> None:
        await sync_to_async(register_token_sync)(self.request.user, parsed_body)


class DeviceTokenRemoveController(BaseController[CustomPydanticFastSerializer]):
    # al cerrar sesión
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self, parsed_body: Body[DeviceTokenRemovePost]) -> None:
        await sync_to_async(remove_token_sync)(self.request.user, parsed_body.token)


class NotificationPreferenceController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[PreferenceGet]:
        return await sync_to_async(preferences_sync)(self.request.user)

    @modify(status_code=HTTPStatus.OK)
    async def put(self, parsed_body: Body[PreferencePut]) -> list[PreferenceGet]:
        return await sync_to_async(update_preferences_sync)(
            self.request.user, parsed_body
        )
