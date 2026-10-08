from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_territory.schemas.common import (
    CalendarDate,
    CityRef,
    ClockTime,
    ImageGet,
    Reference,
)

########################################################################################

type BookingStatusName = Literal[
    "confirmed",
    "in_progress",
    "delivered",
    "closed",
    "cancelled",
]
type RequestStatusName = Literal["open", "awarded", "cancelled", "expired"]
type ApplicationStatusName = Literal["sent", "accepted", "rejected", "withdrawn"]
type Party = Annotated[int, Field(ge=0, le=50)]
type Adults = Annotated[int, Field(ge=1, le=50)]
type Fee = Annotated[int, Field(ge=1, le=1_000_000)]
type Note = Annotated[str, StringConstraints(max_length=1000)]

########################################################################################
# Los guías que ve el turista


class GuideLanguageGet(DTO):
    code: str
    name: str
    level: str


class GuideCardGet(DTO):
    id: UUID
    name: str
    photo: ImageGet | None
    presentation: str
    # `guia`, `traductor` o los dos
    services: list[str]
    languages: list[GuideLanguageGet]
    # nula es todo el país
    city: CityRef | None
    carries_tourists: bool
    # el promedio de lo que dicen los turistas; nulo sin reseñas
    rating: float | None
    reviews_count: NonNegativeInt


class GuideReviewGet(DTO):
    rating: int
    comment: str
    # el nombre de pila de quien la escribió
    author: str
    created_at: datetime


class DepartureCircuitRef(DTO):
    id: UUID
    title: str
    kind: str
    city: CityRef


class GuideRef(DTO):
    id: UUID
    name: str
    photo: ImageGet | None


class DepartureGet(DTO):
    id: UUID
    circuit: DepartureCircuitRef
    guide: GuideRef
    date: date
    start_time: str
    capacity: int
    # cuántas personas ya reservaron y cuántos cupos quedan
    booked: NonNegativeInt
    remaining: NonNegativeInt
    # privada: la primera reserva se la queda
    exclusive: bool
    transport_included: bool
    note: str
    cancelled: bool
    # lo que cuesta por persona (la reserva lo congela)
    price_adult: int
    price_child: int


class GuideDetailGet(GuideCardGet):
    reviews: list[GuideReviewGet]
    # sus próximas salidas
    departures: list[DepartureGet]


class GuideQuery(PageQuery):
    # el código de la ciudad (`leon`...): los de esa ciudad y los de todo el país
    city: Annotated[str, StringConstraints(max_length=40)] | None = None
    language: Annotated[str, StringConstraints(max_length=8)] | None = None
    service: Literal["guia", "traductor"] | None = None


########################################################################################
# Salidas (el guía)


class DeparturePost(DTO):
    circuit_id: Reference
    date: CalendarDate
    start_time: ClockTime
    capacity: Annotated[int, Field(ge=1, le=50)] = 10
    transport_included: bool = False
    note: Annotated[str, StringConstraints(max_length=500)] = ""


# Solo se aplican los campos que llegan.
class DeparturePatch(DTO):
    capacity: Annotated[int, Field(ge=1, le=50)] = 10
    transport_included: bool = False
    note: Annotated[str, StringConstraints(max_length=500)] = ""


class ServiceCancelPost(DTO):
    reason: Annotated[str, StringConstraints(max_length=500)] = ""


########################################################################################
# Convocatorias y postulaciones


class ItineraryRef(DTO):
    id: UUID
    title: str
    stops: NonNegativeInt


class ApplicationGet(DTO):
    id: UUID
    request_id: UUID
    guide: GuideCardGet
    fee: int
    message: str
    status: ApplicationStatusName
    created_at: datetime


class RequestGet(DTO):
    id: UUID
    itinerary: ItineraryRef
    city: CityRef
    date: date
    start_time: str
    adults: int
    children: int
    max_fee: int | None
    note: str
    status: RequestStatusName
    created_at: datetime
    # las postulaciones: completas para quien la publicó
    applications: list[ApplicationGet]


class OpenRequestGet(DTO):
    id: UUID
    itinerary: ItineraryRef
    city: CityRef
    date: date
    start_time: str
    adults: int
    children: int
    max_fee: int | None
    note: str
    # el guía que pregunta ya se postuló
    applied: bool
    created_at: datetime


class RequestPost(DTO):
    itinerary_id: Reference
    date: CalendarDate
    start_time: ClockTime
    adults: Adults = 1
    children: Party = 0
    max_fee: Fee | None = None
    note: Note = ""
    # sin ella, la de la primera parada del itinerario
    city_id: Reference | None = None


class ApplyPost(DTO):
    fee: Fee
    message: Note = ""


class AcceptPost(DTO):
    application_id: Reference


########################################################################################
# Reservas


class PersonGet(DTO):
    id: UUID
    name: str


class BookingRouteRef(DTO):
    id: UUID
    title: str


class BookingGet(DTO):
    id: UUID
    # cómo la ve quien pregunta
    role: Literal["tourist", "guide"]
    status: BookingStatusName
    date: date
    start_time: str
    adults: int
    children: int
    # congelado al reservar, en córdobas
    amount: int
    payment_status: str
    circuit: BookingRouteRef | None
    itinerary: BookingRouteRef | None
    guide: GuideRef
    tourist: PersonGet
    departure_id: UUID | None
    # el turista cancela gratis hasta esta hora
    cancel_deadline: datetime
    can_cancel: bool
    cancelled_at: datetime | None
    cancel_reason: str
    created_at: datetime
    unread_messages: NonNegativeInt
    # quien pregunta ya dejó su reseña
    reviewed: bool


class BookingPost(DTO):
    departure_id: Reference
    adults: Adults = 1
    children: Party = 0
