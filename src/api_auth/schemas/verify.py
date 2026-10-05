from typing import Literal

from api_auth.enums import TokenTypes
from api_core.schemas.base import DTO, PermissiveDTO

from .types import JwtToken

########################################################################################

# un `Enum` no se valida desde el texto del JSON con los DTO estrictos; el `Literal` sí
type VerifiableTokenType = Literal[
    TokenTypes.ACCESS,
    TokenTypes.CHALLENGE,
    TokenTypes.REFRESH,
]

########################################################################################


class MobileVerifyPost(DTO):
    token: JwtToken
    type: VerifiableTokenType


########################################################################################


class WebVerifyPost(PermissiveDTO):
    access: JwtToken | None = None
    refresh: JwtToken | None = None


########################################################################################


class WebVerifyResponse(DTO):
    access: bool
    refresh: bool
