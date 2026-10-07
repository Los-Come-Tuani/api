from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_profiles.controllers.application import (
    MineProviderApplicationController,
    MineProviderProfileController,
    MineProviderRenewalController,
    MineProviderResubmitController,
    ProviderApplicationController,
)
from api_profiles.controllers.queue import (
    ProviderReasonController,
    ProviderRequestApproveController,
    ProviderRequestChangesController,
    ProviderRequestController,
    ProviderRequestDetailController,
    ProviderRequestDocumentReviewController,
    ProviderRequestRejectController,
    ProviderRequestReleaseController,
    ProviderRequestTakeController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

QUEUE: Final[str] = "provider-request"

# las acciones sobre un expediente: `provider-request/{id}/<acción>/`
ACTIONS = (
    (ProviderRequestTakeController, "take"),
    (ProviderRequestReleaseController, "release"),
    (ProviderRequestDocumentReviewController, "document-review"),
    (ProviderRequestChangesController, "request-changes"),
    (ProviderRequestApproveController, "approve"),
    (ProviderRequestRejectController, "reject"),
)

router: Final[Router] = Router(
    prefix="",
    tags=["providers"],
    urls=(
        route_controller(
            ctrl=ProviderApplicationController,
            endpoint="provider-application",
        ),
        route_controller(
            ctrl=MineProviderApplicationController,
            endpoint="provider-application/mine",
        ),
        route_controller(
            ctrl=MineProviderResubmitController,
            endpoint="provider-application/mine/resubmit",
        ),
        route_controller(
            ctrl=MineProviderRenewalController,
            endpoint="provider-application/mine/renewal",
        ),
        route_controller(
            ctrl=MineProviderProfileController,
            endpoint="provider-profile/mine",
        ),
        route_controller(ctrl=ProviderRequestController, endpoint=QUEUE),
        route_controller(ctrl=ProviderReasonController, endpoint=f"{QUEUE}/reason"),
        route_controller(
            ctrl=ProviderRequestDetailController,
            endpoint=QUEUE,
            instance_param=("uuid", "id"),
            suffix="detail",
        ),
        *(
            route_controller(
                ctrl=ctrl,
                endpoint=QUEUE,
                instance_param=("uuid", "id"),
                suffix=action,
                tail=action,
            )
            for ctrl, action in ACTIONS
        ),
    ),
)
