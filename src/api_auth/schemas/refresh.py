from pydantic import ConfigDict

from api_auth.schemas.types import JwtToken
from api_core.schemas.base import DTO

########################################################################################


class RefreshInput(DTO):
    access: JwtToken | None = None
    refresh: JwtToken


########################################################################################


class MobileRefreshPost(RefreshInput):
    pass


########################################################################################


class MobileRefreshResponse(DTO):
    access: str
    refresh: str


########################################################################################


class WebRefreshPost(RefreshInput):
    # el navegador siempre manda también la cookie CSRF (y otras ajenas a esta acción);
    # con `extra="forbid"` el refresco web nunca funcionaría en un navegador real
    model_config = ConfigDict(extra="ignore")

    refresh: JwtToken | None = None
