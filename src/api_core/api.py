from typing import TYPE_CHECKING

from dmr.openapi import build_schema
from dmr.routing import Router

import api_agenda.api
import api_auth.api
import api_catalogs.api
import api_itineraries.api
import api_moderation.api
import api_organizations.api
import api_profiles.api
import api_rewards.api
import api_territory.api

from api_core.controllers.routers import route_controllers, sort_urls
from api_core.controllers.upload import UploadController

if TYPE_CHECKING:
    from typing import Final

    from dmr.openapi.openapi import OpenAPI

########################################################################################

router: Final[Router] = Router(
    prefix="",
    urls=sort_urls((
        *api_agenda.api.router.urls,
        *api_auth.api.router.urls,
        *api_catalogs.api.router.urls,
        *api_itineraries.api.router.urls,
        *api_moderation.api.router.urls,
        *api_organizations.api.router.urls,
        *api_profiles.api.router.urls,
        *api_rewards.api.router.urls,
        *api_territory.api.router.urls,
        *route_controllers(UploadController),
    )),
)

schema: Final[OpenAPI] = build_schema(router)
