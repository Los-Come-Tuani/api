from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, PositiveInt, StringConstraints

from api_core.schemas.base import DTO, LaxDTO
from api_core.schemas.pagination import PageQuery

from .common import (
    CalendarDate,
    CityRef,
    ClockTime,
    ImageGet,
    ImageKey,
    Latitude,
    Longitude,
    Reference,
)
from .place import StopGet

########################################################################################

type CircuitKind = Literal["kplan", "creative", "private"]
type CircuitCategory = Literal["city", "nature", "culture"]
type Difficulty = Literal["easy", "moderate"]
type TravelMode = Literal["walking", "vehicle"]
type BookingMode = Literal["private", "group"]
type CircuitStatusName = Literal["draft", "published", "unpublished", "retired"]

########################################################################################
# Lo que se devuelve


class MunicipalityRef(DTO):
    id: UUID
    name: str


class CircuitStopGet(DTO):
    order: NonNegativeInt
    point: StopGet
    # cómo llegar desde la parada anterior
    directions: str
    # minutos de traslado desde la parada anterior; nulo es "lo calcula la app"
    leg_minutes: int | None


class CircuitInlineGet(DTO):
    id: UUID
    kind: CircuitKind
    status: CircuitStatusName
    city: CityRef
    # la alcaldía que lo organiza: solo en los creativos
    municipality: MunicipalityRef | None
    title: str
    short_title: str
    subtitle: str
    description: str
    category: CircuitCategory
    difficulty: Difficulty
    travel_mode: TravelMode
    price_adult: int
    price_child: int
    recommendations: str
    includes: str
    notes: str
    meeting_point: str
    meeting_latitude: float
    meeting_longitude: float
    # horas de salida en formato de 24 horas
    start_times: list[str]
    bonus_badges: int
    booking_mode: BookingMode
    available_from: date | None
    available_until: date | None
    # sube cuando cambian las paradas o su orden: la app redibuja el recorrido
    version: PositiveInt
    rating: float
    reviews_count: int
    images: list[ImageGet]
    stop_ids: list[UUID]
    # las insignias de sus paradas más las extra
    badges: int
    # el tiempo de visita de las paradas más los traslados que se conocen
    duration_minutes: int
    created_at: datetime
    published_at: datetime | None


class CircuitGet(CircuitInlineGet):
    stops: list[CircuitStopGet]


########################################################################################
# Lo que se manda


class CircuitStopPost(DTO):
    point_id: Reference
    directions: Annotated[str, StringConstraints(max_length=500)] = ""
    leg_minutes: Annotated[int, Field(ge=0, le=600)] | None = None


class CircuitPost(DTO):
    # quien opera una alcaldía solo crea creativos de su ciudad: el tipo se ignora
    kind: CircuitKind = "creative"
    city_id: Reference | None = None
    title: Annotated[str, StringConstraints(max_length=80, min_length=8)]
    short_title: Annotated[str, StringConstraints(max_length=28, min_length=3)]
    subtitle: Annotated[str, StringConstraints(max_length=60, min_length=3)]
    description: Annotated[str, StringConstraints(max_length=2000, min_length=60)]
    category: CircuitCategory
    difficulty: Difficulty
    travel_mode: TravelMode = "walking"
    price_adult: Annotated[int, Field(ge=0, le=20_000)] = 0
    price_child: Annotated[int, Field(ge=0, le=20_000)] = 0
    recommendations: Annotated[str, StringConstraints(max_length=1000)] = ""
    includes: Annotated[str, StringConstraints(max_length=1000)] = ""
    notes: Annotated[str, StringConstraints(max_length=1000)] = ""
    meeting_point: Annotated[str, StringConstraints(max_length=200, min_length=3)]
    meeting_latitude: Latitude
    meeting_longitude: Longitude
    start_times: Annotated[list[ClockTime], Field(max_length=6)] = Field(
        default_factory=list
    )
    # solo en los especiales de K'Plan
    bonus_badges: Annotated[int, Field(ge=0, le=5)] = 0
    booking_mode: BookingMode = "private"
    available_from: CalendarDate | None = None
    available_until: CalendarDate | None = None
    images: Annotated[list[ImageKey], Field(max_length=8)] = Field(default_factory=list)
    stops: Annotated[list[CircuitStopPost], Field(max_length=10, min_length=2)]
    # publicar exige al menos una foto
    status: Literal["draft", "published"] = "draft"


class CircuitPut(CircuitPost):
    status: Literal["draft", "published", "unpublished"] = "draft"


class CircuitQuery(PageQuery):
    city_id: Reference | None = None
    kind: CircuitKind | None = None
    # sin estado: todos menos los retirados
    status: CircuitStatusName | None = None
    search: Annotated[str, StringConstraints(max_length=100)] | None = None


class PublicCircuitQuery(LaxDTO):
    # el código de la ciudad (`leon`, `granada`...)
    city: Annotated[str, StringConstraints(max_length=40)] | None = None
    kind: CircuitKind | None = None
