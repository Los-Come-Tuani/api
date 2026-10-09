from typing import TYPE_CHECKING

from dmr.routing import Router

from api_agenda.controllers import (
    CulturalEventCancelController,
    CulturalEventCloneController,
    CulturalEventController,
    CulturalEventDetailController,
    CulturalEventHideController,
    CulturalEventShowController,
    EventController,
    EventDetailController,
)
from api_core.controllers.routers import route_controller

if TYPE_CHECKING:
    from typing import Final

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")
MANAGED: Final[str] = "cultural-event"

# las acciones sobre un evento del portal: `cultural-event/{id}/<acción>/`
ACTIONS = (
    (CulturalEventCancelController, "cancel"),
    (CulturalEventCloneController, "clone"),
    (CulturalEventHideController, "hide"),
    (CulturalEventShowController, "show"),
)

router: Final[Router] = Router(
    prefix="",
    tags=["agenda"],
    urls=(
        route_controller(ctrl=EventController, endpoint="event"),
        route_controller(
            ctrl=EventDetailController,
            endpoint="event",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(ctrl=CulturalEventController, endpoint=MANAGED),
        route_controller(
            ctrl=CulturalEventDetailController,
            endpoint=MANAGED,
            instance_param=INSTANCE,
            suffix="detail",
        ),
        *(
            route_controller(
                ctrl=ctrl,
                endpoint=MANAGED,
                instance_param=INSTANCE,
                suffix=action,
                tail=action,
            )
            for ctrl, action in ACTIONS
        ),
    ),
)
