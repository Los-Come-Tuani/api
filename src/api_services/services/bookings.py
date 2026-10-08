from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Q
from django.db.transaction import atomic
from django.utils.timezone import localdate, now

from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_messaging.models import Conversation, Message, Participant
from api_profiles.models import ProviderProfile
from api_reputation.models import Review
from api_rewards.services.badges import ensure_tourist
from api_services.models import Booking, BookingStatus, GuidedDeparture
from api_services.schemas import BookingGet, BookingRouteRef, PersonGet
from api_services.services.guides import (
    LIVE_BOOKINGS,
    booked_people,
    clock,
    guide_ref,
    starts_at,
)
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from datetime import date, datetime, time
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_services.schemas import BookingPost

########################################################################################

CONFIRMED: Final[str] = "confirmada"
IN_PROGRESS: Final[str] = "en_curso"
DELIVERED: Final[str] = "prestada"
CANCELLED: Final[str] = "cancelada"

STATUS_API: Final[dict[str, str]] = {
    CANCELLED: "cancelled",
    "cerrada": "closed",
    CONFIRMED: "confirmed",
    DELIVERED: "delivered",
    IN_PROGRESS: "in_progress",
}

# - hasta cuánto antes de empezar el turista cancela gratis
FREE_CANCELLATION: Final[timedelta] = timedelta(hours=24)

NOT_FOUND_DETAIL: Final[str] = "No encontramos esa reserva."

########################################################################################
# Piezas


def status_row(code: str) -> BookingStatus:
    return BookingStatus.objects.get(code=code)


def bookings() -> QuerySet:
    return Booking.objects.select_related(
        "circuit",
        "itinerary",
        "provider__user",
        "status",
        "user",
    )


def provider_of(user: ApiUser) -> ProviderProfile | None:
    return ProviderProfile.objects.filter(user=user).first()


# Las reservas de quien pregunta: las suyas como turista o las de su perfil de guía.
def own_bookings(user: ApiUser) -> QuerySet:
    return bookings().filter(Q(user=user) | Q(provider__user=user))


def own_booking(user: ApiUser, booking_id: UUID, *, lock: bool = False) -> Booking:
    found: Any = own_bookings(user)

    if lock:
        found = found.select_for_update(of=("self",))

    booking: Booking | None = found.filter(pk=booking_id).first()

    # la de otras personas no existe para quien pregunta
    if booking is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return booking


def is_guide_of(user: ApiUser, booking: Booking) -> bool:
    found: Any = booking

    return found.provider.user_id == user.pk


def cancel_deadline(booking: Booking) -> datetime:
    found: Any = booking

    return starts_at(found.date, found.start_time) - FREE_CANCELLATION


def unread_for(user: ApiUser, booking: Booking) -> int:
    participant: Any = Participant.objects.filter(
        conversation__booking=booking, user=user
    ).first()

    if participant is None:
        return 0

    messages = Message.objects.filter(conversation__booking=booking).exclude(
        sender=user
    )

    if participant.last_read_at is not None:
        messages = messages.filter(sent_at__gt=participant.last_read_at)

    return messages.count()


def booking_payload(booking: Booking, viewer: ApiUser) -> BookingGet:
    found: Any = booking
    guide: bool = is_guide_of(viewer, booking)
    deadline: datetime = cancel_deadline(booking)
    cancellable: bool = bool(found.status.allows_cancellation) and (
        guide or now() <= deadline
    )

    return BookingGet(
        adults=int(found.adults),
        amount=int(found.amount),
        can_cancel=cancellable,
        cancel_deadline=deadline,
        cancel_reason=str(found.cancel_reason),
        cancelled_at=found.cancelled_at,
        children=int(found.children),
        circuit=(
            None
            if found.circuit is None
            else BookingRouteRef(id=found.circuit.pk, title=str(found.circuit.title))
        ),
        created_at=found.created_at,
        date=found.date,
        departure_id=found.departure_id,
        guide=guide_ref(found.provider),
        id=found.pk,
        itinerary=(
            None
            if found.itinerary is None
            else BookingRouteRef(
                id=found.itinerary.pk, title=str(found.itinerary.title)
            )
        ),
        payment_status=str(found.payment_status),
        reviewed=Review.objects.filter(author=viewer, booking=booking).exists(),
        role="guide" if guide else "tourist",
        start_time=clock(found.start_time),
        status=STATUS_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        tourist=PersonGet(id=found.user.pk, name=found.user.display_name),
        unread_messages=unread_for(viewer, booking),
    )


# La sala del chat nace con la reserva, con el turista y el guía dentro.
def open_conversation(booking: Booking) -> None:
    found: Any = booking
    conversation, _ = Conversation.objects.get_or_create(booking=booking)

    for user_id in (found.user_id, found.provider.user_id):
        Participant.objects.get_or_create(conversation=conversation, user_id=user_id)


def busy_at(provider: ProviderProfile, day: date, hour: time) -> bool:
    # el guía ya tiene una reserva viva o una salida a esa hora
    return (
        Booking.objects.filter(
            date=day,
            provider=provider,
            start_time=hour,
            status__code__in=LIVE_BOOKINGS,
        ).exists()
        or GuidedDeparture.objects.filter(
            cancelled_at__isnull=True,
            date=day,
            provider=provider,
            start_time=hour,
        ).exists()
    )


########################################################################################
# Lectura


def bookings_sync(user: ApiUser) -> list[BookingGet]:
    return [
        booking_payload(item, user)
        for item in own_bookings(user).order_by("-date", "-start_time", "id")
    ]


def booking_sync(user: ApiUser, booking_id: UUID) -> BookingGet:
    return booking_payload(own_booking(user, booking_id), user)


########################################################################################
# Reservar una salida (circuito oficial)


def book_departure_sync(user: ApiUser, data: BookingPost) -> BookingGet:
    ensure_tourist(user)

    with atomic():
        departure: Any = (
            GuidedDeparture.objects
            .select_for_update(of=("self",))
            .select_related("circuit__status", "provider__status")
            .filter(pk=data.departure_id)
            .first()
        )

        if (
            departure is None
            or departure.cancelled_at is not None
            or departure.circuit.status.code != "publicado"
            or not departure.provider.status.accepts_bookings
            or departure.date < localdate()
        ):
            raise NotFoundError(detail="Esa salida ya no está disponible.")

        if starts_at(departure.date, departure.start_time) <= now():
            raise ConflictError(detail="Esa salida ya empezó.")

        party: int = data.adults + data.children
        booked: int = booked_people(departure)

        if departure.exclusive and booked > 0:
            raise ConflictError(detail="Esa salida privada ya la reservó alguien.")

        if booked + party > departure.capacity:
            left: int = max(0, departure.capacity - booked)

            raise ConflictError(detail=f"Quedan {left} cupos en esa salida.")

        circuit: Any = departure.circuit
        booking: Booking = Booking.objects.create(
            adults=data.adults,
            amount=int(circuit.price_adult) * data.adults
            + int(circuit.price_child) * data.children,
            children=data.children,
            circuit=circuit,
            date=departure.date,
            departure=departure,
            provider=departure.provider,
            start_time=departure.start_time,
            status=status_row(CONFIRMED),
            user=user,
        )

        open_conversation(booking)

    return booking_sync(user, booking.pk)


########################################################################################
# Cancelar, empezar y terminar


# El turista cancela gratis hasta 24 horas antes; el guía, con un motivo, mientras no
# haya empezado.
def cancel_booking_sync(user: ApiUser, booking_id: UUID, reason: str) -> BookingGet:
    with atomic():
        booking: Any = own_booking(user, booking_id, lock=True)
        guide: bool = is_guide_of(user, booking)

        if not booking.status.allows_cancellation:
            raise ConflictError(detail="Esa reserva ya no se puede cancelar.")

        if guide and not reason.strip():
            raise invalid("reason", "Dile al turista por qué cancelas.")

        if not guide and now() > cancel_deadline(booking):
            raise ConflictError(
                detail="Ya pasó el plazo para cancelar (24 horas antes de empezar)."
            )

        Booking.objects.filter(pk=booking.pk).update(
            cancel_reason=reason.strip(),
            cancelled_at=now(),
            cancelled_by=user,
            status=status_row(CANCELLED),
        )

    return booking_sync(user, booking_id)


def guide_booking(user: ApiUser, booking_id: UUID) -> Booking:
    booking: Booking = own_booking(user, booking_id, lock=True)

    if not is_guide_of(user, booking):
        raise ForbiddenError(detail="Esto lo hace el guía.")

    return booking


def start_booking_sync(user: ApiUser, booking_id: UUID) -> BookingGet:
    with atomic():
        booking: Any = guide_booking(user, booking_id)

        if booking.status.code != CONFIRMED:
            raise ConflictError(detail="Esa reserva no está por empezar.")

        if booking.date > localdate():
            raise ConflictError(detail="El recorrido todavía no es hoy.")

        Booking.objects.filter(pk=booking.pk).update(
            started_at=now(), status=status_row(IN_PROGRESS)
        )

    return booking_sync(user, booking_id)


def finish_booking_sync(user: ApiUser, booking_id: UUID) -> BookingGet:
    with atomic():
        booking: Any = guide_booking(user, booking_id)

        if booking.status.code != IN_PROGRESS:
            raise ConflictError(detail="Esa reserva no está en curso.")

        Booking.objects.filter(pk=booking.pk).update(
            finished_at=now(), status=status_row(DELIVERED)
        )

    return booking_sync(user, booking_id)
