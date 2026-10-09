import logging

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final
from uuid import uuid7

from django.db.models import F, Q
from django.db.transaction import atomic, on_commit
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_auth.services.roles import holders_of_sync
from api_core.config import CONFIG
from api_core.services.pages import paginate
from api_core.services.storage import get_storage
from api_core.services.uploads import MEGABYTE
from api_exceptions.enums import RequestScopes
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_landing.models import AppRelease, DemoRequest
from api_landing.schemas import (
    AppReleaseGet,
    DemoRequestGet,
    LatestReleaseGet,
)
from api_notifications.services import notify
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_core.services.storage import PresignedUpload, StoredObject
    from api_landing.schemas import (
        AppReleasePatch,
        AppReleasePost,
        AppReleaseQuery,
        DemoRequestPatch,
        DemoRequestPost,
        DemoRequestQuery,
        InstallerUploadPost,
    )
    from api_territory.services.access import Actor

########################################################################################

logger = logging.getLogger(__name__)

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
    "agendada": "scheduled",
    "contactada": "contacted",
    "descartada": "dismissed",
    "nueva": "new",
    "realizada": "done",
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

# - la clase de aviso que reciben quienes atienden las solicitudes de demo
DEMO_NOTICE_KIND: Final[str] = "solicitud_demo"


@dataclass(frozen=True, slots=True)
class Installer:
    label: str
    content_type: str
    extension: str


# - qué instalador lleva cada plataforma. El tipo va dentro de la firma de la subida:
#   el portal lo fija según la plataforma, no según lo que diga el navegador
INSTALLERS: Final[dict[str, Installer]] = {
    "android": Installer(
        content_type="application/vnd.android.package-archive",
        extension=".apk",
        label="Android",
    ),
    "macos": Installer(
        content_type="application/x-apple-diskimage",
        extension=".dmg",
        label="macOS",
    ),
    "windows": Installer(
        content_type="application/vnd.microsoft.portable-executable",
        extension=".exe",
        label="Windows",
    ),
}

INSTALLER_PREFIX: Final[str] = "app-installer"
INSTALLER_MAX_BYTES: Final[int] = 500 * MEGABYTE
# un instalador pesa cientos de MB: la URL firmada dura más que la de una foto
INSTALLER_UPLOAD_EXPIRES: Final[timedelta] = timedelta(hours=1)

NO_RELEASE_DETAIL: Final[str] = (
    "Todavía no hay una versión de K'Plan para esa plataforma."
)

########################################################################################
# Solicitudes de demo: las manda cualquiera desde la landing


def submit_demo_request_sync(data: DemoRequestPost) -> None:
    # el campo trampa llegó lleno: lo mandó un bot. Se responde igual que a una persona
    # para que no aprenda a esquivarlo
    if data.website:
        return

    fields: dict[str, str] = {
        "city": data.city,
        "email": data.email,
        "kind": DEMO_KIND_BY_API[data.kind],
        "message": data.message,
        "name": data.name,
        "organization": data.organization,
        "phone": data.phone,
    }

    with atomic():
        pending: Any = (
            DemoRequest.objects
            .select_for_update()
            .filter(email=data.email, status="nueva")
            .order_by("-created_at")
            .first()
        )

        # la misma persona la vuelve a mandar antes de que el equipo la atienda: se
        # corrige la que ya está en la bandeja, sin otro aviso
        if pending is not None:
            DemoRequest.objects.filter(pk=pending.pk).update(**fields)
            return

        request: DemoRequest = DemoRequest.objects.create(**fields)

        for user_id in holders_of_sync(P.DEMOS_MANAGE):
            notify(
                user_id,
                DEMO_NOTICE_KIND,
                "Nueva solicitud de demo",
                f"{data.name} ({data.organization}) pidió una demostración.",
                {"demo_request_id": str(request.pk)},
            )


########################################################################################
# La bandeja del equipo (`demos.view`; atender, `demos.manage`)


def demo_payload(request: DemoRequest) -> DemoRequestGet:
    found: Any = request

    return DemoRequestGet(
        city=str(found.city),
        created_at=found.created_at,
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

    changes: dict[str, object] = {}

    if data.status is not None:
        changes["status"] = DEMO_STATUS_BY_API[data.status]

    if data.notes is not None:
        changes["notes"] = data.notes

    with atomic():
        request: Any = find_demo_request(request_id)

        if changes:
            DemoRequest.objects.filter(pk=request.pk).update(
                **changes, updated_at=now(), updated_by=actor.user
            )

    return demo_payload(find_demo_request(request_id))


########################################################################################
# Versiones de la app: el equipo con `releases.manage` sube y publica


def ensure_publisher(actor: Actor) -> None:
    if not actor.can(P.RELEASES_MANAGE):
        raise ForbiddenError


def file_name(release: AppRelease) -> str:
    found: Any = release

    return f"kplan-{found.version}{INSTALLERS[str(found.platform)].extension}"


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
        downloads=int(found.downloads),
        file_name=file_name(release),
        id=found.pk,
        notes=str(found.notes),
        platform=str(found.platform),  # ty: ignore[invalid-argument-type]
        published_at=found.published_at,
        size=int(found.file_size),
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
            f"Ya existe la versión {version} para {INSTALLERS[platform].label}."
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


def issue_installer_upload_sync(
    actor: Actor, data: InstallerUploadPost
) -> PresignedUpload:
    ensure_publisher(actor)

    if data.size > INSTALLER_MAX_BYTES:
        raise invalid(
            "size",
            f"El instalador pesa más de {INSTALLER_MAX_BYTES // MEGABYTE} MB.",
        )

    installer: Installer = INSTALLERS[data.platform]

    return get_storage().presign_upload(
        content_type=installer.content_type,
        expires_in=int(INSTALLER_UPLOAD_EXPIRES.total_seconds()),
        key=f"{INSTALLER_PREFIX}/{data.platform}/{uuid7()}{installer.extension}",
        max_bytes=INSTALLER_MAX_BYTES,
        size=data.size,
    )


# Comprueba que la clave sea un instalador de esa plataforma ya subido: sin esto, una
# versión podría apuntar a cualquier objeto del almacenamiento.
def verify_installer(platform: str, key: str) -> StoredObject:
    if not key.startswith(f"{INSTALLER_PREFIX}/{platform}/"):
        raise invalid("file", "Ese archivo no es un instalador de esa plataforma.")

    stored: StoredObject | None = get_storage().stat(key)

    if stored is None:
        raise invalid("file", "No encontramos el instalador. Súbelo de nuevo.")

    if (
        stored.content_type != INSTALLERS[platform].content_type
        or stored.size > INSTALLER_MAX_BYTES
        or stored.size <= 0
    ):
        raise invalid("file", "El archivo no es del tipo o del tamaño permitidos.")

    return stored


def create_release_sync(actor: Actor, data: AppReleasePost) -> AppReleaseGet:
    ensure_publisher(actor)

    stored: StoredObject = verify_installer(data.platform, data.file)

    if AppRelease.objects.filter(file_key=data.file).exists():
        raise invalid("file", "Ese instalador ya es de otra versión.")

    ensure_version_free(data.platform, data.version)

    release: AppRelease = AppRelease.objects.create(
        created_by=actor.user,
        file_key=data.file,
        file_size=stored.size,
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

        if changes:
            AppRelease.objects.filter(pk=release.pk).update(**changes)

    return reload_release(release_id)


def publish_release_sync(actor: Actor, release_id: UUID) -> AppReleaseGet:
    ensure_publisher(actor)

    with atomic():
        release: Any = find_release(release_id, lock=True)

        if release.status == "publicada":
            raise ConflictError(detail="Esa versión ya está publicada.")

        # quien la descargue tiene que encontrar el archivo
        if get_storage().stat(str(release.file_key)) is None:
            raise ConflictError(
                detail="El instalador ya no está en el almacenamiento. Súbelo de nuevo."
            )

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


def forget_installer(key: str) -> None:
    try:
        get_storage().delete(key)
    except Exception:
        # el objeto que no se borró queda huérfano en el bucket; no rompe el borrado
        logger.exception("No se borró el instalador %s", key)


def delete_release_sync(actor: Actor, release_id: UUID) -> None:
    ensure_publisher(actor)

    with atomic():
        release: Any = find_release(release_id, lock=True)

        if release.status != "borrador":
            raise ConflictError(
                detail="Solo se borra un borrador; una versión publicada se retira."
            )

        key: str = str(release.file_key)
        AppRelease.objects.filter(pk=release.pk).delete()
        on_commit(lambda: forget_installer(key))


def release_download_sync(actor: Actor, release_id: UUID) -> str:
    if not actor.can(P.RELEASES_VIEW, P.RELEASES_MANAGE):
        raise ForbiddenError

    release: AppRelease = find_release(release_id)

    return get_storage().presign_download(
        str(release.file_key),
        expires_in=int(CONFIG.STORAGE_DOWNLOAD_EXPIRES.total_seconds()),
        filename=file_name(release),
    )


########################################################################################
# Lo que ve la landing: público


def latest_releases_sync() -> list[LatestReleaseGet]:
    return [
        LatestReleaseGet(
            file_name=file_name(release),
            notes=str(release.notes),
            platform=str(release.platform),  # ty: ignore[invalid-argument-type]
            published_at=release.published_at,
            size=int(release.file_size),
            version=str(release.version),
        )
        for release in current_releases()
    ]


# Una URL firmada recién hecha para el instalador vigente: el enlace de la landing no
# vence y el bucket sigue privado.
def download_current_sync(platform: str) -> str:
    release: Any = current_releases().filter(platform=platform).first()

    if release is None:
        raise NotFoundError(detail=NO_RELEASE_DETAIL)

    url: str = get_storage().presign_download(
        str(release.file_key),
        expires_in=int(CONFIG.STORAGE_DOWNLOAD_EXPIRES.total_seconds()),
        filename=file_name(release),
    )

    AppRelease.objects.filter(pk=release.pk).update(downloads=F("downloads") + 1)

    return url
