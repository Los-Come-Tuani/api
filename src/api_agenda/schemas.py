from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_territory.schemas.common import (
    CalendarDate,
    CityRef,
    ClockTime,
    ImageGet,
    ImageKey,
    Latitude,
    Longitude,
    PillarRef,
    Reference,
)

########################################################################################

type EventStatusName = Literal["scheduled", "ongoing", "finished", "cancelled"]
type CategoryCode = Annotated[str, StringConstraints(max_length=40, min_length=1)]
type EventName = Annotated[str, StringConstraints(max_length=120, min_length=3)]
type Venue = Annotated[str, StringConstraints(max_length=150, min_length=2)]
type Price = Annotated[int, Field(ge=0, le=100_000)]
type Reason = Annotated[str, StringConstraints(max_length=500)]

########################################################################################


class OrganizerRef(DTO):
    # `kplan`: un evento especial del equipo, sin institución ni alcaldía
    kind: Literal["institution", "municipality", "kplan"]
    id: UUID | None
    name: str


class EventGet(DTO):
    id: UUID
    name: str
    description: str
    # la clase del evento; `code` y `label` como los pilares
    category: PillarRef
    city: CityRef
    venue: str
    address: str
    latitude: float
    longitude: float
    start_date: date
    end_date: date
    # el horario de cada día, en formato de 24 horas
    start_time: str
    end_time: str
    # córdobas; cero es entrada libre
    entry_price: int
    featured: bool
    # lo pone el calendario: próximo, en curso, finalizado; o cancelado
    status: EventStatusName
    cancellation_reason: str
    organizer: OrganizerRef
    # el lugar del mapa donde ocurre, si es uno
    point_id: UUID | None
    images: list[ImageGet]
    cloned_from_id: UUID | None
    created_at: datetime


class ManagedEventGet(EventGet):
    # oculto por moderación: no sale en la app
    hidden: bool
    hidden_reason: str


class PublicEventQuery(PageQuery):
    # el código de la ciudad (`leon`, `granada`...)
    city: Annotated[str, StringConstraints(max_length=40)] | None = None
    category: CategoryCode | None = None
    # los que ocurren entre estas fechas (alguno de sus días)
    from_date: CalendarDate | None = None
    to_date: CalendarDate | None = None
    featured: bool | None = None


class EventQuery(PageQuery):
    city_id: Reference | None = None
    category: CategoryCode | None = None
    status: EventStatusName | None = None
    from_date: CalendarDate | None = None
    to_date: CalendarDate | None = None
    search: Annotated[str, StringConstraints(max_length=100)] | None = None


class EventPost(DTO):
    # dónde ocurre, que no tiene que ser la ciudad de quien lo programa
    city_id: Reference
    category: CategoryCode
    name: EventName
    description: Annotated[str, StringConstraints(max_length=2000)] = ""
    venue: Venue
    address: Annotated[str, StringConstraints(max_length=200)] = ""
    latitude: Latitude
    longitude: Longitude
    start_date: CalendarDate
    end_date: CalendarDate
    start_time: ClockTime
    end_time: ClockTime
    entry_price: Price = 0
    point_id: Reference | None = None
    images: Annotated[list[ImageKey], Field(max_length=8)] = Field(default_factory=list)
    # solo el equipo con `content.moderate`
    featured: bool = False


# Solo se aplican los campos que llegan.
class EventPatch(DTO):
    category: CategoryCode = ""
    name: EventName = ""
    description: Annotated[str, StringConstraints(max_length=2000)] = ""
    venue: Venue = ""
    address: Annotated[str, StringConstraints(max_length=200)] = ""
    latitude: Latitude = 0
    longitude: Longitude = 0
    start_date: CalendarDate | None = None
    end_date: CalendarDate | None = None
    start_time: ClockTime | None = None
    end_time: ClockTime | None = None
    entry_price: Price = 0
    point_id: Reference | None = None
    images: Annotated[list[ImageKey], Field(max_length=8)] = Field(default_factory=list)
    featured: bool = False


class CancelPost(DTO):
    reason: Reason = ""


class HidePost(DTO):
    reason: Annotated[str, StringConstraints(max_length=500, min_length=3)]


class ClonePost(DTO):
    start_date: CalendarDate
    end_date: CalendarDate
