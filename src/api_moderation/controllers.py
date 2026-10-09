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
from api_moderation.schemas import (
    ApprovePost,
    RejectPost,
    RejectionReasonGet,
    VerificationQuery,
    VerificationRequestGet,
    VerificationRequestInlineGet,
)
from api_moderation.services import (
    detail_sync,
    notify_applicant,
    queue_sync,
    rejection_reasons_sync,
    release_sync,
    resolve_sync,
    take_sync,
)

########################################################################################

# Ver la cola pide `organizations.view`. Atender un expediente (tomarlo, devolverlo,
# aprobar o rechazar) pide `organizations.review` o `organizations.manage`.
REVIEW: tuple[str, ...] = (P.ORGANIZATIONS_REVIEW, P.ORGANIZATIONS_MANAGE)


class VerificationRequestController(BaseController[CustomPydanticFastSerializer]):
    # list, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[VerificationQuery],
    ) -> Paginated[VerificationRequestInlineGet]:
        await ensure_permission(self.request.user, P.ORGANIZATIONS_VIEW)

        return await sync_to_async(queue_sync)(parsed_query)


class VerificationReasonController(BaseController[CustomPydanticFastSerializer]):
    # las causas que se ofrecen al rechazar, para armar el formulario
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[RejectionReasonGet]:
        await ensure_permission(self.request.user, *REVIEW, P.ORGANIZATIONS_VIEW)

        return await sync_to_async(rejection_reasons_sync)()


class VerificationRequestDetailController(
    BaseController[CustomPydanticFastSerializer],
):
    # retrieve, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> VerificationRequestGet:
        await ensure_permission(self.request.user, P.ORGANIZATIONS_VIEW)

        return await sync_to_async(detail_sync)(parsed_path.id)


class VerificationRequestTakeController(BaseController[CustomPydanticFastSerializer]):
    # la toma el moderador: queda en revisión y a su nombre
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> VerificationRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        return await sync_to_async(take_sync)(parsed_path.id, self.request.user)


class VerificationRequestReleaseController(
    BaseController[CustomPydanticFastSerializer],
):
    # la devuelve a la cola quien la tiene, o quien administra las organizaciones
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> VerificationRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        return await sync_to_async(release_sync)(
            parsed_path.id,
            self.request.user,
            can_manage=await has_any_permission(
                self.request.user,
                P.ORGANIZATIONS_MANAGE,
            ),
        )


class VerificationRequestApproveController(
    BaseController[CustomPydanticFastSerializer],
):
    # aprobar es lo único que hace visible a la organización
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ApprovePost],
        parsed_path: Path[UuidInstancePath],
    ) -> VerificationRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        detail = await sync_to_async(resolve_sync)(
            parsed_path.id,
            self.request.user,
            approved=True,
            can_manage=await has_any_permission(
                self.request.user,
                P.ORGANIZATIONS_MANAGE,
            ),
            note=parsed_body.note,
            reason_code=None,
        )

        await notify_applicant(detail)

        return detail


class VerificationRequestRejectController(
    BaseController[CustomPydanticFastSerializer],
):
    # rechazar exige un motivo: sin él, quien se postuló reintenta a ciegas
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[RejectPost],
        parsed_path: Path[UuidInstancePath],
    ) -> VerificationRequestGet:
        await ensure_permission(self.request.user, *REVIEW)

        detail = await sync_to_async(resolve_sync)(
            parsed_path.id,
            self.request.user,
            approved=False,
            can_manage=await has_any_permission(
                self.request.user,
                P.ORGANIZATIONS_MANAGE,
            ),
            note=parsed_body.note,
            reason_code=parsed_body.reason,
        )

        await notify_applicant(detail)

        return detail
