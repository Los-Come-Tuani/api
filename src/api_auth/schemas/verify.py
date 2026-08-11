from api_auth.enums import TokenTypes
from api_core.schemas.base import DTO, PermissiveDTO

from .types import JwtToken

########################################################################################


class MobileVerifyPost(DTO):
    token: JwtToken
    type: TokenTypes


########################################################################################


class WebVerifyPost(PermissiveDTO):
    access: JwtToken | None = None
    refresh: JwtToken | None = None


########################################################################################


class WebVerifyResponse(DTO):
    access: bool
    refresh: bool
