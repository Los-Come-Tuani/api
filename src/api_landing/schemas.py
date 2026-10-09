from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import PositiveInt, StringConstraints

from api_auth.schemas.types import Email
from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery

########################################################################################

type DemoKind = Literal[
    "business", "municipality", "institution", "tour_operator", "other"
]
type DemoStatus = Literal["new", "contacted", "scheduled", "done", "dismissed"]
type Platform = Literal["android", "macos", "windows"]
type ReleaseStatus = Literal["draft", "published", "withdrawn"]

type Line = Annotated[str, StringConstraints(max_length=120, min_length=2)]
type Note = Annotated[str, StringConstraints(max_length=2000)]
type ReleaseNotes = Annotated[str, StringConstraints(max_length=4000)]

# - `1.2.0`, `1.2.0-beta.1` o `1.2.0+14`: se muestra y va en el nombre del archivo
type Version = Annotated[
    str,
    StringConstraints(
        max_length=32,
        pattern=r"^\d+(\.\d+){1,3}([-+][0-9A-Za-z.\-]+)?$",
    ),
]

########################################################################################
# Solicitudes de demo


class DemoRequestPost(DTO):
    name: Line
    email: Email
    phone: Annotated[str, StringConstraints(max_length=30)] = ""
    organization: Annotated[str, StringConstraints(max_length=160, min_length=2)]
    kind: DemoKind
    city: Annotated[str, StringConstraints(max_length=120)] = ""
    message: Annotated[str, StringConstraints(max_length=2000)] = ""
    # campo trampa: la landing lo esconde y una persona lo deja vacío; si llega con
    # algo lo llenó un bot
    website: Annotated[str, StringConstraints(max_length=200)] = ""


class DemoRequestGet(DTO):
    id: UUID
    name: str
    email: str
    phone: str
    organization: str
    kind: DemoKind
    city: str
    message: str
    status: DemoStatus
    notes: str
    created_at: datetime
    updated_at: datetime | None
    # quién la movió por última vez
    updated_by: str | None


class DemoRequestQuery(PageQuery):
    status: DemoStatus | None = None
    # nombre, correo u organización, sin importar tildes
    search: Annotated[str, StringConstraints(max_length=100)] | None = None


class DemoRequestPatch(DTO):
    status: DemoStatus | None = None
    notes: Note | None = None


########################################################################################
# Versiones de la app


class InstallerUploadPost(DTO):
    platform: Platform
    # en bytes: la firma lo lleva dentro y el almacenamiento lo hace cumplir
    size: PositiveInt


class AppReleasePost(DTO):
    platform: Platform
    version: Version
    notes: ReleaseNotes = ""
    # la clave que devolvió `app-release/upload/`
    file: Annotated[str, StringConstraints(max_length=200, min_length=1)]


class AppReleasePatch(DTO):
    # la versión solo cambia mientras es un borrador
    version: Version | None = None
    notes: ReleaseNotes | None = None


class AppReleaseGet(DTO):
    id: UUID
    platform: Platform
    version: str
    notes: str
    status: ReleaseStatus
    # la que hoy se descarga desde la landing para su plataforma
    current: bool
    file_name: str
    size: int
    downloads: int
    created_at: datetime
    created_by: str
    published_at: datetime | None
    withdrawn_at: datetime | None


class AppReleaseQuery(PageQuery):
    platform: Platform | None = None
    status: ReleaseStatus | None = None


class ReleaseDownloadGet(DTO):
    # firmada por unos minutos: se abre en cuanto llega
    url: str


class LatestReleaseGet(DTO):
    platform: Platform
    version: str
    notes: str
    file_name: str
    size: int
    published_at: datetime


class PlatformPath(DTO):
    platform: Platform
