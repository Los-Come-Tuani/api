from typing import TYPE_CHECKING, Any, Final

from django.db.models import F, Prefetch, Q
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_core.services.pages import paginate
from api_core.services.uploads import UploadKinds
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_services.services.departures import cancel_circuit_departures
from api_territory.models import (
    Circuit,
    CircuitStatus,
    CircuitStop,
    City,
    Municipality,
    PointOfInterest,
)
from api_territory.schemas.circuit import (
    CircuitGet,
    CircuitInlineGet,
    CircuitStopGet,
    MunicipalityRef,
    RoutePointGet,
)

from .access import Actor, invalid
from .images import (
    check_images,
    current_keys,
    ordered_photos,
    photos_payload,
    replace_photos,
)
from .legs import estimated_leg
from .places import (
    RELATED as POINT_RELATED,
    city_ref,
    coordinate,
    stop_payload,
)

if TYPE_CHECKING:
    from datetime import time
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_territory.schemas.circuit import (
        CircuitPost,
        CircuitPut,
        CircuitQuery,
        PublicCircuitQuery,
    )

########################################################################################

NOT_FOUND_DETAIL: Final[str] = "No encontramos ese circuito."

DRAFT: Final[str] = "borrador"
PUBLISHED: Final[str] = "publicado"
UNPUBLISHED: Final[str] = "despublicado"
RETIRED: Final[str] = "retirado"

STATUS_API: Final[dict[str, str]] = {
    DRAFT: "draft",
    PUBLISHED: "published",
    RETIRED: "retired",
    UNPUBLISHED: "unpublished",
}
STATUS_BY_API: Final[dict[str, str]] = {name: code for code, name in STATUS_API.items()}

# - los creativos dan tres insignias extra al completarlos (la medalla de la ciudad)
CREATIVE_BONUS_BADGES: Final[int] = 3

WITHDRAWN_REASON: Final[str] = "El circuito ya no está disponible en K'Plan."

########################################################################################
# Lectura


def circuits() -> QuerySet:
    stops = (
        CircuitStop.objects
        .select_related(*(f"point__{field}" for field in POINT_RELATED))
        .prefetch_related(ordered_photos("point__"))
        .order_by("order")
    )

    return Circuit.objects.select_related(
        "city", "municipality", "status"
    ).prefetch_related(
        Prefetch("stops", queryset=stops),
        ordered_photos(),
    )


def clock(value: time) -> str:
    return value.strftime("%H:%M")


# La visita de cada parada más el traslado desde la anterior: el escrito a mano o, si no
# hay, el que estiman el portal y la app con la distancia.
def duration_of(stops: list[Any], travel_mode: str) -> int:
    total: int = 0

    for index, stop in enumerate(stops):
        total += int(stop.point.visit_minutes)

        if index == 0:
            continue

        total += (
            int(stop.leg_minutes)
            if stop.leg_minutes is not None
            else estimated_leg(stops[index - 1].point, stop.point, travel_mode)
        )

    return total


def inline_payload(circuit: Circuit) -> CircuitInlineGet:
    found: Any = circuit
    stops: list[Any] = list(found.stops.all())

    return CircuitInlineGet(
        available_from=found.available_from,
        available_until=found.available_until,
        badges=sum(1 for stop in stops if stop.point.has_badge)
        + int(found.bonus_badges),
        bonus_badges=int(found.bonus_badges),
        booking_mode=found.booking_mode,
        category=found.category,
        city=city_ref(found.city),
        created_at=found.created_at,
        description=str(found.description),
        difficulty=found.difficulty,
        duration_minutes=duration_of(stops, str(found.travel_mode)),
        id=found.pk,
        images=photos_payload(circuit),
        includes=str(found.includes),
        kind=found.kind,
        meeting_latitude=float(found.meeting_latitude),
        meeting_longitude=float(found.meeting_longitude),
        meeting_point=str(found.meeting_point),
        municipality=(
            None
            if found.municipality is None
            else MunicipalityRef(
                id=found.municipality.pk, name=str(found.municipality.name)
            )
        ),
        notes=str(found.notes),
        price_adult=int(found.price_adult),
        price_child=int(found.price_child),
        published_at=found.published_at,
        rating=float(found.rating),
        recommendations=str(found.recommendations),
        reviews_count=int(found.reviews_count),
        route=[
            RoutePointGet(
                latitude=float(stop.point.latitude),
                leg_minutes=stop.leg_minutes,
                longitude=float(stop.point.longitude),
                name=str(stop.point.name),
                point_id=stop.point_id,
                visit_minutes=int(stop.point.visit_minutes),
            )
            for stop in stops
        ],
        short_title=str(found.short_title),
        start_times=[clock(value) for value in found.start_times],
        status=STATUS_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        stop_ids=[stop.point_id for stop in stops],
        subtitle=str(found.subtitle),
        title=str(found.title),
        travel_mode=found.travel_mode,
        version=int(found.version),
    )


def circuit_payload(circuit: Circuit) -> CircuitGet:
    found: Any = circuit

    return CircuitGet(
        **dict(inline_payload(circuit)),
        stops=[
            CircuitStopGet(
                directions=str(stop.directions),
                leg_minutes=stop.leg_minutes,
                order=int(stop.order),
                point=stop_payload(stop.point),
            )
            for stop in found.stops.all()
        ],
    )


########################################################################################
# Lo que ve la app (sin sesión): solo lo publicado


def public_circuits_sync(query: PublicCircuitQuery) -> list[CircuitInlineGet]:
    found = circuits().filter(status__code=PUBLISHED)

    if query.city:
        found = found.filter(city__code=query.city)

    if query.kind is not None:
        found = found.filter(kind=query.kind)

    return [
        inline_payload(item) for item in found.order_by("city__name", "title", "id")
    ]


def public_circuit_sync(circuit_id: UUID) -> CircuitGet:
    circuit: Circuit | None = (
        circuits().filter(pk=circuit_id, status__code=PUBLISHED).first()
    )

    if circuit is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return circuit_payload(circuit)


########################################################################################
# Lo que administra el portal


def municipality_of(actor: Actor) -> Municipality | None:
    if actor.organization is None or not actor.operates("municipality"):
        return None

    return (
        Municipality.objects
        .select_related("city")
        .filter(pk=actor.organization.id)
        .first()
    )


# El equipo con `circuits.view` ve todos; la alcaldía, los de su ciudad (RF-A-03): los
# de otra ciudad no existen para ella, ni por identificador.
def visible_circuits(actor: Actor) -> QuerySet:
    found = circuits()

    if actor.can(P.CIRCUITS_VIEW):
        return found

    municipality: Any = municipality_of(actor)

    if municipality is not None:
        return found.filter(city_id=municipality.city_id)

    raise ForbiddenError


def visible_circuit(actor: Actor, circuit_id: UUID) -> Circuit:
    circuit: Circuit | None = visible_circuits(actor).filter(pk=circuit_id).first()

    if circuit is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return circuit


# Edita el equipo con `circuits.manage`; la alcaldía, solo los que organiza ella.
def editable_circuit(actor: Actor, circuit_id: UUID) -> Circuit:
    circuit: Any = visible_circuit(actor, circuit_id)

    if not actor.can(P.CIRCUITS_MANAGE):
        municipality: Any = municipality_of(actor)

        if municipality is None or circuit.municipality_id != municipality.pk:
            raise ForbiddenError

    if circuit.status.is_terminal:
        raise ConflictError(detail="Un circuito retirado ya no se edita.")

    return circuit


def circuits_sync(actor: Actor, query: CircuitQuery) -> Paginated[CircuitInlineGet]:
    found = visible_circuits(actor)

    if query.status is None:
        found = found.exclude(status__code=RETIRED)
    else:
        found = found.filter(status__code=STATUS_BY_API[query.status])

    if query.city_id is not None:
        found = found.filter(city_id=query.city_id)

    if query.kind is not None:
        found = found.filter(kind=query.kind)

    if query.search:
        term: str = query.search.strip()
        found = found.filter(
            Q(title__im_unaccent__icontains=term)
            | Q(short_title__im_unaccent__icontains=term)
        )

    return paginate(
        found.order_by("city__name", "title", "id"),
        query,
        inline_payload,
        CircuitInlineGet,
    )


def circuit_sync(actor: Actor, circuit_id: UUID) -> CircuitGet:
    return circuit_payload(visible_circuit(actor, circuit_id))


########################################################################################
# Validación


# De quién es y dónde: el equipo elige tipo y ciudad (el creativo es de la alcaldía de
# esa ciudad); la alcaldía solo hace creativos de su ciudad.
def placement(actor: Actor, data: CircuitPost) -> tuple[str, City, Municipality | None]:
    if actor.can(P.CIRCUITS_MANAGE):
        if data.city_id is None:
            raise invalid("city_id", "Elige la ciudad del circuito.")

        city: City | None = City.objects.filter(pk=data.city_id).first()

        if city is None:
            raise invalid("city_id", "Esa ciudad no existe.")

        if data.kind != "creative":
            return data.kind, city, None

        organizer: Municipality | None = Municipality.objects.filter(
            city=city, verified_at__isnull=False
        ).first()

        if organizer is None:
            raise invalid(
                "kind",
                "Un circuito creativo es de la alcaldía, y esa ciudad no tiene una "
                "verificada.",
            )

        return data.kind, city, organizer

    municipality: Any = municipality_of(actor)

    if municipality is None:
        raise ForbiddenError

    if data.city_id is not None and data.city_id != municipality.city_id:
        raise invalid("city_id", "Solo puedes publicar circuitos de tu ciudad.")

    return "creative", municipality.city, municipality


def checked_stops(data: CircuitPost, city: City) -> list[PointOfInterest]:
    ids: list[UUID] = [stop.point_id for stop in data.stops]

    if len(set(ids)) != len(ids):
        raise invalid("stops", "Un lugar no se visita dos veces en el mismo recorrido.")

    found: dict[UUID, PointOfInterest] = {
        point.pk: point for point in PointOfInterest.objects.filter(pk__in=ids)
    }

    for index, point_id in enumerate(ids):
        point: Any = found.get(point_id)

        if point is None or not point.active:
            raise invalid(f"stops.{index}.point_id", "Ese lugar no existe o se retiró.")

        if point.city_id != city.pk:
            raise invalid(f"stops.{index}.point_id", "Ese lugar es de otra ciudad.")

    return [found[point_id] for point_id in ids]


def kind_rules(kind: str, data: CircuitPost) -> dict[str, Any]:
    # lo que fija cada tipo: el creativo siempre es en grupo y da tres insignias; el
    # del catálogo, privado y sin extras; el especial elige y da al menos una
    if kind == "creative":
        return {
            "available_from": None,
            "available_until": None,
            "bonus_badges": CREATIVE_BONUS_BADGES,
            "booking_mode": "group",
        }

    if kind == "private":
        return {
            "available_from": None,
            "available_until": None,
            "bonus_badges": 0,
            "booking_mode": "private",
        }

    if data.bonus_badges < 1:
        raise invalid("bonus_badges", "Un especial de K'Plan da al menos una insignia.")

    if (data.available_from is None) != (data.available_until is None):
        raise invalid("available_until", "La temporada lleva las dos fechas o ninguna.")

    if (
        data.available_from is not None
        and data.available_until is not None
        and data.available_until < data.available_from
    ):
        raise invalid("available_until", "La temporada termina antes de empezar.")

    return {
        "available_from": data.available_from,
        "available_until": data.available_until,
        "bonus_badges": data.bonus_badges,
        "booking_mode": data.booking_mode,
    }


def check_publishable(data: CircuitPost, images: list[str]) -> None:
    if data.status != "published":
        return

    if not images:
        raise invalid("images", "Para publicarlo hace falta al menos una foto.")

    if not data.start_times:
        raise invalid("start_times", "Para publicarlo hace falta al menos un horario.")


def fields_of(data: CircuitPost) -> dict[str, Any]:
    if len(set(data.start_times)) != len(data.start_times):
        raise invalid("start_times", "Hay un horario repetido.")

    return {
        "category": data.category,
        "description": data.description,
        "difficulty": data.difficulty,
        "includes": data.includes,
        "meeting_latitude": coordinate(data.meeting_latitude),
        "meeting_longitude": coordinate(data.meeting_longitude),
        "meeting_point": data.meeting_point,
        "notes": data.notes,
        "price_adult": data.price_adult,
        "price_child": data.price_child,
        "recommendations": data.recommendations,
        "short_title": data.short_title,
        "start_times": sorted(data.start_times),
        "subtitle": data.subtitle,
        "title": data.title,
        "travel_mode": data.travel_mode,
    }


def write_stops(
    circuit: Circuit, data: CircuitPost, points: list[PointOfInterest]
) -> None:
    CircuitStop.objects.filter(circuit=circuit).delete()
    CircuitStop.objects.bulk_create(
        CircuitStop(
            circuit=circuit,
            directions=stop.directions,
            leg_minutes=stop.leg_minutes,
            order=order,
            point=point,
        )
        for order, (stop, point) in enumerate(zip(data.stops, points, strict=True))
    )


def status_row(code: str) -> CircuitStatus:
    return CircuitStatus.objects.get(code=code)


########################################################################################
# Cambios


def create_circuit_sync(actor: Actor, data: CircuitPost) -> CircuitGet:
    kind, city, municipality = placement(actor, data)
    points: list[PointOfInterest] = checked_stops(data, city)
    rules: dict[str, Any] = kind_rules(kind, data)
    fields: dict[str, Any] = fields_of(data)
    images: list[str] = check_images(
        data.images,
        current=[],
        field="images",
        kind=UploadKinds.CIRCUIT_PHOTO,
    )

    check_publishable(data, images)

    published: bool = data.status == "published"

    with atomic():
        circuit: Circuit = Circuit.objects.create(
            **fields,
            **rules,
            city=city,
            kind=kind,
            municipality=municipality,
            published_at=now() if published else None,
            status=status_row(PUBLISHED if published else DRAFT),
        )

        write_stops(circuit, data, points)
        replace_photos("circuit", circuit, images)

    return circuit_sync(actor, circuit.pk)


def next_status(current: str, requested: str, *, was_published: bool) -> str:
    if requested == "published":
        return PUBLISHED

    if requested == "unpublished":
        # lo que nunca se publicó sigue siendo un borrador
        return UNPUBLISHED if was_published or current == PUBLISHED else DRAFT

    return DRAFT if not was_published else UNPUBLISHED


def update_circuit_sync(actor: Actor, circuit_id: UUID, data: CircuitPut) -> CircuitGet:
    circuit: Any = editable_circuit(actor, circuit_id)

    # la alcaldía no cambia el tipo ni la ciudad: siguen siendo los suyos
    kind, city, municipality = placement(actor, data)
    points: list[PointOfInterest] = checked_stops(data, city)
    rules: dict[str, Any] = kind_rules(kind, data)
    fields: dict[str, Any] = fields_of(data)
    images: list[str] = check_images(
        data.images,
        current=current_keys("circuit", circuit),
        field="images",
        kind=UploadKinds.CIRCUIT_PHOTO,
    )

    check_publishable(data, images)

    status: str = next_status(
        str(circuit.status.code),
        data.status,
        was_published=circuit.published_at is not None,
    )
    geometry_changed: bool = [stop.point_id for stop in circuit.stops.all()] != [
        point.pk for point in points
    ]

    with atomic():
        Circuit.objects.filter(pk=circuit.pk).update(
            **fields,
            **rules,
            city=city,
            kind=kind,
            municipality=municipality,
            published_at=(
                now()
                if status == PUBLISHED and circuit.published_at is None
                else circuit.published_at
            ),
            status=status_row(status),
            version=F("version") + 1 if geometry_changed else F("version"),
        )

        write_stops(circuit, data, points)
        replace_photos("circuit", circuit, images)

        if circuit.status.code == PUBLISHED and status != PUBLISHED:
            cancel_circuit_departures(
                circuit.pk, by=actor.user, reason=WITHDRAWN_REASON
            )

    return circuit_sync(actor, circuit.pk)


# Retirar es definitivo (RF-A-09): sale de la app y ya no se edita, pero los itinerarios
# que lo siguen o que salieron de él lo conservan. Sus próximas salidas se cancelan.
def retire_circuit_sync(actor: Actor, circuit_id: UUID) -> None:
    circuit: Circuit = editable_circuit(actor, circuit_id)

    with atomic():
        Circuit.objects.filter(pk=circuit.pk).update(status=status_row(RETIRED))
        cancel_circuit_departures(circuit.pk, by=actor.user, reason=WITHDRAWN_REASON)
