from api_core.schemas.base import DTO

from .session import SessionUserGet
from .types import Password, TypedEmail

########################################################################################

type LoginPost = MobileLoginPost | WebLoginPost

########################################################################################


class LoginInput(DTO):
    # sin normalizar: el servicio la normaliza para buscar y registra la original
    email: TypedEmail
    password: Password


########################################################################################


class MobileLoginPost(LoginInput):
    pass


########################################################################################


class MobileLoginResponse(DTO):
    access: str
    refresh: str
    user: SessionUserGet


########################################################################################


class WebLoginPost(LoginInput):
    pass


########################################################################################


class WebLoginResponse(DTO):
    user: SessionUserGet
