from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_reputation.controllers import (
    BookingReviewController,
    DisputeQueueController,
    DisputeResolveController,
    ReviewDisputeController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")

router: Final[Router] = Router(
    prefix="",
    tags=["reputation"],
    urls=(
        route_controller(
            ctrl=BookingReviewController,
            endpoint="booking",
            instance_param=INSTANCE,
            suffix="review",
            tail="review",
        ),
        route_controller(
            ctrl=ReviewDisputeController,
            endpoint="review",
            instance_param=INSTANCE,
            suffix="dispute",
            tail="dispute",
        ),
        route_controller(ctrl=DisputeQueueController, endpoint="review-dispute"),
        route_controller(
            ctrl=DisputeResolveController,
            endpoint="review-dispute",
            instance_param=INSTANCE,
            suffix="resolve",
            tail="resolve",
        ),
    ),
)
