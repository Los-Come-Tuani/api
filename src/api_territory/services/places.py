from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final
from uuid import UUID

from django.db.models import Count, Q
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_catalogs.models import CulturalPillar
from api_catalogs.seeder import CULTURAL_PILLARS, PILLAR_BY_BUSINESS_TYPE
from api_core.services.pages import paginate
from api_core.services.uploads import UploadKinds
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_organizations.models import Business, CulturalInstitution, Photo
from api_territory.models import (
    City,
    Municipality,
    PlaceOffering,
    PlaceProfile,
    PointOfInterest,
    Publication,
)
from api_territory.schemas.common import CityRef, OwnerRef, PillarRef
from api_territory.schemas.place import (
    ContactGet,
    OfferingGet,
    PlaceGet,
    PlaceProfileGet,
    PostGet,
    StopDetailGet,
    StopGet,
)

from .access import Actor, invalid, owned_by
from .images import (
    check_images,
    current_keys,
    image_payload,
    ordered_photos,
    photos_payload,
    replace_photos,
)

if TYPE_CHECKING:
    from datetime import time

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_territory.schemas.place import (
        PlaceOwnerPut,
        PlacePatch,
        PlacePost,
        PlaceProfilePut,
        PlaceQuery,
        PostPatch,
        PostPost,
        PostQuery,
        StopQuery,
    )

########################################################################################

NOT_FOUND_DETAIL: Final[str] = "No encontramos ese lugar."

RELATED: Final[tuple[str, ...]] = (
    "business",
    "city",
    "institution",
    "municipality",
    "pillar",
)

# - las organizaciones que pueden ser dueñas de un lugar, por clase
OWNER_MODELS: Final[dict[str, type[Business | CulturalInstitution | Municipality]]] = {
    "business": Business,
    "institution": CulturalInstitution,
    "municipality": Municipality,
}

# - cuántas novedades trae el detalle público de un lugar
PUBLIC_POSTS: Final[int] = 10

########################################################################################
# Piezas


def points() -> QuerySet:
    return PointOfInterest.objects.select_related(*RELATED).prefetch_related(
        ordered_photos()
    )


def city_ref(city: City) -> CityRef:
    found: Any = city

    return CityRef(code=str(found.code), id=found.pk, name=str(found.name))


def owner_of(point: PointOfInterest) -> OwnerRef | None:
    found: Any = point

    for kind in OWNER_MODELS:
        record: Any = getattr(found, kind)

        if record is not None:
            return OwnerRef(id=record.pk, kind=kind, name=str(record.name))  # ty: ignore[invalid-argument-type]

    return None


def clock(value: time | None) -> str | None:
    return None if value is None else value.strftime("%H:%M")


def stop_payload(point: PointOfInterest) -> StopGet:
    found: Any = point

    return StopGet(
        address=str(found.address),
        city=city_ref(found.city),
        closes_at=clock(found.closes_at),
        description=str(found.description),
        has_badge=bool(found.has_badge),
        id=found.pk,
        images=photos_payload(point),
        latitude=float(found.latitude),
        longitude=float(found.longitude),
        name=str(found.name),
        opens_at=clock(found.opens_at),
        owner=owner_of(point),
        pillar=PillarRef(code=str(found.pillar.code), label=str(found.pillar.label)),
        rating=float(found.rating),
        reviews_count=int(found.reviews_count),
        tip=str(found.tip),
        visit_minutes=int(found.visit_minutes),
    )


def place_payload(point: PointOfInterest) -> PlaceGet:
    found: Any = point

    published: int | None = getattr(found, "published_circuits", None)

    if published is None:
        published = found.circuit_stops.filter(
            circuit__status__code="publicado"
        ).count()

    return PlaceGet(
        **dict(stop_payload(point)),
        active=bool(found.active),
        created_at=found.created_at,
        published_circuits=published,
    )


def profile_payload(point: PointOfInterest) -> PlaceProfileGet:
    profile: Any = PlaceProfile.objects.filter(point=point).first()

    offerings = [
        OfferingGet(
            description=str(item.description),
            id=item.pk,
            name=str(item.name),
            price=item.price,
        )
        for item in PlaceOffering.objects.filter(point=point).order_by("order", "id")
    ]

    if profile is None:
        return PlaceProfileGet(
            amenities=[],
            contact=ContactGet(
                email="", facebook="", instagram="", phone="", website="", whatsapp=""
            ),
            languages=["Español"],
            offerings=offerings,
            updated_at=None,
        )

    return PlaceProfileGet(
        amenities=list(profile.amenities),
        contact=ContactGet(
            email=str(profile.email),
            facebook=str(profile.facebook),
            instagram=str(profile.instagram),
            phone=str(profile.phone),
            website=str(profile.website),
            whatsapp=str(profile.whatsapp),
        ),
        languages=list(profile.languages),
        offerings=offerings,
        updated_at=profile.updated_at,
    )


def post_payload(publication: Publication) -> PostGet:
    found: Any = publication

    return PostGet(
        body=str(found.body),
        id=found.pk,
        image=image_payload(str(found.image_key)) if found.image_key else None,
        place_id=found.point_id,
        published_at=found.published_at,
        title=str(found.title),
        visible=bool(found.visible),
    )


def find_pillar(code: str) -> CulturalPillar:
    pillar: CulturalPillar | None = CulturalPillar.objects.filter(
        active=True, code=code
    ).first()

    if pillar is None:
        raise invalid("pillar", "Ese pilar no existe.")

    return pillar


def check_hours(opens: time | None, closes: time | None) -> None:
    if (opens is None) != (closes is None):
        raise invalid("closes_at", "Van las dos horas o ninguna.")

    if opens is not None and closes is not None and closes <= opens:
        raise invalid(
            "closes_at", "La hora de cierre tiene que ser después de la de apertura."
        )


def coordinate(value: float) -> Decimal:
    return Decimal(str(round(value, 6)))


########################################################################################
# Lo que ve la app (sin sesión)


def public_stops_sync(query: StopQuery) -> Paginated[StopGet]:
    found = points().filter(active=True)

    if query.city:
        found = found.filter(city__code=query.city)

    if query.pillar:
        found = found.filter(pillar__code=query.pillar)

    if query.search:
        found = found.filter(name__im_unaccent__icontains=query.search.strip())

    if query.ids:
        found = found.filter(pk__in=parse_ids(query.ids))

    return paginate(found.order_by("name", "id"), query, stop_payload, StopGet)


def parse_ids(raw: str) -> list[str]:
    ids: list[str] = []

    for part in raw.split(","):
        try:
            ids.append(str(UUID(part.strip())))
        except ValueError:
            continue

    return ids


def public_stop_sync(point_id: UUID) -> StopDetailGet:
    point: PointOfInterest | None = points().filter(active=True, pk=point_id).first()

    if point is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    posts = Publication.objects.filter(point=point, visible=True).order_by(
        "-published_at"
    )[:PUBLIC_POSTS]

    return StopDetailGet(
        **dict(stop_payload(point)),
        posts=[post_payload(item) for item in posts],
        profile=profile_payload(point),
    )


########################################################################################
# Lo que administra el portal


# El equipo con `places.view` ve todos; quien opera una organización, solo los suyos.
def visible_places(actor: Actor) -> QuerySet:
    found = points().annotate(
        published_circuits=Count(
            "circuit_stops",
            filter=Q(circuit_stops__circuit__status__code="publicado"),
        )
    )

    if actor.can(P.PLACES_VIEW):
        return found

    if actor.organization is not None:
        return found.filter(owned_by(actor.organization))

    raise ForbiddenError


def visible_place(actor: Actor, point_id: UUID) -> PointOfInterest:
    point: PointOfInterest | None = visible_places(actor).filter(pk=point_id).first()

    if point is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return point


# Edita la ficha de un lugar el equipo con `places.manage` o su dueño.
def editable_place(actor: Actor, point_id: UUID) -> PointOfInterest:
    point: PointOfInterest = visible_place(actor, point_id)

    if actor.can(P.PLACES_MANAGE):
        return point

    if actor.organization is not None and owner_of(point) is not None:
        owner: Any = owner_of(point)

        if owner.kind == actor.organization.kind and owner.id == actor.organization.id:
            return point

    raise ForbiddenError


def places_sync(actor: Actor, query: PlaceQuery) -> Paginated[PlaceGet]:
    found = visible_places(actor)

    if query.city_id is not None:
        found = found.filter(city_id=query.city_id)

    if query.pillar:
        found = found.filter(pillar__code=query.pillar)

    if query.owner_kind == "none":
        found = found.filter(
            business__isnull=True,
            institution__isnull=True,
            municipality__isnull=True,
        )
    elif query.owner_kind is not None:
        found = found.filter(**{f"{query.owner_kind}__isnull": False})

        if query.owner_id is not None:
            found = found.filter(**{f"{query.owner_kind}_id": query.owner_id})

    if query.active is not None:
        found = found.filter(active=query.active)

    if query.search:
        found = found.filter(name__im_unaccent__icontains=query.search.strip())

    return paginate(found.order_by("name", "id"), query, place_payload, PlaceGet)


def place_sync(actor: Actor, point_id: UUID) -> PlaceGet:
    return place_payload(visible_place(actor, point_id))


def creation_city(
    actor: Actor, city_id: UUID | None
) -> tuple[City, Municipality | None]:
    # el equipo crea en cualquier ciudad y el lugar queda sin dueño; la alcaldía, en la
    # suya y como dueña
    if actor.can(P.PLACES_MANAGE):
        if city_id is None:
            raise invalid("city_id", "Elige la ciudad del lugar.")

        city: City | None = City.objects.filter(pk=city_id).first()

        if city is None:
            raise invalid("city_id", "Esa ciudad no existe.")

        return city, None

    if actor.organization is not None and actor.operates("municipality"):
        municipality: Any = Municipality.objects.select_related("city").get(
            pk=actor.organization.id
        )

        if city_id is not None and city_id != municipality.city_id:
            raise invalid("city_id", "Solo puedes crear lugares en tu ciudad.")

        return municipality.city, municipality

    raise ForbiddenError


def create_place_sync(actor: Actor, data: PlacePost) -> PlaceGet:
    city, municipality = creation_city(actor, data.city_id)
    pillar: CulturalPillar = find_pillar(data.pillar)

    check_hours(data.opens_at, data.closes_at)

    if data.has_badge and not actor.can(P.PLACES_MANAGE):
        raise invalid("has_badge", "La insignia de un lugar la activa el equipo.")

    images = check_images(
        data.images,
        current=[],
        field="images",
        kind=UploadKinds.PLACE_PHOTO,
    )

    with atomic():
        point: PointOfInterest = PointOfInterest.objects.create(
            address=data.address,
            city=city,
            closes_at=data.closes_at,
            description=data.description,
            has_badge=data.has_badge,
            latitude=coordinate(data.latitude),
            longitude=coordinate(data.longitude),
            municipality=municipality,
            name=data.name,
            opens_at=data.opens_at,
            pillar=pillar,
            tip=data.tip,
            visit_minutes=data.visit_minutes,
        )

        replace_photos("point", point, images)

    return place_sync(actor, point.pk)


def ensure_not_in_published_circuits(point: PointOfInterest) -> None:
    found: Any = point

    if found.circuit_stops.filter(circuit__status__code="publicado").exists():
        raise ConflictError(
            detail=(
                "Ese lugar está en circuitos publicados: quítalo de ellos antes de "
                "retirarlo."
            )
        )


def check_restricted_changes(
    actor: Actor,
    place: PointOfInterest,
    changes: dict[str, Any],
) -> None:
    point: Any = place
    badge_changes: bool = (
        "has_badge" in changes and changes["has_badge"] != point.has_badge
    )

    if badge_changes and not actor.can(P.PLACES_MANAGE):
        raise invalid("has_badge", "La insignia de un lugar la activa el equipo.")

    if "active" in changes and changes["active"] != point.active:
        # retirar o devolver un lugar: el equipo o la alcaldía dueña; un comercio no
        # retira su propio lugar
        if not (actor.can(P.PLACES_MANAGE) or point.municipality_id is not None):
            raise ForbiddenError

        if not changes["active"]:
            ensure_not_in_published_circuits(point)


def update_place_sync(actor: Actor, point_id: UUID, patch: PlacePatch) -> PlaceGet:
    point: Any = editable_place(actor, point_id)
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)

    check_restricted_changes(actor, point, changes)

    if "pillar" in changes:
        changes["pillar"] = find_pillar(changes["pillar"])

    for field in ("latitude", "longitude"):
        if field in changes:
            changes[field] = coordinate(changes[field])

    check_hours(
        changes.get("opens_at", point.opens_at),
        changes.get("closes_at", point.closes_at),
    )

    images: list[str] | None = None

    if "images" in changes:
        images = check_images(
            changes.pop("images"),
            current=current_keys("point", point),
            field="images",
            kind=UploadKinds.PLACE_PHOTO,
        )

    with atomic():
        if changes:
            PointOfInterest.objects.filter(pk=point.pk).update(**changes)

        if images is not None:
            replace_photos("point", point, images)

    return place_sync(actor, point.pk)


def retire_place_sync(actor: Actor, point_id: UUID) -> None:
    point: Any = editable_place(actor, point_id)

    if not (actor.can(P.PLACES_MANAGE) or point.municipality_id is not None):
        raise ForbiddenError

    ensure_not_in_published_circuits(point)

    PointOfInterest.objects.filter(pk=point.pk).update(active=False)


def set_owner_sync(actor: Actor, point_id: UUID, data: PlaceOwnerPut) -> PlaceGet:
    if not actor.can(P.PLACES_MANAGE, P.ORGANIZATIONS_MANAGE):
        raise ForbiddenError

    # quien asigna lugares a las organizaciones los ve todos, aunque no edite fichas
    point: Any = points().filter(pk=point_id).first()

    if point is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)
    owner: dict[str, Any] = {
        "business": None,
        "institution": None,
        "municipality": None,
    }

    if (data.kind is None) != (data.id is None):
        raise invalid("id", "Di la clase de organización y cuál, o ninguna de las dos.")

    if data.kind is not None:
        record: Any = OWNER_MODELS[data.kind].objects.filter(pk=data.id).first()

        if record is None or record.verified_at is None:
            raise invalid("id", "No encontramos esa organización verificada.")

        if record.city_id != point.city_id:
            raise invalid("id", "La organización es de otra ciudad.")

        if (
            data.kind == "business"
            and PointOfInterest.objects
            .filter(business=record)
            .exclude(pk=point.pk)
            .exists()
        ):
            raise ConflictError(detail="Ese comercio ya tiene su lugar.")

        owner[data.kind] = record

    PointOfInterest.objects.filter(pk=point.pk).update(**owner)

    return place_payload(points().get(pk=point.pk))


########################################################################################
# Ficha


def place_profile_sync(actor: Actor, point_id: UUID) -> PlaceProfileGet:
    return profile_payload(visible_place(actor, point_id))


def put_place_profile_sync(
    actor: Actor,
    point_id: UUID,
    data: PlaceProfilePut,
) -> PlaceProfileGet:
    point: PointOfInterest = editable_place(actor, point_id)

    with atomic():
        PlaceProfile.objects.update_or_create(
            point=point,
            defaults={
                "amenities": list(dict.fromkeys(data.amenities)),
                "email": data.contact.email,
                "facebook": data.contact.facebook,
                "instagram": data.contact.instagram,
                "languages": list(dict.fromkeys(data.languages)),
                "phone": data.contact.phone,
                "updated_at": now(),
                "website": data.contact.website,
                "whatsapp": data.contact.whatsapp,
            },
        )

        PlaceOffering.objects.filter(point=point).delete()
        PlaceOffering.objects.bulk_create(
            PlaceOffering(
                description=item.description,
                name=item.name,
                order=order,
                point=point,
                price=item.price,
            )
            for order, item in enumerate(data.offerings)
        )

    return profile_payload(point)


########################################################################################
# Novedades


def visible_posts(actor: Actor) -> QuerySet:
    places = visible_places(actor).values("pk")

    return Publication.objects.filter(point__in=places)


def posts_sync(actor: Actor, query: PostQuery) -> Paginated[PostGet]:
    found = visible_posts(actor)

    if query.place_id is not None:
        found = found.filter(point_id=query.place_id)

    return paginate(
        found.order_by("-published_at", "id"),
        query,
        post_payload,
        PostGet,
    )


def editable_post(actor: Actor, post_id: UUID) -> Publication:
    publication: Any = visible_posts(actor).filter(pk=post_id).first()

    if publication is None:
        raise NotFoundError(detail="No encontramos esa novedad.")

    # quien modera el contenido también oculta o borra lo que publicó otro
    if not actor.can(P.CONTENT_MODERATE):
        editable_place(actor, publication.point_id)

    return publication


def check_post_image(key: str | None, current: str) -> str:
    if key is None:
        return ""

    check_images(
        [key],
        current=[current] if current else [],
        field="image_key",
        kind=UploadKinds.PLACE_PHOTO,
    )

    return key


def create_post_sync(actor: Actor, data: PostPost) -> PostGet:
    point: PointOfInterest = editable_place(actor, data.place_id)
    image_key: str = check_post_image(data.image_key, "")

    publication: Publication = Publication.objects.create(
        author=actor.user,
        body=data.body,
        image_key=image_key,
        point=point,
        title=data.title,
        visible=data.visible,
    )

    return post_payload(publication)


def update_post_sync(actor: Actor, post_id: UUID, patch: PostPatch) -> PostGet:
    publication: Any = editable_post(actor, post_id)
    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)

    if "image_key" in changes:
        changes["image_key"] = check_post_image(
            changes["image_key"], str(publication.image_key)
        )

    if changes:
        Publication.objects.filter(pk=publication.pk).update(**changes)

    return post_payload(Publication.objects.get(pk=publication.pk))


def delete_post_sync(actor: Actor, post_id: UUID) -> None:
    publication: Publication = editable_post(actor, post_id)

    Publication.objects.filter(pk=publication.pk).delete()


########################################################################################
# El lugar de un comercio


def pillar_for_business(business: Business) -> CulturalPillar:
    found: Any = business
    code: str = PILLAR_BY_BUSINESS_TYPE.get(str(found.business_type.code), "cultura")
    label: str = dict(CULTURAL_PILLARS)[code]

    # en una base recién migrada la siembra corre después: el pilar se crea si falta
    pillar, _ = CulturalPillar.objects.get_or_create(
        code=code, defaults={"label": label}
    )

    return pillar


# Aprobar un comercio le da su lugar en el mapa, con lo que mandó al postularse: nombre,
# dirección, ubicación y la foto de su platillo. Después lo completa desde el portal.
def ensure_business_place_sync(business: Business) -> PointOfInterest:
    found: Any = business
    existing: PointOfInterest | None = PointOfInterest.objects.filter(
        business=business
    ).first()

    if existing is not None:
        return existing

    with atomic():
        point: PointOfInterest = PointOfInterest.objects.create(
            address=str(found.address)[:140],
            business=business,
            city_id=found.city_id,
            latitude=found.latitude,
            longitude=found.longitude,
            name=str(found.name)[:80],
            pillar=pillar_for_business(business),
        )

        keys = list(
            Photo.objects
            .filter(business=business)
            .order_by("order", "id")
            .values_list("file_key", flat=True)
        )
        replace_photos("point", point, [str(key) for key in keys])

    return point
