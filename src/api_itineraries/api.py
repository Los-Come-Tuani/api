from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_itineraries.controllers import ItineraryController, ItineraryDetailController

if TYPE_CHECKING:
    from typing import Final

########################################################################################

router: Final[Router] = Router(
    prefix="",
    tags=["itineraries"],
    urls=(
        route_controller(ctrl=ItineraryController, endpoint="itinerary"),
        route_controller(
            ctrl=ItineraryDetailController,
            endpoint="itinerary",
            instance_param=("uuid", "id"),
            suffix="detail",
        ),
    ),
)
