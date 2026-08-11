from typing import Final

from pydantic import (
    EmailStr,
    HttpUrl,
    TypeAdapter,
    ValidationError as PydanticValidationError,
)
from pydantic_core import PydanticCustomError

########################################################################################

EMAIL_ADAPTER: Final[TypeAdapter[EmailStr]] = TypeAdapter(EmailStr)
URL_ADAPTER: Final[TypeAdapter[HttpUrl]] = TypeAdapter(HttpUrl)

########################################################################################


def empty_or_email(value: str) -> str:
    if value:
        try:
            EMAIL_ADAPTER.validate_python(value)
        except PydanticValidationError as p:
            raise PydanticCustomError(
                "api_custom",
                "",
                {"msg": "Debe ser un correo válido."},
            ) from p

    return value


########################################################################################


def empty_or_url(value: str) -> str:
    if value:
        try:
            URL_ADAPTER.validate_python(value)
        except PydanticValidationError as p:
            raise PydanticCustomError(
                "api_custom",
                "",
                {"msg": "Debe ser un URL válido."},
            ) from p

    return value
