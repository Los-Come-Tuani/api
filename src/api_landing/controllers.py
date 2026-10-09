from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint
from dmr.throttling import Rate

from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.mixins import PublicEndpointMixin
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.controllers.throttles import build_throttle
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_landing import services
from api_landing.schemas import (
    AppReleaseGet,
    AppReleasePatch,
    AppReleasePost,
    AppReleaseQuery,
    DemoRequestGet,
    DemoRequestPatch,
    DemoRequestPost,
    DemoRequestQuery,
    DemoRequestResult,
    LatestReleaseGet,
)
from api_territory.controllers import as_actor

########################################################################################
# Solicitudes de demo: las manda cualquiera desde la landing; la bandeja es del equipo


class DemoRequestController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self, parsed_query: StrictQuery[DemoRequestQuery]
    ) -> Paginated[DemoRequestGet]:
        return await as_actor(
            self.request.user, services.demo_requests_sync, parsed_query
        )

    # Pública a propósito: quien la pide no tiene cuenta. La acotan el límite estricto
    # de peticiones y el campo trampa. Responde con los links vigentes, también a un
    # bot.
    @modify(
        auth=None,
        status_code=HTTPStatus.OK,
        throttling=(build_throttle(10, Rate.minute),),
    )
    async def post(self, parsed_body: Body[DemoRequestPost]) -> DemoRequestResult:  # ruff: ignore[no-self-use]
        return await sync_to_async(services.submit_demo_request_sync)(parsed_body)


class DemoRequestDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> DemoRequestGet:
        return await as_actor(
            self.request.user, services.demo_request_sync, parsed_path.id
        )

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[DemoRequestPatch],
        parsed_path: Path[UuidInstancePath],
    ) -> DemoRequestGet:
        return await as_actor(
            self.request.user,
            services.update_demo_request_sync,
            parsed_path.id,
            parsed_body,
        )


########################################################################################
# Versiones de la app: ver, `releases.view`; crear, publicar y retirar,
# `releases.manage`


class AppReleaseController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self, parsed_query: StrictQuery[AppReleaseQuery]
    ) -> Paginated[AppReleaseGet]:
        return await as_actor(self.request.user, services.releases_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[AppReleasePost]) -> AppReleaseGet:
        return await as_actor(
            self.request.user, services.create_release_sync, parsed_body
        )


class AppReleaseDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[AppReleasePatch],
        parsed_path: Path[UuidInstancePath],
    ) -> AppReleaseGet:
        return await as_actor(
            self.request.user,
            services.update_release_sync,
            parsed_path.id,
            parsed_body,
        )

    # solo un borrador: una versión que ya se publicó se retira
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[UuidInstancePath]) -> None:
        await as_actor(self.request.user, services.delete_release_sync, parsed_path.id)


class AppReleasePublishController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> AppReleaseGet:
        return await as_actor(
            self.request.user, services.publish_release_sync, parsed_path.id
        )


class AppReleaseWithdrawController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> AppReleaseGet:
        return await as_actor(
            self.request.user, services.withdraw_release_sync, parsed_path.id
        )


########################################################################################
# Lo que usa la landing: público. Dice qué versiones hay, sin los links: esos se dan al
# pedir la demo.


class LatestAppReleaseController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[LatestReleaseGet]:  # ruff: ignore[no-self-use]
        return await sync_to_async(services.latest_releases_sync)()
