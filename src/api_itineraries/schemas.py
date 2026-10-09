from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, PositiveInt, StringConstraints

from api_core.schemas.base import DTO
from api_territory.schemas.common import ClockTime, Reference

########################################################################################

type ItineraryStatusName = Literal["planned", "in_progress", "completed"]
type TravelMode = Literal["walking", "vehicle"]
type Pace = Literal["relaxed", "balanced", "intense"]
type Title = Annotated[str, StringConstraints(max_length=80, min_length=3)]
type StopIds = Annotated[list[Reference], Field(max_length=30)]
# - la posición de la parada ("0", "1"...) -> minutos desde la medianoche
type FixedArrivals = Annotated[
    dict[
        Annotated[str, StringConstraints(pattern=r"^\d{1,2}$")],
        Annotated[int, Field(ge=0, le=1439)],
    ],
    Field(max_length=30),
]

########################################################################################


class FollowedCircuitRef(DTO):
    id: UUID
    title: str
    # si cambió desde la última vez, la app redibuja
    version: PositiveInt
    # un circuito despublicado o retirado sigue en el itinerario que ya lo tenía
    published: bool


class ItineraryStopGet(DTO):
    order: NonNegativeInt
    # el lugar del que salió; nulo si ese lugar ya no existe
    point_id: UUID | None
    name: str
    latitude: float
    longitude: float
    visited_at: datetime | None


class ItineraryGet(DTO):
    id: UUID
    title: str
    status: ItineraryStatusName
    # falso mientras sigue el circuito tal cual: las paradas son las del circuito vivo
    adjusted: bool
    followed_circuit: FollowedCircuitRef | None
    # de qué circuitos salió
    origin_circuit_ids: list[UUID]
    stops: list[ItineraryStopGet]
    start_time: str
    travel_mode: TravelMode
    pace: Pace
    fixed_arrivals: dict[str, int]
    created_at: datetime


class ItineraryPost(DTO):
    title: Title
    # seguir un circuito publicado; con `stop_ids` además, se arma una copia ajustada
    circuit_id: Reference | None = None
    stop_ids: StopIds | None = None
    start_time: ClockTime | None = None
    travel_mode: TravelMode | None = None
    pace: Pace = "balanced"
    fixed_arrivals: FixedArrivals = Field(default_factory=dict)


# Solo se aplican los campos que llegan. Cambiar las paradas de uno que sigue un
# circuito lo vuelve una copia propia (no se revierte).
class ItineraryPatch(DTO):
    title: Title = ""
    stop_ids: StopIds = Field(default_factory=list)
    start_time: ClockTime | None = None
    travel_mode: TravelMode = "walking"
    pace: Pace = "balanced"
    fixed_arrivals: FixedArrivals = Field(default_factory=dict)
