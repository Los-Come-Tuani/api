from os import environ
from typing import TYPE_CHECKING

from django.core.asgi import get_asgi_application

if TYPE_CHECKING:
    from django.core.handlers.asgi import ASGIHandler

########################################################################################

environ.setdefault("DJANGO_SETTINGS_MODULE", "api_core.settings")

application: ASGIHandler = get_asgi_application()
