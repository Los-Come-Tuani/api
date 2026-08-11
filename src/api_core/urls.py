from http import HTTPStatus
from typing import TYPE_CHECKING

from dmr.openapi.views import OpenAPIJsonView
from dmr.routing import path

from api_core.config import CONFIG
from api_utils.factories import build_4xx_handler, build_500_handler

from .api import router, schema
from .controllers.health import HealthCheckController
from .controllers.root import RootController

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.urls import URLPattern
    from django.urls.resolvers import URLResolver

########################################################################################

handler400 = build_4xx_handler(HTTPStatus.BAD_REQUEST)
handler403 = build_4xx_handler(HTTPStatus.FORBIDDEN)
handler404 = build_4xx_handler(HTTPStatus.NOT_FOUND)
handler500 = build_500_handler()

########################################################################################

urlpatterns: Sequence[URLPattern | URLResolver] = (
    path(
        name="api-root",
        route="",
        view=RootController.as_view(),
    ),
    path(
        name="health-check",
        route="health/",
        view=HealthCheckController.as_view(),
    ),
    path(
        name="openapi-schema",
        route="openapi/",
        view=OpenAPIJsonView.as_view(
            schema=schema,
            skip_validation=(not CONFIG.DEBUG),
        ),
    ),
    *router.urls,
)
