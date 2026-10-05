from typing import Annotated, Literal

from pydantic import AfterValidator, StringConstraints

from api_auth.enums import ApiUserStatus
from api_core.schemas.validators import required_email, typed_email

########################################################################################

# - correo ya normalizado (sin espacios y en minúsculas) y validado
type Email = Annotated[
    str,
    StringConstraints(max_length=254, min_length=3),
    AfterValidator(func=required_email),
]

type JwtToken = Annotated[str, StringConstraints(max_length=512, min_length=1)]

# - correo validado pero sin normalizar: el inicio de sesión registra el identificador
#   exactamente como lo tecleó la persona
type TypedEmail = Annotated[
    str,
    StringConstraints(max_length=254, min_length=3),
    AfterValidator(func=typed_email),
]

# - código de un solo uso que llega por correo
type OneTimeCode = Annotated[str, StringConstraints(pattern=r"^\d{6}$")]

type Password = Annotated[str, StringConstraints(max_length=256, min_length=1)]
type TwoFactorCode = Annotated[str, StringConstraints(max_length=32, min_length=6)]

# - un `Enum` no se valida desde el texto del JSON con los DTO estrictos, ni desde el
#   valor que trae el modelo; el `Literal` de sus miembros sí
type UserStatus = Literal[
    ApiUserStatus.ACTIVE,
    ApiUserStatus.CLOSING,
    ApiUserStatus.EXPELLED,
    ApiUserStatus.PENDING,
    ApiUserStatus.SUSPENDED,
]

type Username = Annotated[str, StringConstraints(max_length=100, min_length=1)]
