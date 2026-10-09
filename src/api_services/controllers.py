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
from api_services.schemas import (
    AcceptPost,
    ApplicationGet,
    ApplyPost,
    BookingGet,
    BookingPost,
    DepartureGet,
    DeparturePatch,
    DeparturePost,
    GuideCardGet,
    GuideDetailGet,
    GuideQuery,
    OpenRequestGet,
    RequestGet,
    RequestPost,
    ServiceCancelPost,
)
from api_services.services import bookings, departures, guides, requests
from api_territory.controllers import as_actor
from api_territory.services.circuits import visible_circuit

if TYPE_CHECKING:
    from uuid import UUID

    from api_territory.services.access import Actor

########################################################################################
# Lo público: los guías aprobados y las salidas de un circuito


class GuideController(
    PublicEndpointMixin, BaseController[CustomPydanticFastSerializer]
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(  # ruff: ignore[no-self-use]
        self,
        parsed_query: StrictQuery[GuideQuery],
    ) -> Paginated[GuideCardGet]:
        return await sync_to_async(guides.guides_sync)(parsed_query)


class GuideDetailController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> GuideDetailGet:  # ruff: ignore[no-self-use]
        return await sync_to_async(guides.guide_sync)(parsed_path.id)


class CircuitDepartureController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    # los próximos horarios de guía de un circuito oficial
    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> list[DepartureGet]:  # ruff: ignore[no-self-use]
        return await sync_to_async(guides.circuit_departures_sync)(parsed_path.id)


def official_departures(actor: Actor, circuit_id: UUID) -> list[DepartureGet]:
    return departures.official_departures_sync(visible_circuit(actor, circuit_id))


class OfficialCircuitDepartureController(BaseController[CustomPydanticFastSerializer]):
    # el portal: las salidas de un circuito que ve, aunque ya no esté publicado
    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> list[DepartureGet]:
        return await as_actor(self.request.user, official_departures, parsed_path.id)


########################################################################################
# El guía: sus salidas, las convocatorias abiertas y sus postulaciones


class DepartureController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[DepartureGet]:
        return await sync_to_async(departures.departures_sync)(self.request.user)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[DeparturePost]) -> DepartureGet:
        return await sync_to_async(departures.create_departure_sync)(
            self.request.user, parsed_body
        )


class DepartureDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[DeparturePatch],
        parsed_path: Path[UuidInstancePath],
    ) -> DepartureGet:
        return await sync_to_async(departures.update_departure_sync)(
            self.request.user, parsed_path.id, parsed_body
        )


class DepartureCancelController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ServiceCancelPost],
        parsed_path: Path[UuidInstancePath],
    ) -> DepartureGet:
        return await sync_to_async(departures.cancel_departure_sync)(
            self.request.user, parsed_path.id, parsed_body.reason
        )


class OpenRequestController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[OpenRequestGet]:
        return await sync_to_async(requests.open_requests_sync)(self.request.user)


class OpenRequestApplyController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[ApplyPost],
        parsed_path: Path[UuidInstancePath],
    ) -> ApplicationGet:
        return await sync_to_async(requests.apply_sync)(
            self.request.user, parsed_path.id, parsed_body
        )


class MineApplicationController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[ApplicationGet]:
        return await sync_to_async(requests.own_applications_sync)(self.request.user)


class ApplicationWithdrawController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> ApplicationGet:
        return await sync_to_async(requests.withdraw_application_sync)(
            self.request.user, parsed_path.id
        )


########################################################################################
# El turista: sus convocatorias


class ServiceRequestController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[RequestGet]:
        return await sync_to_async(requests.requests_sync)(self.request.user)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[RequestPost]) -> RequestGet:
        return await sync_to_async(requests.create_request_sync)(
            self.request.user, parsed_body
        )


class ServiceRequestDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> RequestGet:
        return await sync_to_async(requests.request_sync)(
            self.request.user, parsed_path.id
        )


class ServiceRequestAcceptController(BaseController[CustomPydanticFastSerializer]):
    # elegir una postulación crea la reserva
    @modify(status_code=HTTPStatus.CREATED)
    async def post(
        self,
        parsed_body: Body[AcceptPost],
        parsed_path: Path[UuidInstancePath],
    ) -> BookingGet:
        return await sync_to_async(requests.accept_application_sync)(
            self.request.user, parsed_path.id, parsed_body
        )


class ServiceRequestCancelController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> RequestGet:
        return await sync_to_async(requests.cancel_request_sync)(
            self.request.user, parsed_path.id
        )


########################################################################################
# Las reservas: del turista y del guía


class BookingController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[BookingGet]:
        return await sync_to_async(bookings.bookings_sync)(self.request.user)

    # reservar una salida de un guía
    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[BookingPost]) -> BookingGet:
        return await sync_to_async(bookings.book_departure_sync)(
            self.request.user, parsed_body
        )


class BookingDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> BookingGet:
        return await sync_to_async(bookings.booking_sync)(
            self.request.user, parsed_path.id
        )


class BookingCancelController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ServiceCancelPost],
        parsed_path: Path[UuidInstancePath],
    ) -> BookingGet:
        return await sync_to_async(bookings.cancel_booking_sync)(
            self.request.user, parsed_path.id, parsed_body.reason
        )


class BookingStartController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> BookingGet:
        return await sync_to_async(bookings.start_booking_sync)(
            self.request.user, parsed_path.id
        )


class BookingFinishController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_path: Path[UuidInstancePath]) -> BookingGet:
        return await sync_to_async(bookings.finish_booking_sync)(
            self.request.user, parsed_path.id
        )
