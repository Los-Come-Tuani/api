from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_territory.controllers import (
    CircuitController,
    CircuitDetailController,
    OfficialCircuitController,
    OfficialCircuitDetailController,
    PlaceController,
    PlaceDetailController,
    PlaceOwnerController,
    PlaceProfileController,
    PostController,
    PostDetailController,
    StopController,
    StopDetailController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")

router: Final[Router] = Router(
    prefix="",
    tags=["territory"],
    urls=(
        # la app: público
        route_controller(ctrl=StopController, endpoint="stop"),
        route_controller(
            ctrl=StopDetailController,
            endpoint="stop",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(ctrl=CircuitController, endpoint="circuit"),
        route_controller(
            ctrl=CircuitDetailController,
            endpoint="circuit",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        # el portal
        route_controller(ctrl=PlaceController, endpoint="place"),
        route_controller(
            ctrl=PlaceDetailController,
            endpoint="place",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(
            ctrl=PlaceOwnerController,
            endpoint="place",
            instance_param=INSTANCE,
            suffix="owner",
            tail="owner",
        ),
        route_controller(
            ctrl=PlaceProfileController,
            endpoint="place",
            instance_param=INSTANCE,
            suffix="profile",
            tail="profile",
        ),
        route_controller(ctrl=PostController, endpoint="post"),
        route_controller(
            ctrl=PostDetailController,
            endpoint="post",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(ctrl=OfficialCircuitController, endpoint="official-circuit"),
        route_controller(
            ctrl=OfficialCircuitDetailController,
            endpoint="official-circuit",
            instance_param=INSTANCE,
            suffix="detail",
        ),
    ),
)
