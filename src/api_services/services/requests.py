from typing import TYPE_CHECKING, Any, Final

from django.db.models import Count, Q
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from django.utils.timezone import localdate, now

from api_exceptions.errors import ConflictError, NotFoundError
from api_finance.services.payments import open_payment
from api_itineraries.models import Itinerary
from api_notifications.services import notify
from api_rewards.services.badges import ensure_tourist
from api_services.models import Application, Booking, RequestStatus, ServiceRequest
from api_services.schemas import (
    ApplicationGet,
    ApplicationRequestRef,
    ItineraryRef,
    OpenRequestGet,
    RequestGet,
)
from api_services.services.bookings import (
    CONFIRMED,
    booking_sync,
    busy_at,
    open_conversation,
    status_row,
)
from api_services.services.guides import (
    active_guide,
    card_payload,
    clock,
    visible_guides,
)
from api_territory.models import City
from api_territory.services.access import invalid
from api_territory.services.places import city_ref

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_profiles.models import ProviderProfile
    from api_services.schemas import (
        AcceptPost,
        ApplyPost,
        BookingGet,
        RequestPost,
    )

########################################################################################

OPEN: Final[str] = "abierta"
AWARDED: Final[str] = "adjudicada"
CANCELLED: Final[str] = "cancelada"
EXPIRED: Final[str] = "expirada"

STATUS_API: Final[dict[str, str]] = {
    AWARDED: "awarded",
    CANCELLED: "cancelled",
    EXPIRED: "expired",
    OPEN: "open",
}

APPLICATION_API: Final[dict[str, str]] = {
    "aceptada": "accepted",
    "enviada": "sent",
    "rechazada": "rejected",
    "retirada": "withdrawn",
}

NOT_FOUND_DETAIL: Final[str] = "No encontramos esa convocatoria."

########################################################################################
# Piezas


def request_status(code: str) -> RequestStatus:
    return RequestStatus.objects.get(code=code)


# La convocatoria cuya fecha pasó sin adjudicarse vence.
def expire_requests() -> None:
    ServiceRequest.objects.filter(status__code=OPEN, date__lt=localdate()).update(
        closed_at=now(), status=request_status(EXPIRED)
    )
    Application.objects.filter(request__status__code=EXPIRED, status="enviada").update(
        status="rechazada"
    )


def requests() -> QuerySet:
    return ServiceRequest.objects.select_related(
        "city", "itinerary", "status"
    ).annotate(stops_count=Count("itinerary__stops", distinct=True))


def itinerary_ref(request: ServiceRequest) -> ItineraryRef:
    found: Any = request

    return ItineraryRef(
        id=found.itinerary.pk,
        stops=int(getattr(found, "stops_count", 0) or 0),
        title=str(found.itinerary.title),
    )


def application_payload(application: Application) -> ApplicationGet:
    found: Any = application
    provider: Any = visible_guides(only_visible=False).get(pk=found.provider_id)
    request: Any = requests().get(pk=found.request_id)

    return ApplicationGet(
        created_at=found.created_at,
        fee=int(found.fee),
        guide=card_payload(provider),
        id=found.pk,
        message=str(found.message),
        request=ApplicationRequestRef(
            adults=int(request.adults),
            children=int(request.children),
            city=city_ref(request.city),
            date=request.date,
            itinerary=itinerary_ref(request),
            start_time=clock(request.start_time),
        ),
        request_id=found.request_id,
        status=APPLICATION_API[str(found.status)],  # ty: ignore[invalid-argument-type]
    )


def request_payload(request: ServiceRequest, *, with_applications: bool) -> RequestGet:
    found: Any = request

    return RequestGet(
        adults=int(found.adults),
        applications=(
            [
                application_payload(item)
                for item in found.applications.order_by("fee", "created_at")
            ]
            if with_applications
            else []
        ),
        children=int(found.children),
        city=city_ref(found.city),
        created_at=found.created_at,
        date=found.date,
        id=found.pk,
        itinerary=itinerary_ref(request),
        max_fee=found.max_fee,
        note=str(found.note),
        start_time=clock(found.start_time),
        status=STATUS_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
    )


########################################################################################
# El turista publica y elige


def own_request(
    user: ApiUser, request_id: UUID, *, lock: bool = False
) -> ServiceRequest:
    found: Any = requests().filter(user=user)

    if lock:
        found = ServiceRequest.objects.select_for_update().filter(user=user)

    request: ServiceRequest | None = found.filter(pk=request_id).first()

    if request is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return request


def requests_sync(user: ApiUser) -> list[RequestGet]:
    expire_requests()

    return [
        request_payload(item, with_applications=True)
        for item in requests().filter(user=user).order_by("-created_at", "id")
    ]


def request_sync(user: ApiUser, request_id: UUID) -> RequestGet:
    expire_requests()

    return request_payload(own_request(user, request_id), with_applications=True)


def city_of(itinerary: Itinerary, city_id: UUID | None) -> City:
    if city_id is not None:
        city: City | None = City.objects.filter(pk=city_id).first()

        if city is None:
            raise invalid("city_id", "Esa ciudad no existe.")

        return city

    found: Any = itinerary
    stop: Any = (
        found.stops
        .select_related("point__city")
        .filter(point__isnull=False)
        .order_by("order")
        .first()
    )

    if stop is None:
        raise invalid("city_id", "Di en qué ciudad es el recorrido.")

    return stop.point.city


# Solo para un itinerario propio (armado o ajustado por el turista): en un circuito
# oficial el guía publica sus horarios y se reserva una salida.
def create_request_sync(user: ApiUser, data: RequestPost) -> RequestGet:
    ensure_tourist(user)

    itinerary: Any = Itinerary.objects.filter(
        deleted_at__isnull=True, pk=data.itinerary_id, user=user
    ).first()

    if itinerary is None:
        raise invalid("itinerary_id", "Ese itinerario no existe.")

    if not itinerary.adjusted:
        raise invalid(
            "itinerary_id",
            "Para un circuito oficial, reserva una salida de un guía.",
        )

    if data.date < localdate():
        raise invalid("date", "La fecha tiene que ser hoy o después.")

    city: City = city_of(itinerary, data.city_id)

    if ServiceRequest.objects.filter(itinerary=itinerary, status__code=OPEN).exists():
        raise ConflictError(detail="Ese itinerario ya tiene una convocatoria abierta.")

    request: ServiceRequest = ServiceRequest.objects.create(
        adults=data.adults,
        children=data.children,
        city=city,
        date=data.date,
        itinerary=itinerary,
        max_fee=data.max_fee,
        note=data.note,
        start_time=data.start_time,
        status=request_status(OPEN),
        user=user,
    )

    return request_sync(user, request.pk)


# Elegir una postulación crea la reserva (con la tarifa del guía congelada) y cierra la
# convocatoria; las demás quedan rechazadas.
def accept_application_sync(
    user: ApiUser,
    request_id: UUID,
    data: AcceptPost,
) -> BookingGet:
    with atomic():
        request: Any = own_request(user, request_id, lock=True)

        if request.status.code != OPEN:
            raise ConflictError(detail="Esa convocatoria ya no está abierta.")

        application: Any = (
            Application.objects
            .select_related("provider__status")
            .filter(pk=data.application_id, request=request, status="enviada")
            .first()
        )

        if application is None:
            raise invalid("application_id", "Esa postulación no está disponible.")

        provider: Any = application.provider

        if not provider.status.accepts_bookings:
            raise ConflictError(detail="Ese guía ya no acepta reservas.")

        if busy_at(provider, request.date, request.start_time):
            raise ConflictError(detail="Ese guía ya tiene otro recorrido a esa hora.")

        booking: Booking = Booking.objects.create(
            adults=request.adults,
            amount=application.fee,
            application=application,
            children=request.children,
            date=request.date,
            itinerary_id=request.itinerary_id,
            provider=provider,
            start_time=request.start_time,
            status=status_row(CONFIRMED),
            user=user,
        )

        Application.objects.filter(pk=application.pk).update(status="aceptada")
        Application.objects.filter(request=request, status="enviada").update(
            status="rechazada"
        )
        ServiceRequest.objects.filter(pk=request.pk).update(
            closed_at=now(), status=request_status(AWARDED)
        )

        open_conversation(booking)
        open_payment(booking)
        notify(
            provider.user_id,
            "reserva",
            "Te eligieron",
            f"{user.display_name} aceptó tu postulación para el {request.date:%d/%m}.",
            {"booking_id": str(booking.pk)},
        )

    return booking_sync(user, booking.pk)


def cancel_request_sync(user: ApiUser, request_id: UUID) -> RequestGet:
    with atomic():
        request: Any = own_request(user, request_id, lock=True)

        if request.status.code != OPEN:
            raise ConflictError(detail="Esa convocatoria ya no está abierta.")

        ServiceRequest.objects.filter(pk=request.pk).update(
            closed_at=now(), status=request_status(CANCELLED)
        )
        Application.objects.filter(request=request, status="enviada").update(
            status="rechazada"
        )

    return request_sync(user, request_id)


########################################################################################
# El guía ve las abiertas de su zona y se postula


def covered_by(provider: ProviderProfile) -> Q:
    found: Any = provider

    # el guía de todo el país ve todas; el de una ciudad, las de su ciudad
    return Q() if found.city_id is None else Q(city_id=found.city_id)


def open_requests_sync(user: ApiUser) -> list[OpenRequestGet]:
    provider: Any = active_guide(user)
    expire_requests()

    applied: set[UUID] = set(
        Application.objects.filter(provider=provider).values_list(
            "request_id", flat=True
        )
    )

    found = (
        requests()
        .filter(covered_by(provider), date__gte=localdate(), status__code=OPEN)
        .exclude(user=user)
        .order_by("date", "start_time", "id")
    )

    return [
        OpenRequestGet(
            adults=int(item.adults),
            applied=item.pk in applied,
            children=int(item.children),
            city=city_ref(item.city),
            created_at=item.created_at,
            date=item.date,
            id=item.pk,
            itinerary=itinerary_ref(item),
            max_fee=item.max_fee,
            note=str(item.note),
            start_time=clock(item.start_time),
        )
        for item in found
    ]


def apply_sync(user: ApiUser, request_id: UUID, data: ApplyPost) -> ApplicationGet:
    provider: Any = active_guide(user)
    expire_requests()

    request: Any = (
        ServiceRequest.objects
        .filter(covered_by(provider), pk=request_id, status__code=OPEN)
        .exclude(user=user)
        .first()
    )

    if request is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    if request.max_fee is not None and data.fee > request.max_fee:
        raise invalid("fee", f"El turista paga hasta C$ {request.max_fee}.")

    try:
        application: Application = Application.objects.create(
            fee=data.fee,
            message=data.message,
            provider=provider,
            request=request,
        )
    except IntegrityError as i:
        raise ConflictError(detail="Ya te postulaste a esta convocatoria.") from i

    notify(
        request.user_id,
        "convocatoria",
        "Un guía se postuló",
        f"{user.display_name} se ofrece para tu recorrido por C$ {data.fee}.",
        {"request_id": str(request.pk)},
    )

    return application_payload(application)


def own_applications_sync(user: ApiUser) -> list[ApplicationGet]:
    provider = active_guide(user)

    return [
        application_payload(item)
        for item in Application.objects.filter(provider=provider).order_by(
            "-created_at", "id"
        )
    ]


def withdraw_application_sync(user: ApiUser, application_id: UUID) -> ApplicationGet:
    provider = active_guide(user)
    application: Any = Application.objects.filter(
        pk=application_id, provider=provider
    ).first()

    if application is None:
        raise NotFoundError(detail="No encontramos esa postulación.")

    if application.status != "enviada":
        raise ConflictError(detail="Esa postulación ya se resolvió.")

    Application.objects.filter(pk=application.pk).update(status="retirada")
    application.refresh_from_db()

    return application_payload(application)
