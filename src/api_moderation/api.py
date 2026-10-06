from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_moderation.controllers import (
    VerificationReasonController,
    VerificationRequestApproveController,
    VerificationRequestController,
    VerificationRequestDetailController,
    VerificationRequestRejectController,
    VerificationRequestReleaseController,
    VerificationRequestTakeController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

ENDPOINT: Final[str] = "verification-request"

router: Final[Router] = Router(
    prefix="",
    tags=["moderation"],
    urls=(
        route_controller(ctrl=VerificationRequestController, endpoint=ENDPOINT),
        route_controller(
            ctrl=VerificationReasonController,
            endpoint=f"{ENDPOINT}/reason",
        ),
        route_controller(
            ctrl=VerificationRequestDetailController,
            endpoint=ENDPOINT,
            instance_param=("uuid", "id"),
            suffix="detail",
        ),
        route_controller(
            ctrl=VerificationRequestTakeController,
            endpoint=ENDPOINT,
            instance_param=("uuid", "id"),
            suffix="take",
            tail="take",
        ),
        route_controller(
            ctrl=VerificationRequestReleaseController,
            endpoint=ENDPOINT,
            instance_param=("uuid", "id"),
            suffix="release",
            tail="release",
        ),
        route_controller(
            ctrl=VerificationRequestApproveController,
            endpoint=ENDPOINT,
            instance_param=("uuid", "id"),
            suffix="approve",
            tail="approve",
        ),
        route_controller(
            ctrl=VerificationRequestRejectController,
            endpoint=ENDPOINT,
            instance_param=("uuid", "id"),
            suffix="reject",
            tail="reject",
        ),
    ),
)
