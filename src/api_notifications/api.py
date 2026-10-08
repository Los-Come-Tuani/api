from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_notifications.controllers import (
    DeviceTokenController,
    DeviceTokenRemoveController,
    NotificationController,
    NotificationPreferenceController,
    NotificationReadAllController,
    NotificationReadController,
    NotificationUnreadController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

router: Final[Router] = Router(
    prefix="",
    tags=["notifications"],
    urls=(
        route_controller(ctrl=NotificationController, endpoint="notification"),
        route_controller(
            ctrl=NotificationReadAllController,
            endpoint="notification/read-all",
        ),
        route_controller(
            ctrl=NotificationUnreadController,
            endpoint="notification/unread",
        ),
        route_controller(
            ctrl=NotificationReadController,
            endpoint="notification",
            instance_param=("uuid", "id"),
            suffix="read",
            tail="read",
        ),
        route_controller(
            ctrl=NotificationPreferenceController,
            endpoint="notification-preference",
        ),
        route_controller(ctrl=DeviceTokenController, endpoint="device-token"),
        route_controller(
            ctrl=DeviceTokenRemoveController,
            endpoint="device-token/remove",
        ),
    ),
)
