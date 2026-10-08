from typing import TYPE_CHECKING, Any

from django.db.transaction import atomic
from django.db.utils import IntegrityError
from django.utils.timezone import localdate, now

from api_exceptions.errors import ConflictError, NotFoundError
from api_services.models import Booking, GuidedDeparture
from api_services.services.bookings import CANCELLED, busy_at, status_row
from api_services.services.guides import (
    LIVE_BOOKINGS,
    active_guide,
    booked_people,
    departure_payload,
    departures,
)
from api_territory.models import Circuit
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from uuid import UUID

    from api_auth.models import ApiUser
    from api_services.schemas import DepartureGet, DeparturePatch, DeparturePost

########################################################################################
# Las salidas que el guía publica sobre los circuitos oficiales


def own_departure(user: ApiUser, departure_id: UUID) -> GuidedDeparture:
    provider = active_guide(user)
    departure: GuidedDeparture | None = (
        departures().filter(pk=departure_id, provider=provider).first()
    )

    if departure is None:
        raise NotFoundError(detail="No encontramos esa salida.")

    return departure


def departures_sync(user: ApiUser) -> list[DepartureGet]:
    provider = active_guide(user)

    return [
        departure_payload(item)
        for item in departures()
        .filter(date__gte=localdate(), provider=provider)
        .order_by("date", "start_time")
    ]


def create_departure_sync(user: ApiUser, data: DeparturePost) -> DepartureGet:
    provider: Any = active_guide(user)
    circuit: Any = (
        Circuit.objects
        .select_related("status")
        .filter(pk=data.circuit_id, status__code="publicado")
        .first()
    )

    if circuit is None:
        raise invalid("circuit_id", "Ese circuito no existe o no está publicado.")

    # el guía de una ciudad guía en su ciudad; el de todo el país, en cualquiera
    if provider.city_id is not None and provider.city_id != circuit.city_id:
        raise invalid("circuit_id", "Ese circuito es de otra ciudad.")

    if data.date < localdate():
        raise invalid("date", "La salida tiene que ser hoy o después.")

    if busy_at(provider, data.date, data.start_time):
        raise ConflictError(detail="Ya tienes una salida o una reserva a esa hora.")

    try:
        departure: GuidedDeparture = GuidedDeparture.objects.create(
            capacity=data.capacity,
            circuit=circuit,
            date=data.date,
            # en los circuitos privados la primera reserva se queda con la salida
            exclusive=circuit.booking_mode == "private",
            note=data.note,
            provider=provider,
            start_time=data.start_time,
            transport_included=data.transport_included,
        )
    except IntegrityError as i:
        raise ConflictError(detail="Ya tienes una salida a esa hora.") from i

    return departure_payload(departures().get(pk=departure.pk))


def update_departure_sync(
    user: ApiUser,
    departure_id: UUID,
    patch: DeparturePatch,
) -> DepartureGet:
    departure: Any = own_departure(user, departure_id)
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)

    if departure.cancelled_at is not None:
        raise ConflictError(detail="Esa salida está cancelada.")

    if "capacity" in changes and changes["capacity"] < booked_people(departure):
        raise invalid("capacity", "Ya reservaron más personas que esos cupos.")

    if changes:
        GuidedDeparture.objects.filter(pk=departure.pk).update(**changes)

    return departure_payload(departures().get(pk=departure.pk))


# Cancelar la salida cancela sus reservas, con el motivo que da el guía.
def cancel_departure_sync(
    user: ApiUser, departure_id: UUID, reason: str
) -> DepartureGet:
    departure: Any = own_departure(user, departure_id)

    if departure.cancelled_at is not None:
        raise ConflictError(detail="Esa salida ya está cancelada.")

    if not reason.strip():
        raise invalid("reason", "Dile a quienes reservaron por qué cancelas.")

    moment = now()

    with atomic():
        GuidedDeparture.objects.filter(pk=departure.pk).update(
            cancel_reason=reason.strip(), cancelled_at=moment
        )
        Booking.objects.filter(
            departure=departure, status__code__in=LIVE_BOOKINGS
        ).update(
            cancel_reason=reason.strip(),
            cancelled_at=moment,
            cancelled_by=user,
            status=status_row(CANCELLED),
        )

    return departure_payload(departures().get(pk=departure.pk))
