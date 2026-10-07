from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from api_core.schemas.base import DTO
from api_moderation.schemas import CityRef
from api_organizations.schemas.application import Phone
from api_profiles.schemas.application import (
    CredentialGet,
    FileGet,
    FileKey,
    LanguagePost,
    LevelName,
    OptionRef,
    ProviderStatusName,
)

########################################################################################


class LanguageGet(DTO):
    code: str
    label: str
    level: LevelName


class ProviderProfileGet(DTO):
    """El perfil de un guía o traductor, como lo ve él mismo."""

    id: UUID
    status: ProviderStatusName
    services: list[str]
    # nula es todo el país
    city: CityRef | None
    phone: str
    presentation: str
    photo: FileGet | None
    languages: list[LanguageGet]
    carries_tourists: bool
    approved_at: datetime | None
    # sin reseñas no hay promedio (llegan con la contratación)
    rating: float | None
    reviews: int
    # uno por tipo: el que está en vigor o, si no hay, el más reciente
    documents: list[CredentialGet]
    # los tipos que se le piden y no tienen uno en vigor
    missing: list[OptionRef]


# Solo se aplican los campos que llegan. Son cambios descriptivos: se ven de inmediato
# y no pasan por la revisión (RF-P-06). Los servicios y la ciudad no están: son parte
# de lo que se acredita.
class ProviderProfilePatch(DTO):
    presentation: Annotated[
        str,
        StringConstraints(max_length=1000, strip_whitespace=True),
    ] = ""
    phone: Phone = ""
    languages: Annotated[list[LanguagePost], Field(max_length=20, min_length=1)] = (
        Field(default_factory=list)
    )
    # la clave de una foto subida con `kind` `provider-photo`; nula la quita
    photo_key: FileKey | None = None

    @field_validator("languages")
    @classmethod
    def check_languages(cls, value: list[LanguagePost]) -> list[LanguagePost]:
        codes: list[str] = [item.code for item in value]

        if len(codes) != len(set(codes)):
            raise ValueError("Cada idioma va una sola vez.")

        return value
