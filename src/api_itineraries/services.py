from datetime import time
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Prefetch
from django.db.transaction import atomic
from django.utils.timezone import now

from api_exceptions.errors import ConflictError, NotFoundError
from api_itineraries.models import (
    Itinerary,
    ItineraryCircuit,
    ItineraryStatus,
    ItineraryStop,
)
from api_itineraries.schemas import (
    FollowedCircuitRef,
    ItineraryGet,
    ItineraryStopGet,
)
from api_territory.models import Circuit, CircuitStop, PointOfInterest
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_itineraries.schemas import ItineraryPatch, ItineraryPost

########################################################################################

NOT_FOUND_DETAIL: Final[str] = "No encontramos ese itinerario."

PLANNED: Final[str] = "planificado"
IN_PROGRESS: Final[str] = "en_curso"
DELETED: Final[str] = "eliminado"

STATUS_API: Final[dict[str, str]] = {
    "completado": "completed",
    IN_PROGRESS: "in_progress",
    PLANNED: "planned",
}

DEFAULT_START: Final[time] = time(9, 0)

########################################################################################
# Lectura


def own_itineraries(user: ApiUser) -> QuerySet:
    return (
        Itinerary.objects
        .select_related("status", "followed_circuit__status")
        .prefetch_related(
            Prefetch("stops", queryset=ItineraryStop.objects.order_by("order")),
            Prefetch("origins", queryset=ItineraryCircuit.objects.order_by("order")),
        )
        .filter(deleted_at__isnull=True, user=user)
    )


def own_itinerary(user: ApiUser, itinerary_id: UUID) -> Itinerary:
    found: Itinerary | None = own_itineraries(user).filter(pk=itinerary_id).first()

    # el de otra persona no existe para quien pregunta
    if found is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return found


def circuit_stops(circuit: Circuit) -> list[ItineraryStopGet]:
    return [
        ItineraryStopGet(
            latitude=float(stop.point.latitude),
            longitude=float(stop.point.longitude),
            name=str(stop.point.name),
            order=int(stop.order),
            point_id=stop.point_id,
            visited_at=None,
        )
        for stop in CircuitStop.objects
        .select_related("point")
        .filter(circuit=circuit)
        .order_by("order")
    ]


def itinerary_payload(itinerary: Itinerary) -> ItineraryGet:
    found: Any = itinerary
    circuit: Any = found.followed_circuit

    if found.adjusted or circuit is None:
        stops = [
            ItineraryStopGet(
                latitude=float(stop.latitude),
                longitude=float(stop.longitude),
                name=str(stop.name),
                order=int(stop.order),
                point_id=stop.point_id,
                visited_at=stop.visited_at,
            )
            for stop in found.stops.all()
        ]
    else:
        stops = circuit_stops(circuit)

    return ItineraryGet(
        adjusted=bool(found.adjusted),
        created_at=found.created_at,
        fixed_arrivals={
            str(key): int(value) for key, value in found.fixed_arrivals.items()
        },
        followed_circuit=(
            None
            if circuit is None
            else FollowedCircuitRef(
                id=circuit.pk,
                published=bool(circuit.status.is_visible),
                title=str(circuit.title),
                version=int(circuit.version),
            )
        ),
        id=found.pk,
        origin_circuit_ids=[origin.circuit_id for origin in found.origins.all()],
        pace=found.pace,
        start_time=found.start_time.strftime("%H:%M")
        if isinstance(found.start_time, time)
        else str(found.start_time)[:5],
        status=STATUS_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        stops=stops,
        title=str(found.title),
        travel_mode=found.travel_mode,
    )


def itineraries_sync(user: ApiUser) -> list[ItineraryGet]:
    return [
        itinerary_payload(item)
        for item in own_itineraries(user).order_by("-created_at", "id")
    ]


def itinerary_sync(user: ApiUser, itinerary_id: UUID) -> ItineraryGet:
    return itinerary_payload(own_itinerary(user, itinerary_id))


########################################################################################
# Cambios


def status_row(code: str) -> ItineraryStatus:
    return ItineraryStatus.objects.get(code=code)


def published_circuit(circuit_id: UUID) -> Circuit:
    circuit: Circuit | None = Circuit.objects.filter(
        pk=circuit_id, status__code="publicado"
    ).first()

    if circuit is None:
        raise invalid("circuit_id", "Ese circuito no existe o no está publicado.")

    return circuit


def active_points(ids: list[UUID]) -> list[PointOfInterest]:
    if len(set(ids)) != len(ids):
        raise invalid("stop_ids", "Una parada está repetida.")

    found: dict[UUID, PointOfInterest] = {
        point.pk: point
        for point in PointOfInterest.objects.filter(active=True, pk__in=ids)
    }

    for index, point_id in enumerate(ids):
        if point_id not in found:
            raise invalid(f"stop_ids.{index}", "Ese lugar no existe o se retiró.")

    return [found[point_id] for point_id in ids]


# Las paradas propias son copias (D-16): nombre y coordenadas del lugar; lo visitado
# antes se conserva si el lugar sigue en la lista.
def write_copies(itinerary: Itinerary, points: list[PointOfInterest]) -> None:
    visited: dict[UUID, Any] = {
        stop.point_id: stop.visited_at
        for stop in ItineraryStop.objects.filter(itinerary=itinerary)
        if stop.point_id is not None
    }

    ItineraryStop.objects.filter(itinerary=itinerary).delete()
    ItineraryStop.objects.bulk_create(
        ItineraryStop(
            itinerary=itinerary,
            latitude=point.latitude,
            longitude=point.longitude,
            name=point.name,
            order=order,
            point=point,
            visited_at=visited.get(point.pk),
        )
        for order, point in enumerate(points)
    )


def add_origin(itinerary: Itinerary, circuit: Circuit) -> None:
    ItineraryCircuit.objects.get_or_create(circuit=circuit, itinerary=itinerary)


def create_itinerary_sync(user: ApiUser, data: ItineraryPost) -> ItineraryGet:
    circuit: Any = (
        None if data.circuit_id is None else published_circuit(data.circuit_id)
    )
    points: list[PointOfInterest] | None = (
        None if data.stop_ids is None else active_points(data.stop_ids)
    )

    # sin paradas propias sigue el circuito tal cual; con ellas (o sin circuito) es una
    # copia propia desde el principio
    follows: bool = circuit is not None and points is None

    with atomic():
        itinerary: Itinerary = Itinerary.objects.create(
            adjusted=not follows,
            fixed_arrivals=dict(data.fixed_arrivals),
            followed_circuit=circuit if follows else None,
            pace=data.pace,
            start_time=data.start_time or DEFAULT_START,
            status=status_row(PLANNED),
            title=data.title,
            travel_mode=data.travel_mode
            or (circuit.travel_mode if circuit is not None else "walking"),
            user=user,
        )

        if circuit is not None:
            add_origin(itinerary, circuit)

        if points is not None:
            write_copies(itinerary, points)

    return itinerary_sync(user, itinerary.pk)


def update_itinerary_sync(
    user: ApiUser,
    itinerary_id: UUID,
    patch: ItineraryPatch,
) -> ItineraryGet:
    itinerary: Any = own_itinerary(user, itinerary_id)

    if not itinerary.status.allows_editing:
        raise ConflictError(detail="Un itinerario completado ya no se edita.")

    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
    stop_ids: list[UUID] | None = changes.pop("stop_ids", None)

    if "start_time" in changes and changes["start_time"] is None:
        changes["start_time"] = DEFAULT_START

    points: list[PointOfInterest] | None = None

    if stop_ids is not None:
        points = active_points(stop_ids)

        # lo mismo que el circuito que sigue no es un ajuste
        if (
            not itinerary.adjusted
            and itinerary.followed_circuit is not None
            and [stop.point_id for stop in circuit_stops(itinerary.followed_circuit)]
            == [point.pk for point in points]
        ):
            points = None

    with atomic():
        if points is not None and not itinerary.adjusted:
            # el primer ajuste suelta el circuito vivo y copia: no se revierte (D-33)
            changes["adjusted"] = True
            changes["followed_circuit"] = None

        if changes:
            Itinerary.objects.filter(pk=itinerary.pk).update(**changes)

        if points is not None:
            write_copies(itinerary, points)

    return itinerary_sync(user, itinerary.pk)


def delete_itinerary_sync(user: ApiUser, itinerary_id: UUID) -> None:
    itinerary: Any = own_itinerary(user, itinerary_id)

    if itinerary.status.code == IN_PROGRESS:
        raise ConflictError(detail="Un recorrido en curso no se descarta.")

    Itinerary.objects.filter(pk=itinerary.pk).update(
        deleted_at=now(),
        status=status_row(DELETED),
    )
