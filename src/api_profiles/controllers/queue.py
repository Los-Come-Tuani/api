from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_auth.catalog import FunctionalPermissions as P
from api_auth.services.roles import ensure_permission, has_any_permission
from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_moderation.schemas import ApprovePost, RejectPost
from api_profiles.schemas.queue import (
    DocumentReviewPost,
    ProviderQueueQuery,
    ProviderReasonsGet,
    ProviderRequestGet,
    ProviderRequestInlineGet,
    RequestChangesPost,
)
from api_profiles.services.queue import (
    approve_sync,
    detail_sync,
    notify_provider,
    queue_sync,
    reasons_sync,
    reject_sync,
    release_sync,
    request_changes_sync,
    review_document_sync,
    take_sync,
)

########################################################################################

# Ver la cola pide `guides.view`. Revisar (tomar, devolver, aceptar o rechazar
# documentos y pedir correcciones) pide `guides.review` o `guides.decide`; aprobar y
# rechazar al prestador, solo `guides.decide`.
REVIEW: tuple[str, ...] = (P.GUIDES_REVIEW, P.GUIDES_DECIDE)


class ProviderRequestController(BaseController[CustomPydanticFastSerializer]):
    # list, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[ProviderQueueQuery],
    ) -> Paginated[ProviderRequestInlineGet]:
        await ensure_permission(self.request.user, P.GUIDES_VIEW)

        return await sync_to_async(queue_sync)(parsed_query)


class ProviderReasonController(BaseController[CustomPydanticFastSerializer]):
    # las causas que se ofrecen al rechazar un documento o al prestador
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> ProviderReasonsGet:
        await ensure_permission(self.request.user, P.GUIDES_VIEW)

        return await sync_to_async(reasons_sync)()


class ProviderRequestDetailController(BaseController[CustomPydanticFastSerializer]):
    # retrieve, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> ProviderRequestGet:
        await ensure_permission(self.request.user, P.GUIDES_VIEW)

        return await sync_to_async(detail_sync)(parsed_path.id)


class ProviderRequestTakeController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> ProviderRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        return await sync_to_async(take_sync)(parsed_path.id, self.request.user)


class ProviderRequestReleaseController(BaseController[CustomPydanticFastSerializer]):
    # la devuelve a la cola quien la tiene, o quien decide
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> ProviderRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        return await sync_to_async(release_sync)(
            parsed_path.id,
            self.request.user,
            can_decide=await has_any_permission(self.request.user, P.GUIDES_DECIDE),
        )


class ProviderRequestDocumentReviewController(
    BaseController[CustomPydanticFastSerializer],
):
    # acepta o rechaza un documento; en una renovación, el último cierra el expediente
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[DocumentReviewPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ProviderRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        detail = await sync_to_async(review_document_sync)(
            parsed_path.id,
            self.request.user,
            parsed_body,
        )

        if detail.resolution is not None:
            await notify_provider(detail)

        return detail


class ProviderRequestChangesController(BaseController[CustomPydanticFastSerializer]):
    # algo está mal: cierra el expediente para que el prestador lo corrija
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[RequestChangesPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ProviderRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        detail = await sync_to_async(request_changes_sync)(
            parsed_path.id,
            self.request.user,
            parsed_body.note,
        )

        await notify_provider(detail)

        return detail


class ProviderRequestApproveController(BaseController[CustomPydanticFastSerializer]):
    # aprobar es lo único que hace visible al prestador y le da su rol
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ApprovePost],
        parsed_path: Path[UuidInstancePath],
    ) -> ProviderRequestGet:
        await ensure_permission(self.request.user, P.GUIDES_DECIDE)

        detail = await sync_to_async(approve_sync)(
            parsed_path.id,
            self.request.user,
            parsed_body.note,
        )

        await notify_provider(detail)

        return detail


class ProviderRequestRejectController(BaseController[CustomPydanticFastSerializer]):
    # rechazar exige un motivo: sin él, el prestador reintenta a ciegas
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[RejectPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ProviderRequestGet:
        await ensure_permission(self.request.user, P.GUIDES_DECIDE)

        detail = await sync_to_async(reject_sync)(
            parsed_path.id,
            self.request.user,
            note=parsed_body.note,
            reason_code=parsed_body.reason,
        )

        await notify_provider(detail)

        return detail
