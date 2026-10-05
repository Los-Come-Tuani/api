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


def required_email(value: str) -> str:
    # el correo es el identificador de acceso: se guarda y se busca en minúsculas
    normalized: str = value.strip().lower()

    typed_email(normalized)

    return normalized


def typed_email(value: str) -> str:
    # valida el formato pero devuelve el texto tal cual llegó: el registro de intentos
    # de acceso guarda el identificador "tal como se tecleó" (RF-S-06)
    try:
        EMAIL_ADAPTER.validate_python(value.strip().lower())
    except PydanticValidationError as p:
        raise PydanticCustomError(
            "api_custom",
            "",
            {"msg": "Debe ser un correo válido."},
        ) from p

    return value


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
