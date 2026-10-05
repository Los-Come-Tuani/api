from datetime import date
from typing import Annotated

from django.utils.timezone import localdate
from pydantic import AfterValidator, Field, StringConstraints
from pydantic_core import PydanticCustomError

from api_auth.models import ApiUser
from api_core.schemas.base import DTO

from .types import Email, OneTimeCode, Password, TypedEmail, Username

########################################################################################

ADULT_AGE: int = 18

MIN_BIRTH_YEAR: int = 1900

########################################################################################


def ensure_adult(value: date) -> date:
    today: date = localdate()

    # 29 de febrero -> 28 de febrero cuando el año de hace dieciocho años no es bisiesto
    try:
        limit: date = today.replace(year=today.year - ADULT_AGE)
    except ValueError:
        limit = today.replace(day=28, year=today.year - ADULT_AGE)

    if value.year < MIN_BIRTH_YEAR:
        raise PydanticCustomError(
            "api_custom",
            "",
            {"msg": "La fecha de nacimiento no es válida."},
        )

    if value > limit:
        raise PydanticCustomError(
            "api_custom",
            "",
            {"msg": f"Debes ser mayor de {ADULT_AGE} años."},
        )

    return value


########################################################################################

# - la fecha llega como texto ISO en el JSON; el DTO estricto no la convertiría solo
type BirthDate = Annotated[
    date,
    Field(strict=False),
    AfterValidator(func=ensure_adult),
]

type FirstName = Annotated[str, StringConstraints(max_length=100, min_length=1)]

type LastName = Annotated[str, StringConstraints(max_length=100)]

# - país en ISO 3166-1 alfa-2 (`NI`, `US`...), siempre en mayúsculas
type Nationality = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Za-z]{2}$", to_upper=True),
]

type OptionalUsername = Annotated[
    Username,
    AfterValidator(func=ApiUser.normalize_username),
]

########################################################################################


class RegisterCodePost(DTO):
    email: Email


class RegisterVerifyPost(RegisterCodePost):
    code: OneTimeCode


class RegisterPost(RegisterVerifyPost):
    password: Password

    first_name: FirstName
    last_name: LastName = ""

    birth_date: BirthDate
    nationality: Nationality

    username: OptionalUsername | None = None


########################################################################################


class PasswordForgotPost(DTO):
    email: Email


class PasswordResetPost(RegisterVerifyPost):
    password: Password


class PasswordChangePost(DTO):
    current_password: Password
    password: Password


########################################################################################


class ProfilePatch(DTO):
    # El correo no está aquí a propósito: es el canal de recuperación y de avisos de
    # moderación, y cambiarlo exige otro procedimiento (RF-S-09). Mandarlo da 400.
    # Solo se aplican los campos que llegan; los valores por defecto no se usan.
    first_name: FirstName = ""
    last_name: LastName = ""
    nationality: Nationality = ""
    username: OptionalUsername | None = None


########################################################################################


class AccountClosePost(DTO):
    password: Password


class AccountRestorePost(DTO):
    email: TypedEmail
    password: Password
