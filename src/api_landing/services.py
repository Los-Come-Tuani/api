from typing import TYPE_CHECKING, Any, Final

from django.db.models import F, Q
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_auth.services.roles import holders_of_sync
from api_core.services.pages import paginate
from api_exceptions.enums import RequestScopes
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_landing.models import AppRelease, DemoRequest
from api_landing.schemas import (
    AppReleaseGet,
    DeliveredLink,
    DemoRequestGet,
    DemoRequestResult,
    LatestReleaseGet,
)
from api_notifications.services import notify

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_landing.schemas import (
        AppReleasePatch,
        AppReleasePost,
        AppReleaseQuery,
        DemoRequestPatch,
        DemoRequestPost,
        DemoRequestQuery,
    )
    from api_territory.services.access import Actor

########################################################################################

DEMO_KIND_API: Final[dict[str, str]] = {
    "alcaldia": "municipality",
    "comercio": "business",
    "institucion": "institution",
    "operador": "tour_operator",
    "otro": "other",
}
DEMO_KIND_BY_API: Final[dict[str, str]] = {
    name: code for code, name in DEMO_KIND_API.items()
}

DEMO_STATUS_API: Final[dict[str, str]] = {
    "entregada": "delivered",
    "pendiente": "pending",
}
DEMO_STATUS_BY_API: Final[dict[str, str]] = {
    name: code for code, name in DEMO_STATUS_API.items()
}

RELEASE_STATUS_API: Final[dict[str, str]] = {
    "borrador": "draft",
    "publicada": "published",
    "retirada": "withdrawn",
}
RELEASE_STATUS_BY_API: Final[dict[str, str]] = {
    name: code for code, name in RELEASE_STATUS_API.items()
}

PLATFORM_LABELS: Final[dict[str, str]] = {
    "android": "Android",
    "macos": "macOS",
    "windows": "Windows",
}

# - la clase de aviso que reciben quienes atienden las solicitudes de demo
DEMO_NOTICE_KIND: Final[str] = "solicitud_demo"

########################################################################################
# Solicitudes de demo: las manda cualquiera desde la landing


def delivery(*, delivered: bool, at: datetime) -> dict[str, object]:
    if delivered:
        return {"delivered_at": at, "status": "entregada"}

    return {"delivered_at": None, "status": "pendiente"}


def submit_demo_request_sync(data: DemoRequestPost) -> DemoRequestResult:
    current: list[Any] = list(current_releases())
    result = DemoRequestResult(
        delivered=bool(current),
        links=[
            DeliveredLink(
                link=str(release.link),
                platform=str(release.platform),  # ty: ignore[invalid-argument-type]
                version=str(release.version),
            )
            for release in current
        ],
    )

    # el campo trampa llegó lleno: lo mandó un bot. Se responde igual que a una persona
    # para que no aprenda a esquivarlo, pero no se guarda nada
    if data.website:
        return result

    fields: dict[str, object] = {
        "city": data.city,
        "email": data.email,
        "kind": DEMO_KIND_BY_API[data.kind],
        "message": data.message,
        "name": data.name,
        "organization": data.organization,
        "phone": data.phone,
        **delivery(delivered=result.delivered, at=now()),
    }

    with atomic():
        pending: Any = (
            DemoRequest.objects
            .select_for_update()
            .filter(email=data.email, status="pendiente")
            .order_by("-created_at")
            .first()
        )

        AppRelease.objects.filter(pk__in=[release.pk for release in current]).update(
            deliveries=F("deliveries") + 1
        )

        # la misma persona la vuelve a mandar antes de que el equipo le entregue los
        # links: se corrige la que ya está en la bandeja, sin otro aviso
        if pending is not None:
            DemoRequest.objects.filter(pk=pending.pk).update(**fields)
            return result

        request: DemoRequest = DemoRequest.objects.create(**fields)
        followup: str = (
            "Ya recibió los links de descarga."
            if result.delivered
            else "No hay una versión publicada: hay que hacerle llegar el link."
        )

        for user_id in holders_of_sync(P.DEMOS_MANAGE):
            notify(
                user_id,
                DEMO_NOTICE_KIND,
                "Nueva solicitud de demo",
                f"{data.name} ({data.organization}) pidió una demostración. {followup}",
                {"demo_request_id": str(request.pk)},
            )

    return result


########################################################################################
# La bandeja del equipo (`demos.view`; atender, `demos.manage`)


def demo_payload(request: DemoRequest) -> DemoRequestGet:
    found: Any = request

    return DemoRequestGet(
        city=str(found.city),
        created_at=found.created_at,
        delivered_at=found.delivered_at,
        email=str(found.email),
        id=found.pk,
        kind=DEMO_KIND_API[str(found.kind)],  # ty: ignore[invalid-argument-type]
        message=str(found.message),
        name=str(found.name),
        notes=str(found.notes),
        organization=str(found.organization),
        phone=str(found.phone),
        status=DEMO_STATUS_API[str(found.status)],  # ty: ignore[invalid-argument-type]
        updated_at=found.updated_at,
        updated_by=(
            found.updated_by.display_name if found.updated_by is not None else None
        ),
    )


def demo_requests() -> QuerySet:
    return DemoRequest.objects.select_related("updated_by")


def ensure_demo_viewer(actor: Actor) -> None:
    if not actor.can(P.DEMOS_VIEW, P.DEMOS_MANAGE):
        raise ForbiddenError


def demo_requests_sync(
    actor: Actor, query: DemoRequestQuery
) -> Paginated[DemoRequestGet]:
    ensure_demo_viewer(actor)

    found = demo_requests()

    if query.status is not None:
        found = found.filter(status=DEMO_STATUS_BY_API[query.status])

    if query.search and (term := query.search.strip()):
        found = found.filter(
            Q(name__im_unaccent__icontains=term)
            | Q(email__icontains=term)
            | Q(organization__im_unaccent__icontains=term)
        )

    return paginate(
        found.order_by("-created_at", "id"), query, demo_payload, DemoRequestGet
    )


def find_demo_request(request_id: UUID) -> DemoRequest:
    found: DemoRequest | None = demo_requests().filter(pk=request_id).first()

    if found is None:
        raise NotFoundError(detail="No encontramos esa solicitud de demo.")

    return found


def demo_request_sync(actor: Actor, request_id: UUID) -> DemoRequestGet:
    ensure_demo_viewer(actor)

    return demo_payload(find_demo_request(request_id))


def update_demo_request_sync(
    actor: Actor,
    request_id: UUID,
    data: DemoRequestPatch,
) -> DemoRequestGet:
    if not actor.can(P.DEMOS_MANAGE):
        raise ForbiddenError

    with atomic():
        request: Any = find_demo_request(request_id)
        changes: dict[str, object] = {}

        # la fecha de entrega se conserva si el estado no cambia
        if data.status is not None:
            status: str = DEMO_STATUS_BY_API[data.status]

            if status != request.status:
                changes |= delivery(delivered=status == "entregada", at=now())

        if data.notes is not None:
            changes["notes"] = data.notes

        if changes:
            DemoRequest.objects.filter(pk=request.pk).update(
                **changes, updated_at=now(), updated_by=actor.user
            )

    return demo_payload(find_demo_request(request_id))


########################################################################################
# Versiones de la app: el equipo con `releases.manage` las crea y publica


def ensure_publisher(actor: Actor) -> None:
    if not actor.can(P.RELEASES_MANAGE):
        raise ForbiddenError


def current_releases() -> QuerySet:
    # la publicada más reciente de cada plataforma (`DISTINCT ON`)
    return (
        AppRelease.objects
        .filter(status="publicada")
        .order_by("platform", "-published_at", "-id")
        .distinct("platform")
    )


def current_ids() -> frozenset[UUID]:
    return frozenset(current_releases().values_list("pk", flat=True))


def release_payload(release: AppRelease, current: frozenset[UUID]) -> AppReleaseGet:
    found: Any = release

    return AppReleaseGet(
        created_at=found.created_at,
        created_by=found.created_by.display_name,
        current=found.pk in current,
        deliveries=int(found.deliveries),
        id=found.pk,
        link=str(found.link),
        notes=str(found.notes),
        platform=str(found.platform),  # ty: ignore[invalid-argument-type]
        published_at=found.published_at,
        status=RELEASE_STATUS_API[str(found.status)],  # ty: ignore[invalid-argument-type]
        version=str(found.version),
        withdrawn_at=found.withdrawn_at,
    )


def releases() -> QuerySet:
    return AppRelease.objects.select_related("created_by")


def find_release(release_id: UUID, *, lock: bool = False) -> AppRelease:
    found = AppRelease.objects.select_for_update() if lock else releases()
    release: AppRelease | None = found.filter(pk=release_id).first()

    if release is None:
        raise NotFoundError(detail="No encontramos esa versión.")

    return release


def reload_release(release_id: UUID) -> AppReleaseGet:
    return release_payload(releases().get(pk=release_id), current_ids())


def ensure_version_free(
    platform: str, version: str, *, but: UUID | None = None
) -> None:
    taken = AppRelease.objects.filter(platform=platform, version=version)

    if but is not None:
        taken = taken.exclude(pk=but)

    if taken.exists():
        message: str = (
            f"Ya existe la versión {version} para {PLATFORM_LABELS[platform]}."
        )

        raise ConflictError(
            detail=message,
            field_errors={"version": message},
        ).scoped(RequestScopes.BODY)


def releases_sync(actor: Actor, query: AppReleaseQuery) -> Paginated[AppReleaseGet]:
    if not actor.can(P.RELEASES_VIEW, P.RELEASES_MANAGE):
        raise ForbiddenError

    found = releases()

    if query.platform is not None:
        found = found.filter(platform=query.platform)

    if query.status is not None:
        found = found.filter(status=RELEASE_STATUS_BY_API[query.status])

    current: frozenset[UUID] = current_ids()

    return paginate(
        found.order_by("-created_at", "id"),
        query,
        lambda release: release_payload(release, current),
        AppReleaseGet,
    )


def create_release_sync(actor: Actor, data: AppReleasePost) -> AppReleaseGet:
    ensure_publisher(actor)
    ensure_version_free(data.platform, data.version)

    release: AppRelease = AppRelease.objects.create(
        created_by=actor.user,
        link=data.link,
        notes=data.notes,
        platform=data.platform,
        version=data.version,
    )

    return reload_release(release.pk)


def update_release_sync(
    actor: Actor,
    release_id: UUID,
    data: AppReleasePatch,
) -> AppReleaseGet:
    ensure_publisher(actor)

    with atomic():
        release: Any = find_release(release_id, lock=True)
        changes: dict[str, str] = {}

        if data.version is not None and data.version != release.version:
            if release.status != "borrador":
                raise ConflictError(
                    detail="La versión solo cambia mientras es un borrador."
                )

            ensure_version_free(release.platform, data.version, but=release.pk)
            changes["version"] = data.version

        if data.notes is not None:
            changes["notes"] = data.notes

        if data.link is not None:
            changes["link"] = data.link

        if changes:
            AppRelease.objects.filter(pk=release.pk).update(**changes)

    return reload_release(release_id)


def publish_release_sync(actor: Actor, release_id: UUID) -> AppReleaseGet:
    ensure_publisher(actor)

    with atomic():
        release: Any = find_release(release_id, lock=True)

        if release.status == "publicada":
            raise ConflictError(detail="Esa versión ya está publicada.")

        AppRelease.objects.filter(pk=release.pk).update(
            published_at=now(),
            published_by=actor.user,
            status="publicada",
            withdrawn_at=None,
        )

    return reload_release(release_id)


def withdraw_release_sync(actor: Actor, release_id: UUID) -> AppReleaseGet:
    ensure_publisher(actor)

    with atomic():
        release: Any = find_release(release_id, lock=True)

        if release.status != "publicada":
            raise ConflictError(detail="Solo se retira una versión publicada.")

        AppRelease.objects.filter(pk=release.pk).update(
            status="retirada", withdrawn_at=now()
        )

    return reload_release(release_id)


def delete_release_sync(actor: Actor, release_id: UUID) -> None:
    ensure_publisher(actor)

    with atomic():
        release: Any = find_release(release_id, lock=True)

        if release.status != "borrador":
            raise ConflictError(
                detail="Solo se borra un borrador; una versión publicada se retira."
            )

        AppRelease.objects.filter(pk=release.pk).delete()


########################################################################################
# Lo que ve la landing: público y sin los links


def latest_releases_sync() -> list[LatestReleaseGet]:
    return [
        LatestReleaseGet(
            notes=str(release.notes),
            platform=str(release.platform),  # ty: ignore[invalid-argument-type]
            published_at=release.published_at,
            version=str(release.version),
        )
        for release in current_releases()
    ]
