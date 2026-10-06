from typing import TYPE_CHECKING

from dmr.routing import Router

from api_catalogs.controllers.catalogs import (
    BusinessTypeListController,
    CityListController,
    InstitutionTypeListController,
)
from api_core.controllers.routers import route_controller

if TYPE_CHECKING:
    from typing import Final

########################################################################################

router: Final[Router] = Router(
    prefix="",
    tags=["catalogs"],
    urls=(
        route_controller(ctrl=CityListController, endpoint="catalog/city"),
        route_controller(
            ctrl=BusinessTypeListController,
            endpoint="catalog/business-type",
        ),
        route_controller(
            ctrl=InstitutionTypeListController,
            endpoint="catalog/institution-type",
        ),
    ),
)
