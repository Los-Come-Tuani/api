from datetime import datetime, time
from typing import TYPE_CHECKING, Any, Final

from django.db.models import F, Prefetch, Q
from django.utils.timezone import localdate, make_aware

from api_core.services.pages import paginate
from api_exceptions.errors import ForbiddenError, NotFoundError
from api_profiles.enums import LEVEL_API_NAMES
from api_profiles.models import ProviderLanguage, ProviderProfile
from api_reputation.models import Review
from api_services.models import Booking, GuidedDeparture
from api_services.schemas import (
    DepartureCircuitRef,
    DepartureGet,
    GuideCardGet,
    GuideDetailGet,
    GuideLanguageGet,
    GuideRef,
    GuideReviewGet,
)
from api_territory.services.images import image_payload
from api_territory.services.places import city_ref

if TYPE_CHECKING:
    from datetime import date
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_core.schemas.pagination import Paginated
    from api_services.schemas import GuideQuery

########################################################################################

GUIDE_SERVICE: Final[str] = "guia"
PUBLIC_REVIEWS: Final[int] = 20
# - las reservas que todavía ocupan al guía o un cupo
LIVE_BOOKINGS: Final[tuple[str, ...]] = ("confirmada", "en_curso")

########################################################################################
# Tiempo


# La fecha y hora local de algo que empieza un día a una hora.
def starts_at(day: date, hour: time) -> datetime:
    return make_aware(datetime.combine(day, hour))


def clock(value: time) -> str:
    return value.strftime("%H:%M")


########################################################################################
# El guía


def services_of(provider: ProviderProfile) -> list[str]:
    found: Any = provider

    return sorted(str(item.service.code) for item in found.services.all())


# Quien guía: un prestador aprobado que ofrece el servicio de guía y acepta reservas.
def active_guide(user: ApiUser) -> ProviderProfile:
    provider: Any = (
        ProviderProfile.objects
        .select_related("city", "status", "user")
        .prefetch_related("services__service")
        .filter(user=user)
        .first()
    )

    if (
        provider is None
        or not provider.status.accepts_bookings
        or GUIDE_SERVICE not in services_of(provider)
    ):
        raise ForbiddenError(detail="Esto es para un guía aprobado.")

    return provider


def visible_guides(*, only_visible: bool = True) -> QuerySet:
    found = ProviderProfile.objects.select_related(
        "city", "status", "user"
    ).prefetch_related(
        "services__service",
        Prefetch(
            "languages",
            queryset=ProviderLanguage.objects.select_related("language"),
        ),
    )

    # el turista solo encuentra a los prestadores activos (`es_visible`)
    return found.filter(status__is_visible=True) if only_visible else found


def guide_ref(provider: ProviderProfile) -> GuideRef:
    found: Any = provider

    return GuideRef(
        id=found.pk,
        name=found.user.display_name,
        photo=image_payload(str(found.photo_key)) if found.photo_key else None,
    )


def card_payload(provider: ProviderProfile) -> GuideCardGet:
    found: Any = provider
    rating: Any = found.rating_average

    return GuideCardGet(
        carries_tourists=bool(found.carries_tourists),
        city=None if found.city is None else city_ref(found.city),
        id=found.pk,
        languages=[
            GuideLanguageGet(
                code=str(item.language.code),
                level=LEVEL_API_NAMES.get(str(item.level), str(item.level)),
                name=str(item.language.name),
            )
            for item in found.languages.all()
        ],
        name=found.user.display_name,
        photo=image_payload(str(found.photo_key)) if found.photo_key else None,
        presentation=str(found.presentation),
        rating=None if rating is None else round(float(rating), 1),
        reviews_count=int(found.reviews_count),
        services=services_of(provider),
        user_id=found.user_id,
    )


########################################################################################
# Salidas


def booked_people(departure: GuidedDeparture) -> int:
    total: int = 0

    for booking in Booking.objects.filter(
        departure=departure, status__code__in=LIVE_BOOKINGS
    ).only("adults", "children"):
        found: Any = booking
        total += int(found.adults) + int(found.children)

    return total


def departure_payload(departure: GuidedDeparture) -> DepartureGet:
    found: Any = departure
    booked: int = booked_people(departure)
    circuit: Any = found.circuit

    taken: bool = found.exclusive and booked > 0

    return DepartureGet(
        booked=booked,
        cancelled=found.cancelled_at is not None,
        capacity=int(found.capacity),
        circuit=DepartureCircuitRef(
            city=city_ref(circuit.city),
            id=circuit.pk,
            kind=str(circuit.kind),
            title=str(circuit.title),
        ),
        date=found.date,
        exclusive=bool(found.exclusive),
        guide=guide_ref(found.provider),
        id=found.pk,
        note=str(found.note),
        price_adult=int(circuit.price_adult),
        price_child=int(circuit.price_child),
        remaining=0 if taken else max(0, int(found.capacity) - booked),
        start_time=clock(found.start_time),
        transport_included=bool(found.transport_included),
    )


def departures() -> QuerySet:
    return GuidedDeparture.objects.select_related(
        "circuit__city",
        "provider__user",
    )


def upcoming_departures() -> QuerySet:
    return departures().filter(
        cancelled_at__isnull=True,
        circuit__status__code="publicado",
        date__gte=localdate(),
    )


########################################################################################
# Lo público


def guides_sync(query: GuideQuery) -> Paginated[GuideCardGet]:
    found = visible_guides()

    if query.city:
        found = found.filter(Q(city__code=query.city) | Q(city__isnull=True))

    if query.language:
        found = found.filter(languages__language__code=query.language)

    if query.service:
        found = found.filter(services__service__code=query.service)

    # los mejor calificados primero; los nuevos, sin promedio, al final
    return paginate(
        found.distinct().order_by(
            F("rating_average").desc(nulls_last=True), "user__first_name", "id"
        ),
        query,
        card_payload,
        GuideCardGet,
    )


def guide_sync(provider_id: UUID) -> GuideDetailGet:
    provider: Any = visible_guides().filter(pk=provider_id).first()

    if provider is None:
        raise NotFoundError(detail="No encontramos a ese guía.")

    reviews = (
        Review.objects
        .select_related("author")
        .filter(
            direction="tourist_to_guide",
            hidden_at__isnull=True,
            subject=provider.user,
        )
        .order_by("-created_at")[:PUBLIC_REVIEWS]
    )

    return GuideDetailGet(
        **dict(card_payload(provider)),
        departures=[
            departure_payload(item)
            for item in upcoming_departures()
            .filter(provider=provider)
            .order_by("date", "start_time")
        ],
        reviews=[
            GuideReviewGet(
                author=str(item.author.first_name) or "Turista",
                comment=str(item.comment),
                created_at=item.created_at,
                id=item.pk,
                rating=int(item.rating),
            )
            for item in reviews
        ],
    )


def circuit_departures_sync(circuit_id: UUID) -> list[DepartureGet]:
    return [
        departure_payload(item)
        for item in upcoming_departures()
        .filter(circuit_id=circuit_id)
        .order_by("date", "start_time")
    ]
