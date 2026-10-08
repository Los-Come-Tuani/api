from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_reports.controllers import (
    ReportController,
    ReportReasonController,
    ReportResolveController,
    SanctionController,
    SanctionLiftController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")

router: Final[Router] = Router(
    prefix="",
    tags=["reports"],
    urls=(
        route_controller(ctrl=ReportReasonController, endpoint="report/reason"),
        route_controller(ctrl=ReportController, endpoint="report"),
        route_controller(
            ctrl=ReportResolveController,
            endpoint="report",
            instance_param=INSTANCE,
            suffix="resolve",
            tail="resolve",
        ),
        route_controller(ctrl=SanctionController, endpoint="sanction"),
        route_controller(
            ctrl=SanctionLiftController,
            endpoint="sanction",
            instance_param=INSTANCE,
            suffix="lift",
            tail="lift",
        ),
    ),
)
