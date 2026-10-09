from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from django.utils.timezone import localdate
from pydantic import Field, StringConstraints, field_validator, model_validator

from api_auth.schemas.account import BirthDate, FirstName, LastName, Nationality
from api_auth.schemas.session import SessionUserGet
from api_auth.schemas.types import Email, OneTimeCode, Password
from api_core.schemas.base import DTO
from api_organizations.schemas.application import Phone, ReasonGet, ResolutionGet

########################################################################################

# - un UUID y una fecha llegan como texto en el JSON, y el DTO estricto no los
#   convertiría solos
type Reference = Annotated[UUID, Field(strict=False)]
type Day = Annotated[date, Field(strict=False)]

type ServiceCode = Literal["guia", "traductor"]
type LevelName = Literal["basic", "intermediate", "advanced", "native"]
type FileKey = Annotated[str, StringConstraints(max_length=255, min_length=1)]

type RequestStatus = Literal["submitted", "in_review", "approved", "rejected"]
type ProcedureName = Literal["application", "renewal"]
type ProviderStatusName = Literal["unaccredited", "in_review", "active", "suspended"]
type CredentialStatusName = Literal[
    "uploaded",
    "in_review",
    "approved",
    "rejected",
    "expired",
    "replaced",
]

########################################################################################
# Lo que manda quien se postula


class LanguagePost(DTO):
    # ISO 639-1 (`es`, `en`...)
    code: Annotated[
        str,
        StringConstraints(max_length=8, min_length=2, to_lower=True),
    ]
    level: LevelName


# Un documento con sus fechas y el archivo ya subido (`POST /upload/` con `kind`
# `provider-document`).
class DocumentPost(DTO):
    # el código del tipo (`cedula`, `licencia_intur`...), de
    # `GET /catalog/credential-type/`
    type: Annotated[str, StringConstraints(max_length=40, min_length=1)]
    # el folio del documento
    number: Annotated[
        str,
        StringConstraints(max_length=60, min_length=1, strip_whitespace=True),
    ]
    issued_on: Day
    # obligatoria en los tipos que vencen
    expires_on: Day | None = None
    file_key: FileKey

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        today: date = localdate()

        if self.issued_on > today:
            raise ValueError("La fecha de emisión no puede ser futura.")

        if self.expires_on is not None:
            if self.expires_on <= self.issued_on:
                raise ValueError("El vencimiento tiene que ser posterior a la emisión.")

            if self.expires_on <= today:
                raise ValueError("El documento ya venció: sube uno vigente.")

        return self


# Lo que el prestador declara de sí: lo mismo al postularse y al corregir.
class ProfileData(DTO):
    services: Annotated[list[ServiceCode], Field(max_length=2, min_length=1)]
    # nulo es todo el país
    city_id: Reference | None = None
    phone: Phone
    presentation: Annotated[
        str,
        StringConstraints(max_length=1000, strip_whitespace=True),
    ] = ""
    languages: Annotated[list[LanguagePost], Field(max_length=20, min_length=1)]
    # lleva turistas en su vehículo: se le piden licencia de conducir y seguro
    carries_tourists: bool = False

    @field_validator("services")
    @classmethod
    def check_services(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Cada servicio va una sola vez.")

        return value

    @field_validator("languages")
    @classmethod
    def check_languages(cls, value: list[LanguagePost]) -> list[LanguagePost]:
        codes: list[str] = [item.code for item in value]

        if len(codes) != len(set(codes)):
            raise ValueError("Cada idioma va una sola vez.")

        return value


class ProviderApplicationPost(ProfileData):
    # la cuenta: el código es el que llegó al correo (`POST /auth/register-code/`)
    email: Email
    code: OneTimeCode
    password: Password
    first_name: FirstName
    last_name: LastName = ""
    birth_date: BirthDate
    nationality: Nationality

    # uno por cada tipo que se le pide, y ninguno más
    documents: Annotated[list[DocumentPost], Field(max_length=10, min_length=1)]


# Corregir lo rechazado: los datos del perfil y, en `documents`, solo lo que se sube
# otra vez. Lo aceptado pasa tal cual al expediente nuevo.
class ProviderResubmitPost(ProfileData):
    documents: Annotated[list[DocumentPost], Field(max_length=10)] = Field(
        default_factory=list
    )


class ProviderRenewalPost(DTO):
    documents: Annotated[list[DocumentPost], Field(max_length=10, min_length=1)]


########################################################################################
# Lo que recibe


class OptionRef(DTO):
    code: str
    label: str


class FileGet(DTO):
    # la clave se manda de vuelta tal cual si no se cambia el archivo
    key: str
    # vence en minutos; nula si el almacenamiento no está configurado
    url: str | None


class ReviewGet(DTO):
    accepted: bool
    # solo al rechazar
    reason: ReasonGet | None
    note: str
    reviewed_at: datetime


class CredentialGet(DTO):
    id: UUID
    type: OptionRef
    number: str
    issued_on: date
    expires_on: date | None
    file: FileGet
    status: CredentialStatusName
    # lo que dijo quien revisó; nulo mientras nadie lo revisa
    review: ReviewGet | None
    uploaded_at: datetime


class LanguageLevelGet(DTO):
    code: str
    level: LevelName


class ProfileDataGet(DTO):
    # con la forma del reenvío: el formulario de corrección se llena con esto
    services: list[str]
    city_id: UUID | None
    phone: str
    presentation: str
    languages: list[LanguageLevelGet]
    carries_tourists: bool


class ProviderSummaryGet(DTO):
    id: UUID
    status: ProviderStatusName
    services: list[str]
    approved_at: datetime | None


class ProviderApplicationGet(DTO):
    """El expediente más reciente de un prestador: lo que ve quien se postuló."""

    id: UUID
    procedure: ProcedureName
    status: RequestStatus
    submitted_at: datetime
    resolved_at: datetime | None
    resolution: ResolutionGet | None
    provider: ProviderSummaryGet
    profile: ProfileDataGet
    documents: list[CredentialGet]
    # los tipos que se le piden y no tienen un documento utilizable
    missing: list[OptionRef]


class ProviderApplicationResponse(DTO):
    # la cuenta queda dentro, igual que con el inicio de sesión móvil
    access: str
    refresh: str
    user: SessionUserGet
    application: ProviderApplicationGet
