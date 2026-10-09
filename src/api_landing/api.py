from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_landing.controllers import (
    AppReleaseController,
    AppReleaseDetailController,
    AppReleasePublishController,
    AppReleaseWithdrawController,
    DemoRequestController,
    DemoRequestDetailController,
    LatestAppReleaseController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")

router: Final[Router] = Router(
    prefix="",
    tags=["landing"],
    urls=(
        route_controller(ctrl=DemoRequestController, endpoint="demo-request"),
        route_controller(
            ctrl=DemoRequestDetailController,
            endpoint="demo-request",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(ctrl=AppReleaseController, endpoint="app-release"),
        route_controller(
            ctrl=LatestAppReleaseController, endpoint="app-release/latest"
        ),
        route_controller(
            ctrl=AppReleaseDetailController,
            endpoint="app-release",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(
            ctrl=AppReleasePublishController,
            endpoint="app-release",
            instance_param=INSTANCE,
            suffix="publish",
            tail="publish",
        ),
        route_controller(
            ctrl=AppReleaseWithdrawController,
            endpoint="app-release",
            instance_param=INSTANCE,
            suffix="withdraw",
            tail="withdraw",
        ),
    ),
)
