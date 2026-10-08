from http import HTTPStatus

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify

from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.path import UuidInstancePath
from api_messaging.schemas import MessageGet, MessagePost, MessageQuery
from api_messaging.services import mark_read_sync, messages_sync, send_sync

########################################################################################
# El chat de una reserva: solo el turista y el guía. La app pregunta cada pocos
# segundos por lo posterior al último mensaje que tiene (`after`).


class BookingMessageController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_path: Path[UuidInstancePath],
        parsed_query: StrictQuery[MessageQuery],
    ) -> list[MessageGet]:
        return await sync_to_async(messages_sync)(
            self.request.user, parsed_path.id, parsed_query.after
        )

    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[MessagePost],
        parsed_path: Path[UuidInstancePath],
    ) -> MessageGet:
        return await sync_to_async(send_sync)(
            self.request.user, parsed_path.id, parsed_body.body
        )


class BookingMessageReadController(BaseController[CustomPydanticFastSerializer]):
    # quien pregunta leyó todo lo que hay
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> None:
        await sync_to_async(mark_read_sync)(self.request.user, parsed_path.id)
