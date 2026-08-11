from typing import TYPE_CHECKING

from dmr.openapi import build_schema
from dmr.routing import Router

import api_auth.api

from api_core.controllers.routers import sort_urls

if TYPE_CHECKING:
    from typing import Final

    from dmr.openapi.openapi import OpenAPI

########################################################################################

router: Final[Router] = Router(
    prefix="",
    urls=sort_urls((*api_auth.api.router.urls,)),
)

schema: Final[OpenAPI] = build_schema(router)
