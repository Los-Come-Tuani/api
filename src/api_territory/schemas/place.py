from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery

from .common import (
    CityRef,
    ClockTime,
    ImageGet,
    ImageKey,
    Latitude,
    Longitude,
    OrganizationKind,
    OwnerRef,
    PillarRef,
    Reference,
)

########################################################################################

type PlaceName = Annotated[str, StringConstraints(max_length=80, min_length=3)]
type PillarCode = Annotated[str, StringConstraints(max_length=40, min_length=1)]
type Address = Annotated[str, StringConstraints(max_length=140)]
type Description = Annotated[str, StringConstraints(max_length=2000)]
type Tip = Annotated[str, StringConstraints(max_length=140)]
type VisitMinutes = Annotated[int, Field(ge=5, le=720)]
type Images = Annotated[list[ImageKey], Field(max_length=8)]

########################################################################################
# Lo que ve la app


class StopGet(DTO):
    id: UUID
    name: str
    pillar: PillarRef
    city: CityRef
    address: str
    description: str
    tip: str
    latitude: float
    longitude: float
    # sin horario es un lugar que no cierra
    opens_at: str | None
    closes_at: str | None
    visit_minutes: int
    has_badge: bool
    rating: float
    reviews_count: int
    # la primera es la portada
    images: list[ImageGet]
    owner: OwnerRef | None


class OfferingGet(DTO):
    id: UUID
    name: str
    description: str
    # córdobas; nulo es "a consultar"
    price: int | None


class ContactGet(DTO):
    phone: str
    whatsapp: str
    email: str
    website: str
    instagram: str
    facebook: str


class PlaceProfileGet(DTO):
    offerings: list[OfferingGet]
    amenities: list[str]
    languages: list[str]
    contact: ContactGet
    updated_at: datetime | None


class PostGet(DTO):
    id: UUID
    place_id: UUID
    title: str
    body: str
    image: ImageGet | None
    visible: bool
    published_at: datetime


class StopDetailGet(StopGet):
    profile: PlaceProfileGet
    # las novedades visibles, de la más reciente a la más vieja
    posts: list[PostGet]


class StopQuery(PageQuery):
    # el código de la ciudad (`leon`, `granada`...)
    city: Annotated[str, StringConstraints(max_length=40)] | None = None
    pillar: PillarCode | None = None
    search: Annotated[str, StringConstraints(max_length=100)] | None = None
    # varios lugares a la vez, separados por comas
    ids: Annotated[str, StringConstraints(max_length=4000)] | None = None


########################################################################################
# Lo que administra el portal


class PlaceGet(StopGet):
    active: bool
    created_at: datetime
    # en cuántos circuitos publicados está
    published_circuits: NonNegativeInt


class PlaceQuery(PageQuery):
    city_id: Reference | None = None
    pillar: PillarCode | None = None
    owner_kind: OrganizationKind | Literal["none"] | None = None
    owner_id: Reference | None = None
    active: bool | None = None
    search: Annotated[str, StringConstraints(max_length=100)] | None = None


class PlacePost(DTO):
    # quien opera una alcaldía crea en su ciudad; el equipo, en cualquiera
    city_id: Reference | None = None
    pillar: PillarCode
    name: PlaceName
    description: Description = ""
    address: Address = ""
    latitude: Latitude
    longitude: Longitude
    opens_at: ClockTime | None = None
    closes_at: ClockTime | None = None
    visit_minutes: VisitMinutes = 30
    tip: Tip = ""
    # solo el equipo con `places.manage`
    has_badge: bool = False
    images: Images = Field(default_factory=list)


# Solo se aplican los campos que llegan.
class PlacePatch(DTO):
    pillar: PillarCode = ""
    name: PlaceName = ""
    description: Description = ""
    address: Address = ""
    latitude: Latitude = 0
    longitude: Longitude = 0
    opens_at: ClockTime | None = None
    closes_at: ClockTime | None = None
    visit_minutes: VisitMinutes = 30
    tip: Tip = ""
    has_badge: bool = False
    active: bool = True
    images: Images = Field(default_factory=list)


class PlaceOwnerPut(DTO):
    # nulos los dos: el lugar vuelve a ser del equipo
    kind: OrganizationKind | None = None
    id: Reference | None = None


########################################################################################
# Ficha y novedades

type Phone = Annotated[
    str, StringConstraints(max_length=20, pattern=r"^(\+?[\d\s-]{8,16})?$")
]


class OfferingPost(DTO):
    name: Annotated[str, StringConstraints(max_length=80, min_length=1)]
    description: Annotated[str, StringConstraints(max_length=300)] = ""
    price: Annotated[int, Field(ge=0, le=1_000_000)] | None = None


class ContactPut(DTO):
    phone: Phone = ""
    whatsapp: Phone = ""
    email: Annotated[str, StringConstraints(max_length=254)] = ""
    website: Annotated[str, StringConstraints(max_length=200)] = ""
    instagram: Annotated[str, StringConstraints(max_length=40)] = ""
    facebook: Annotated[str, StringConstraints(max_length=80)] = ""


class PlaceProfilePut(DTO):
    offerings: Annotated[list[OfferingPost], Field(max_length=24)] = Field(
        default_factory=list
    )
    amenities: Annotated[
        list[Annotated[str, StringConstraints(max_length=40, min_length=1)]],
        Field(max_length=20),
    ] = Field(default_factory=list)
    languages: Annotated[
        list[Annotated[str, StringConstraints(max_length=40, min_length=1)]],
        Field(max_length=12),
    ] = Field(default_factory=list)
    contact: ContactPut = Field(default_factory=ContactPut)


type PostTitle = Annotated[str, StringConstraints(max_length=80, min_length=4)]
type PostBody = Annotated[str, StringConstraints(max_length=500, min_length=20)]


class PostQuery(PageQuery):
    place_id: Reference | None = None


class PostPost(DTO):
    place_id: Reference
    title: PostTitle
    body: PostBody
    image_key: ImageKey | None = None
    visible: bool = True


# Solo se aplican los campos que llegan.
class PostPatch(DTO):
    title: PostTitle = ""
    body: PostBody = ""
    image_key: ImageKey | None = None
    visible: bool = True
