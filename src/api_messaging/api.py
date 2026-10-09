from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_messaging.controllers import (
    BookingMessageController,
    BookingMessageReadController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

router: Final[Router] = Router(
    prefix="",
    tags=["messaging"],
    urls=(
        route_controller(
            ctrl=BookingMessageController,
            endpoint="booking",
            instance_param=("uuid", "id"),
            suffix="message",
            tail="message",
        ),
        route_controller(
            ctrl=BookingMessageReadController,
            endpoint="booking",
            instance_param=("uuid", "id"),
            suffix="message-read",
            tail="message/read",
        ),
    ),
)
