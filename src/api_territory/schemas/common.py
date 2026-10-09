from datetime import date, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from api_core.schemas.base import DTO

########################################################################################

# - un UUID, una hora o una fecha llegan como texto en el JSON, y el DTO estricto no los
#   convertiría solos
type Reference = Annotated[UUID, Field(strict=False)]
type ClockTime = Annotated[time, Field(strict=False)]
type CalendarDate = Annotated[date, Field(strict=False)]

# - el territorio nicaragüense
type Latitude = Annotated[float, Field(ge=10.7, le=15.1, strict=False)]
type Longitude = Annotated[float, Field(ge=-87.7, le=-82.6, strict=False)]

# - la clave de un archivo ya subido (`upload/`) o de una imagen que el objeto ya tiene
type ImageKey = Annotated[str, StringConstraints(max_length=500, min_length=1)]

type OrganizationKind = Literal["business", "institution", "municipality"]

########################################################################################


class ImageGet(DTO):
    key: str
    # para mostrarla; las del almacenamiento vencen en minutos y son nulas si no está
    # configurado
    url: str | None


class PillarRef(DTO):
    code: str
    label: str


class CityRef(DTO):
    id: UUID
    code: str
    name: str


class OwnerRef(DTO):
    kind: OrganizationKind
    id: UUID
    name: str
