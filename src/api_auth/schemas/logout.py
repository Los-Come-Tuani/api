from pydantic import ConfigDict

from api_core.schemas.base import DTO

from .types import JwtToken

########################################################################################

type LogoutPost = MobileLogoutPost | WebLogoutPost

########################################################################################


class LogoutInput(DTO):
    access: JwtToken | None = None
    refresh: JwtToken | None = None


########################################################################################


class MobileLogoutPost(LogoutInput):
    pass


########################################################################################


class WebLogoutPost(LogoutInput):
    # ver `WebRefreshPost`: el navegador manda también la cookie CSRF
    model_config = ConfigDict(extra="ignore")
