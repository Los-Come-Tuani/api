from typing import TYPE_CHECKING

from dmr.routing import Router

from api_catalogs.controllers.catalogs import (
    BusinessTypeListController,
    CityListController,
    CredentialTypeListController,
    InstitutionTypeListController,
    LanguageListController,
    PillarListController,
    ServiceTypeListController,
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
        route_controller(ctrl=LanguageListController, endpoint="catalog/language"),
        route_controller(
            ctrl=ServiceTypeListController,
            endpoint="catalog/service-type",
        ),
        route_controller(
            ctrl=CredentialTypeListController,
            endpoint="catalog/credential-type",
        ),
        route_controller(ctrl=PillarListController, endpoint="catalog/pillar"),
    ),
)
