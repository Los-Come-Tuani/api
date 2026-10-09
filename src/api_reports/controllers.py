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
from api_reports import services
from api_reports.schemas import (
    ReportGet,
    ReportPost,
    ReportQuery,
    ReportReasonGet,
    ResolveReportPost,
    SanctionGet,
    SanctionPost,
    SanctionQuery,
)
from api_territory.controllers import as_actor

########################################################################################
# Reportar: cualquiera con sesión. La bandeja: `content.moderate` o `users.manage`.


class ReportReasonController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[ReportReasonGet]:  # ruff: ignore[no-self-use]
        return await sync_to_async(services.reasons_sync)()


class ReportController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_query: StrictQuery[ReportQuery]) -> Paginated[ReportGet]:
        return await as_actor(self.request.user, services.reports_sync, parsed_query)

    # se responde vacío: quien reporta no ve la bandeja
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self, parsed_body: Body[ReportPost]) -> None:
        await sync_to_async(services.report_sync)(self.request.user, parsed_body)


class ReportResolveController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ResolveReportPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ReportGet:
        return await as_actor(
            self.request.user,
            services.resolve_report_sync,
            parsed_path.id,
            parsed_body,
        )


########################################################################################
# Sanciones: `users.manage` (ver, también `users.view`)


class SanctionController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self, parsed_query: StrictQuery[SanctionQuery]
    ) -> Paginated[SanctionGet]:
        return await as_actor(self.request.user, services.sanctions_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[SanctionPost]) -> SanctionGet:
        return await as_actor(
            self.request.user, services.create_sanction_sync, parsed_body
        )


class SanctionLiftController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> SanctionGet:
        return await as_actor(
            self.request.user, services.lift_sanction_sync, parsed_path.id
        )
