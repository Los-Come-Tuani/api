from api_core.schemas.base import DTO, PermissiveDTO

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


class WebLogoutPost(PermissiveDTO, LogoutInput):
    pass
