from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_services.controllers import (
    ApplicationWithdrawController,
    BookingCancelController,
    BookingController,
    BookingDetailController,
    BookingFinishController,
    BookingStartController,
    CircuitDepartureController,
    DepartureCancelController,
    DepartureController,
    DepartureDetailController,
    GuideController,
    GuideDetailController,
    MineApplicationController,
    OpenRequestApplyController,
    OpenRequestController,
    ServiceRequestAcceptController,
    ServiceRequestCancelController,
    ServiceRequestController,
    ServiceRequestDetailController,
)

if TYPE_CHECKING:
    from typing import Final

    from api_core.controllers.base import BaseController
    from api_core.controllers.routers import URL

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")


def action(ctrl: type[BaseController], endpoint: str, tail: str) -> URL:
    return route_controller(
        ctrl=ctrl,
        endpoint=endpoint,
        instance_param=INSTANCE,
        suffix=tail,
        tail=tail,
    )


def detail(ctrl: type[BaseController], endpoint: str) -> URL:
    return route_controller(
        ctrl=ctrl,
        endpoint=endpoint,
        instance_param=INSTANCE,
        suffix="detail",
    )


router: Final[Router] = Router(
    prefix="",
    tags=["services"],
    urls=(
        # lo público
        route_controller(ctrl=GuideController, endpoint="guide"),
        detail(GuideDetailController, "guide"),
        action(CircuitDepartureController, "circuit", "departure"),
        # el guía
        route_controller(ctrl=DepartureController, endpoint="departure"),
        detail(DepartureDetailController, "departure"),
        action(DepartureCancelController, "departure", "cancel"),
        route_controller(ctrl=OpenRequestController, endpoint="open-request"),
        action(OpenRequestApplyController, "open-request", "apply"),
        route_controller(ctrl=MineApplicationController, endpoint="application/mine"),
        action(ApplicationWithdrawController, "application", "withdraw"),
        # el turista
        route_controller(ctrl=ServiceRequestController, endpoint="service-request"),
        detail(ServiceRequestDetailController, "service-request"),
        action(ServiceRequestAcceptController, "service-request", "accept"),
        action(ServiceRequestCancelController, "service-request", "cancel"),
        # las reservas
        route_controller(ctrl=BookingController, endpoint="booking"),
        detail(BookingDetailController, "booking"),
        action(BookingCancelController, "booking", "cancel"),
        action(BookingStartController, "booking", "start"),
        action(BookingFinishController, "booking", "finish"),
    ),
)
