from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import StringConstraints

from api_auth.schemas.types import Email
from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery

########################################################################################

type DemoKind = Literal[
    "business", "municipality", "institution", "tour_operator", "other"
]
type DemoStatus = Literal["pending", "delivered"]
type Platform = Literal["android", "macos", "windows"]
type ReleaseStatus = Literal["draft", "published", "withdrawn"]

type Line = Annotated[str, StringConstraints(max_length=120, min_length=2)]
type Note = Annotated[str, StringConstraints(max_length=2000)]
type ReleaseNotes = Annotated[str, StringConstraints(max_length=4000)]

# - `1.2.0`, `1.2.0-beta.1` o `1.2.0+14`
type Version = Annotated[
    str,
    StringConstraints(
        max_length=32,
        pattern=r"^\d+(\.\d+){1,3}([-+][0-9A-Za-z.\-]+)?$",
    ),
]

# - donde está el instalador (un link compartido de Drive); siempre https
type Link = Annotated[
    str,
    StringConstraints(max_length=500, pattern=r"^https://\S+$", strip_whitespace=True),
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


class DeliveredLink(DTO):
    platform: Platform
    version: str
    link: str


class DemoRequestResult(DTO):
    # si la landing pudo darle los links en ese momento; si no, se le avisa después
    delivered: bool
    links: list[DeliveredLink]


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
    delivered_at: datetime | None
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


class AppReleasePost(DTO):
    platform: Platform
    version: Version
    notes: ReleaseNotes = ""
    link: Link


class AppReleasePatch(DTO):
    # la versión solo cambia mientras es un borrador; el link, siempre
    version: Version | None = None
    notes: ReleaseNotes | None = None
    link: Link | None = None


class AppReleaseGet(DTO):
    id: UUID
    platform: Platform
    version: str
    notes: str
    link: str
    status: ReleaseStatus
    # la que hoy se entrega a quien pide una demo para su plataforma
    current: bool
    deliveries: int
    created_at: datetime
    created_by: str
    published_at: datetime | None
    withdrawn_at: datetime | None


class AppReleaseQuery(PageQuery):
    platform: Platform | None = None
    status: ReleaseStatus | None = None


# Lo público: qué hay disponible, sin el link (ese se da al pedir la demo).
class LatestReleaseGet(DTO):
    platform: Platform
    version: str
    notes: str
    published_at: datetime
