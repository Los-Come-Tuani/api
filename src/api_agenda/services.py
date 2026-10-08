from typing import TYPE_CHECKING, Any, Final

from django.db.transaction import atomic
from django.utils.timezone import localdate, now

from api_agenda.models import Event, EventStatus
from api_agenda.schemas import EventGet, ManagedEventGet, OrganizerRef
from api_auth.catalog import FunctionalPermissions as P
from api_catalogs.models import EventCategory
from api_core.services.pages import paginate
from api_core.services.uploads import UploadKinds
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_territory.models import City, PointOfInterest
from api_territory.schemas.common import PillarRef
from api_territory.services.access import Actor, invalid
from api_territory.services.images import (
    check_images,
    current_keys,
    ordered_photos,
    photos_payload,
    replace_photos,
)
from api_territory.services.places import city_ref, coordinate

if TYPE_CHECKING:
    from datetime import date, time
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_agenda.schemas import (
        ClonePost,
        EventPatch,
        EventPost,
        EventQuery,
        PublicEventQuery,
    )
    from api_core.schemas.pagination import Paginated

########################################################################################

NOT_FOUND_DETAIL: Final[str] = "No encontramos ese evento."

SCHEDULED: Final[str] = "programado"
ONGOING: Final[str] = "publicado"
FINISHED: Final[str] = "finalizado"
CANCELLED: Final[str] = "cancelado"

STATUS_API: Final[dict[str, str]] = {
    CANCELLED: "cancelled",
    FINISHED: "finished",
    ONGOING: "ongoing",
    SCHEDULED: "scheduled",
}
STATUS_BY_API: Final[dict[str, str]] = {name: code for code, name in STATUS_API.items()}

# - quién puede programar eventos, además del equipo
ORGANIZER_KINDS: Final[frozenset[str]] = frozenset({"institution", "municipality"})

########################################################################################
# Calendario


def status_row(code: str) -> EventStatus:
    return EventStatus.objects.get(code=code)


# La vigencia la gobierna el calendario (RF-I-02): lo que empezó pasa a en curso y lo
# que terminó, a finalizado. Corre antes de cada lectura y con `syncevents` cada día.
def sync_states() -> None:
    today: date = localdate()

    Event.objects.filter(status__code=SCHEDULED, start_date__lte=today).update(
        status=status_row(ONGOING)
    )
    Event.objects.filter(
        end_date__lt=today,
        status__code__in=(SCHEDULED, ONGOING),
    ).update(status=status_row(FINISHED))


def initial_status(start: date) -> EventStatus:
    return status_row(ONGOING if start <= localdate() else SCHEDULED)


########################################################################################
# Lectura


def events() -> QuerySet:
    return Event.objects.select_related(
        "category",
        "city",
        "institution",
        "municipality",
        "status",
    ).prefetch_related(ordered_photos())


def clock(value: time) -> str:
    return value.strftime("%H:%M")


def organizer_of(event: Event) -> OrganizerRef:
    found: Any = event

    if found.institution is not None:
        return OrganizerRef(
            id=found.institution.pk,
            kind="institution",
            name=str(found.institution.name),
        )

    if found.municipality is not None:
        return OrganizerRef(
            id=found.municipality.pk,
            kind="municipality",
            name=str(found.municipality.name),
        )

    return OrganizerRef(id=None, kind="kplan", name="K'Plan")


def event_payload(event: Event) -> EventGet:
    found: Any = event

    return EventGet(
        address=str(found.address),
        cancellation_reason=str(found.cancellation_reason),
        category=PillarRef(
            code=str(found.category.code), label=str(found.category.label)
        ),
        city=city_ref(found.city),
        cloned_from_id=found.cloned_from_id,
        created_at=found.created_at,
        description=str(found.description),
        end_date=found.end_date,
        end_time=clock(found.end_time),
        entry_price=int(found.entry_price),
        featured=bool(found.featured),
        id=found.pk,
        images=photos_payload(event),
        latitude=float(found.latitude),
        longitude=float(found.longitude),
        name=str(found.name),
        organizer=organizer_of(event),
        point_id=found.point_id,
        start_date=found.start_date,
        start_time=clock(found.start_time),
        status=STATUS_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        venue=str(found.venue),
    )


def managed_payload(event: Event) -> ManagedEventGet:
    found: Any = event

    return ManagedEventGet(
        **dict(event_payload(event)),
        hidden=found.hidden_at is not None,
        hidden_reason=str(found.hidden_reason),
    )


def in_range(found: QuerySet, start: date | None, end: date | None) -> QuerySet:
    # alguno de sus días cae en el rango
    if start is not None:
        found = found.filter(end_date__gte=start)

    if end is not None:
        found = found.filter(start_date__lte=end)

    return found


# Lo que ve la app: lo próximo y lo que está en curso (también lo cancelado, señalado),
# sin lo oculto por moderación.
def public_events_sync(query: PublicEventQuery) -> Paginated[EventGet]:
    sync_states()

    found = events().filter(
        end_date__gte=localdate(),
        hidden_at__isnull=True,
        status__is_visible=True,
    )

    if query.city:
        found = found.filter(city__code=query.city)

    if query.category:
        found = found.filter(category__code=query.category)

    if query.featured is not None:
        found = found.filter(featured=query.featured)

    found = in_range(found, query.from_date, query.to_date)

    return paginate(
        found.order_by("start_date", "start_time", "id"),
        query,
        event_payload,
        EventGet,
    )


def public_event_sync(event_id: UUID) -> EventGet:
    sync_states()

    event: Event | None = (
        events()
        .filter(hidden_at__isnull=True, pk=event_id, status__is_visible=True)
        .first()
    )

    if event is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return event_payload(event)


########################################################################################
# Lo que administra el portal


def organizes(actor: Actor) -> bool:
    return actor.organization is not None and actor.organization.kind in ORGANIZER_KINDS


# El equipo con `content.moderate` ve todos; la institución o la alcaldía, los suyos.
def visible_events(actor: Actor) -> QuerySet:
    found = events()

    if actor.can(P.CONTENT_MODERATE):
        return found

    if organizes(actor):
        organization: Any = actor.organization

        return found.filter(**{f"{organization.kind}_id": organization.id})

    raise ForbiddenError


def visible_event(actor: Actor, event_id: UUID) -> Event:
    event: Event | None = visible_events(actor).filter(pk=event_id).first()

    if event is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return event


def editable_event(actor: Actor, event_id: UUID) -> Event:
    event: Any = visible_event(actor, event_id)

    if not event.status.allows_editing:
        raise ConflictError(detail="Un evento finalizado o cancelado ya no se edita.")

    return event


def events_sync(actor: Actor, query: EventQuery) -> Paginated[ManagedEventGet]:
    sync_states()

    found = visible_events(actor)

    if query.city_id is not None:
        found = found.filter(city_id=query.city_id)

    if query.category:
        found = found.filter(category__code=query.category)

    if query.status is not None:
        found = found.filter(status__code=STATUS_BY_API[query.status])

    if query.search:
        found = found.filter(name__im_unaccent__icontains=query.search.strip())

    found = in_range(found, query.from_date, query.to_date)

    return paginate(
        found.order_by("-start_date", "id"),
        query,
        managed_payload,
        ManagedEventGet,
    )


def event_sync(actor: Actor, event_id: UUID) -> ManagedEventGet:
    sync_states()

    return managed_payload(visible_event(actor, event_id))


########################################################################################
# Validación


def find_category(code: str) -> EventCategory:
    category: EventCategory | None = EventCategory.objects.filter(
        active=True, code=code
    ).first()

    if category is None:
        raise invalid("category", "Esa clase de evento no existe.")

    return category


def find_city(city_id: UUID) -> City:
    city: City | None = City.objects.filter(pk=city_id).first()

    if city is None:
        raise invalid("city_id", "Esa ciudad no existe.")

    return city


def find_point(point_id: UUID | None, city: City) -> PointOfInterest | None:
    if point_id is None:
        return None

    point: Any = PointOfInterest.objects.filter(active=True, pk=point_id).first()

    if point is None or point.city_id != city.pk:
        raise invalid("point_id", "Ese lugar no existe o es de otra ciudad.")

    return point


# Las fechas se comprueban al guardar (RF-I-01): no es una restricción de la tabla,
# porque el evento de ayer tiene que poder seguir existiendo.
def check_dates(start: date, end: date, *, changed: bool = True) -> None:
    if changed and start < localdate():
        raise invalid("start_date", "El evento tiene que empezar hoy o después.")

    if end < start:
        raise invalid("end_date", "El evento no puede terminar antes de empezar.")


def check_times(start: time, end: time) -> None:
    if start == end:
        raise invalid("end_time", "La hora de cierre tiene que ser otra.")


########################################################################################
# Cambios


def organizer_fields(actor: Actor) -> dict[str, Any]:
    # el equipo programa los especiales de K'Plan; la institución o la alcaldía, lo suyo
    if organizes(actor):
        organization: Any = actor.organization

        return {organization.kind: organization.id}

    if actor.can(P.CONTENT_MODERATE):
        return {}

    raise ForbiddenError


def create_event_sync(actor: Actor, data: EventPost) -> ManagedEventGet:
    organizer: dict[str, Any] = organizer_fields(actor)
    city: City = find_city(data.city_id)
    category: EventCategory = find_category(data.category)
    point: PointOfInterest | None = find_point(data.point_id, city)

    check_dates(data.start_date, data.end_date)
    check_times(data.start_time, data.end_time)

    if data.featured and not actor.can(P.CONTENT_MODERATE):
        raise invalid("featured", "Destacar un evento lo decide el equipo.")

    images = check_images(
        data.images, current=[], field="images", kind=UploadKinds.EVENT_PHOTO
    )

    with atomic():
        event: Event = Event.objects.create(
            **{f"{kind}_id": value for kind, value in organizer.items()},
            address=data.address,
            category=category,
            city=city,
            description=data.description,
            end_date=data.end_date,
            end_time=data.end_time,
            entry_price=data.entry_price,
            featured=data.featured,
            latitude=coordinate(data.latitude),
            longitude=coordinate(data.longitude),
            name=data.name,
            point=point,
            start_date=data.start_date,
            start_time=data.start_time,
            status=initial_status(data.start_date),
            venue=data.venue,
        )

        replace_photos("event", event, images)

    return event_sync(actor, event.pk)


def check_schedule_changes(
    actor: Actor,
    record: Event,
    changes: dict[str, Any],
) -> date:
    event: Any = record

    if (
        "featured" in changes
        and changes["featured"] != event.featured
        and not actor.can(P.CONTENT_MODERATE)
    ):
        raise invalid("featured", "Destacar un evento lo decide el equipo.")

    for field in ("start_date", "end_date", "start_time", "end_time"):
        if field in changes and changes[field] is None:
            raise invalid(field, "Este campo no puede quedar vacío.")

    start: date = changes.get("start_date", event.start_date)

    check_dates(
        start,
        changes.get("end_date", event.end_date),
        changed="start_date" in changes and start != event.start_date,
    )
    check_times(
        changes.get("start_time", event.start_time),
        changes.get("end_time", event.end_time),
    )

    return start


def update_event_sync(
    actor: Actor, event_id: UUID, patch: EventPatch
) -> ManagedEventGet:
    event: Any = editable_event(actor, event_id)
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)
    start: date = check_schedule_changes(actor, event, changes)

    if "category" in changes:
        changes["category"] = find_category(changes["category"])

    if "point_id" in changes:
        changes["point"] = find_point(changes.pop("point_id"), event.city)

    for field in ("latitude", "longitude"):
        if field in changes:
            changes[field] = coordinate(changes[field])

    images: list[str] | None = None

    if "images" in changes:
        images = check_images(
            changes.pop("images"),
            current=current_keys("event", event),
            field="images",
            kind=UploadKinds.EVENT_PHOTO,
        )

    if "start_date" in changes and event.status.code == SCHEDULED:
        changes["status"] = initial_status(start)

    with atomic():
        if changes:
            Event.objects.filter(pk=event.pk).update(**changes)

        if images is not None:
            replace_photos("event", event, images)

    return event_sync(actor, event.pk)


# Cancelarlo lo deja visible, señalado, y deja de atraer gente al recinto (RF-I-05).
def cancel_event_sync(actor: Actor, event_id: UUID, reason: str) -> ManagedEventGet:
    event: Event = editable_event(actor, event_id)

    Event.objects.filter(pk=event.pk).update(
        cancellation_reason=reason.strip(),
        status=status_row(CANCELLED),
    )

    return event_sync(actor, event.pk)


# Un atajo para la programación recurrente (RF-I-06): copia todo menos las fechas.
def clone_event_sync(actor: Actor, event_id: UUID, data: ClonePost) -> ManagedEventGet:
    original: Any = visible_event(actor, event_id)

    if not (actor.can(P.CONTENT_MODERATE) or organizes(actor)):
        raise ForbiddenError

    check_dates(data.start_date, data.end_date)

    keys: list[str] = current_keys("event", original)

    with atomic():
        clone: Event = Event.objects.create(
            address=original.address,
            category_id=original.category_id,
            city_id=original.city_id,
            cloned_from=original,
            description=original.description,
            end_date=data.end_date,
            end_time=original.end_time,
            entry_price=original.entry_price,
            institution_id=original.institution_id,
            latitude=original.latitude,
            longitude=original.longitude,
            municipality_id=original.municipality_id,
            name=original.name,
            point_id=original.point_id,
            start_date=data.start_date,
            start_time=original.start_time,
            status=initial_status(data.start_date),
            venue=original.venue,
        )

        replace_photos("event", clone, keys)

    return event_sync(actor, clone.pk)


# Moderación posterior: el equipo con `content.moderate` lo saca de la app o lo
# devuelve.
def hide_event_sync(actor: Actor, event_id: UUID, reason: str) -> ManagedEventGet:
    if not actor.can(P.CONTENT_MODERATE):
        raise ForbiddenError

    event: Event = visible_event(actor, event_id)

    Event.objects.filter(pk=event.pk).update(
        hidden_at=now(), hidden_reason=reason.strip()
    )

    return event_sync(actor, event.pk)


def show_event_sync(actor: Actor, event_id: UUID) -> ManagedEventGet:
    if not actor.can(P.CONTENT_MODERATE):
        raise ForbiddenError

    event: Event = visible_event(actor, event_id)

    Event.objects.filter(pk=event.pk).update(hidden_at=None, hidden_reason="")

    return event_sync(actor, event.pk)
