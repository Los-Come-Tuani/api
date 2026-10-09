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
from api_reputation.schemas import (
    DisputeGet,
    DisputePost,
    DisputeQuery,
    ResolvePost,
    ReviewGet,
    ReviewPost,
)
from api_reputation.services import (
    dispute_sync,
    disputes_sync,
    resolve_sync,
    review_sync,
)
from api_territory.controllers import as_actor

########################################################################################


class BookingReviewController(BaseController[CustomPydanticFastSerializer]):
    # el turista califica al guía y el guía al turista, una vez cada uno
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[ReviewPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ReviewGet:
        return await sync_to_async(review_sync)(
            self.request.user, parsed_path.id, parsed_body
        )


class ReviewDisputeController(BaseController[CustomPydanticFastSerializer]):
    # el reseñado pide que el equipo la revise
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[DisputePost],
        parsed_path: Path[UuidInstancePath],
    ) -> DisputeGet:
        return await sync_to_async(dispute_sync)(
            self.request.user, parsed_path.id, parsed_body.reason
        )


class DisputeQueueController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self, parsed_query: StrictQuery[DisputeQuery]
    ) -> Paginated[DisputeGet]:
        return await as_actor(self.request.user, disputes_sync, parsed_query)


class DisputeResolveController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ResolvePost],
        parsed_path: Path[UuidInstancePath],
    ) -> DisputeGet:
        return await as_actor(
            self.request.user, resolve_sync, parsed_path.id, parsed_body
        )
