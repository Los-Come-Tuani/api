from datetime import datetime, time
from decimal import Decimal
from re import fullmatch
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from api_auth.schemas.account import FirstName, LastName
from api_auth.schemas.session import SessionUserGet
from api_auth.schemas.types import Email, OneTimeCode, Password
from api_core.schemas.base import DTO

########################################################################################

# - un UUID llega como texto en el JSON, y el DTO estricto no lo convertiría solo
type Reference = Annotated[UUID, Field(strict=False)]


def check_ruc(value: str) -> str:
    # provisional: el formato oficial del RUC no está definido en ninguna fuente
    ruc: str = value.upper()

    if fullmatch(r"[A-Z0-9-]{13,16}", ruc) is None:
        raise ValueError("El RUC debe tener de 13 a 16 letras, números o guiones.")

    return ruc


type Ruc = Annotated[
    str, StringConstraints(strip_whitespace=True), AfterValidator(check_ruc)
]

type Phone = Annotated[str, StringConstraints(pattern=r"^[0-9+()\- ]{7,30}$")]

# - el territorio nicaragüense (el mismo rango que verifica la base)
type Latitude = Annotated[
    Decimal,
    Field(
        strict=False,
        ge=Decimal("10.7"),
        le=Decimal("15.1"),
        max_digits=9,
        decimal_places=6,
    ),
]
type Longitude = Annotated[
    Decimal,
    Field(
        strict=False,
        ge=Decimal("-87.7"),
        le=Decimal("-82.6"),
        max_digits=9,
        decimal_places=6,
    ),
]

type Clock = Annotated[time, Field(strict=False)]

type OrganizationKind = Literal["business", "institution", "municipality"]

########################################################################################
# Lo que manda quien se postula


# La persona que se postula y su cuenta. El código es el que llegó al correo (el mismo
# que pide el registro de la app: `POST /auth/register-code/`).
class ApplicantPost(DTO):
    email: Email
    code: OneTimeCode
    password: Password
    first_name: FirstName
    last_name: LastName = ""


class HoursPost(DTO):
    # 0 es domingo, 6 es sábado
    weekday: Annotated[int, Field(ge=0, le=6)]
    closed: bool = False
    # un cierre anterior a la apertura significa madrugada
    opens: Clock | None = None
    closes: Clock | None = None

    @model_validator(mode="after")
    def check_hours(self) -> Self:
        if self.closed and (self.opens is not None or self.closes is not None):
            raise ValueError("Un día cerrado no lleva horario.")

        if not self.closed:
            if self.opens is None or self.closes is None:
                raise ValueError(
                    "Un día abierto necesita la hora de apertura y de cierre."
                )

            if self.opens == self.closes:
                raise ValueError(
                    "La hora de apertura y la de cierre no pueden ser la misma."
                )

        return self


class SignatureDishPost(DTO):
    name: Annotated[str, StringConstraints(max_length=150, min_length=1)]
    description: Annotated[str, StringConstraints(max_length=1000)] = ""
    reference_price: Annotated[
        Decimal,
        Field(strict=False, gt=Decimal(0), max_digits=12, decimal_places=2),
    ]
    # el código ISO de la moneda (`NIO`, `USD`)
    currency: Annotated[
        str, StringConstraints(max_length=3, min_length=3, to_upper=True)
    ]
    # la clave que devolvió `POST /upload/` para la foto del platillo
    photo_key: Annotated[str, StringConstraints(max_length=255, min_length=1)]


class BusinessData(DTO):
    city_id: Reference
    business_type_id: Reference
    ruc: Ruc
    name: Annotated[str, StringConstraints(max_length=150, min_length=1)]
    address: Annotated[str, StringConstraints(max_length=255, min_length=1)]
    phone: Phone
    alternate_phone: Annotated[
        str, StringConstraints(pattern=r"^([0-9+()\- ]{7,30})?$")
    ] = ""
    latitude: Latitude
    longitude: Longitude
    hours: Annotated[list[HoursPost], Field(max_length=7)]
    signature_dish: SignatureDishPost

    @field_validator("hours")
    @classmethod
    def check_one_row_per_weekday(cls, value: list[HoursPost]) -> list[HoursPost]:
        days: list[int] = [row.weekday for row in value]

        if len(days) != len(set(days)):
            raise ValueError("Cada día de la semana va una sola vez.")

        return value


class InstitutionData(DTO):
    city_id: Reference
    institution_type_id: Reference
    name: Annotated[str, StringConstraints(max_length=150, min_length=1)]
    contact_email: Email
    phone: Phone
    # la clave que devolvió `POST /upload/` para el documento de existencia legal
    document_key: Annotated[str, StringConstraints(max_length=255, min_length=1)]


class MunicipalityData(DTO):
    city_id: Reference
    # el nombre oficial de la alcaldía
    name: Annotated[str, StringConstraints(max_length=150, min_length=1)]
    contact_email: Email
    phone: Phone
    # la clave que devolvió `POST /upload/` para el documento que acredita la
    # representación de quien solicita
    document_key: Annotated[str, StringConstraints(max_length=255, min_length=1)]


class BusinessApplicationPost(ApplicantPost, BusinessData):
    pass


class InstitutionApplicationPost(ApplicantPost, InstitutionData):
    pass


class MunicipalityApplicationPost(ApplicantPost, MunicipalityData):
    pass


########################################################################################
# Lo que recibe


class ReasonGet(DTO):
    code: str
    label: str


class ResolutionGet(DTO):
    approved: bool
    # solo al rechazar
    reason: ReasonGet | None
    # lo que el equipo le comunica a quien se postuló
    note: str
    resolved_at: datetime


class ApplicationGet(DTO):
    """La solicitud de una organización: lo que ve quien se postuló."""

    id: UUID
    kind: OrganizationKind
    organization_id: UUID
    organization_name: str
    # `submitted` y `in_review` están en la bandeja del equipo; los otros cierran el
    # expediente
    status: Literal["submitted", "in_review", "approved", "rejected"]
    submitted_at: datetime
    resolved_at: datetime | None
    # nulo mientras no se resuelve
    resolution: ResolutionGet | None


class ApplicationSessionResponse(DTO):
    # la sesión queda abierta en las cookies: quien se postula entra con acceso limitado
    # a su solicitud mientras el equipo la revisa
    user: SessionUserGet
    application: ApplicationGet
