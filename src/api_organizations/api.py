from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_organizations.controllers.application import (
    BusinessApplicationController,
    InstitutionApplicationController,
    MineApplicationController,
    MineResubmitController,
    MunicipalityApplicationController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

router: Final[Router] = Router(
    prefix="",
    tags=["organizations"],
    urls=(
        route_controller(
            ctrl=BusinessApplicationController,
            endpoint="organization-application/business",
        ),
        route_controller(
            ctrl=InstitutionApplicationController,
            endpoint="organization-application/institution",
        ),
        route_controller(
            ctrl=MineApplicationController,
            endpoint="organization-application/mine",
        ),
        route_controller(
            ctrl=MineResubmitController,
            endpoint="organization-application/mine/resubmit",
        ),
        route_controller(
            ctrl=MunicipalityApplicationController,
            endpoint="organization-application/municipality",
        ),
    ),
)
