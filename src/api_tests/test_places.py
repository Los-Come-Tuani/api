from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group
from django.db import IntegrityError
from django.db.transaction import atomic

from api_auth.enums import ApiUserTypes
from api_auth.models import ApiUserGroups
from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_moderation.enums import VerificationStates
from api_moderation.models import VerificationRequest, VerificationStatus
from api_organizations.models import Photo
from api_territory.models import PointOfInterest, Publication
from api_territory.services.places import ensure_business_place_sync
from api_tests.helpers import body
from api_tests.territory_helpers import (
    PLACE_PHOTO,
    city,
    make_circuit,
    make_point,
    mobile_headers,
    operator,
    signed_in,
    verified_business,
    verified_municipality,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    storage.put(PLACE_PHOTO, content_type="image/jpeg")
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


@pytest.fixture
def business_owner(make_user: Callable[..., ApiUser]) -> ApiUser:
    business = verified_business()
    ensure_business_place_sync(business)

    return operator(make_user(email="negocio@example.com"), business, "Negocio")


@pytest.fixture
def mayor(make_user: Callable[..., ApiUser]) -> ApiUser:
    return operator(
        make_user(email="alcaldia@example.com"),
        verified_municipality(),
        "Alcaldía",
    )


def place_of(user: ApiUser) -> PointOfInterest:
    return PointOfInterest.objects.get(business__role_assignments__user=user)


def new_place(**override: object) -> dict:
    return {
        "latitude": 12.4350,
        "longitude": -86.8790,
        "name": "Museo de Leyendas",
        "pillar": "cultura",
        **override,
    }


########################################################################################
# Lo que ve la app


def test_the_app_sees_active_places_without_a_session(client: DMRClient) -> None:
    make_point(name="Catedral de León")
    make_point(name="Ruinas cerradas", active=False)
    make_point("granada", name="Catedral de Granada")

    leon = body(client.get("/stop/", {"city": "leon"}))

    assert {item["name"] for item in leon["results"]} == {"Catedral de León"}
    assert leon["results"][0]["pillar"] == {"code": "historia", "label": "Historia"}


def test_a_retired_place_does_not_exist_for_the_app(client: DMRClient) -> None:
    retired = make_point(active=False)

    assert client.get(f"/stop/{retired.pk}/").status_code == HTTPStatus.NOT_FOUND


def test_the_detail_brings_the_profile_and_only_the_visible_posts(
    client: DMRClient,
) -> None:
    point = make_point()
    Publication.objects.create(body="Abrimos más temprano.", point=point, title="Hola")
    Publication.objects.create(
        body="Esto no se ve.", point=point, title="Oculta", visible=False
    )

    detail = body(client.get(f"/stop/{point.pk}/"))

    assert [post["title"] for post in detail["posts"]] == ["Hola"]
    assert detail["profile"]["languages"] == ["Español"]


def test_the_app_finds_several_places_by_id(client: DMRClient) -> None:
    first = make_point(name="Uno")
    second = make_point(name="Dos")
    make_point(name="Tres")

    found = body(client.get("/stop/", {"ids": f"{first.pk},{second.pk}"}))

    assert {item["name"] for item in found["results"]} == {"Uno", "Dos"}


########################################################################################
# Quién ve qué en el portal


def test_the_portal_places_need_a_session(client: DMRClient) -> None:
    assert client.get("/place/").status_code == HTTPStatus.UNAUTHORIZED


def test_a_tourist_cannot_list_places(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    tourist = make_user(email="turista@example.com")
    ApiUserGroups.objects.create(
        api_user=tourist, group=Group.objects.get(name=ApiUserTypes.CLIENT.value)
    )

    response = client.get("/place/", headers=mobile_headers(tourist))

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_team_sees_every_place_and_an_owner_only_its_own(
    make_member: Callable[..., ApiUser],
    business_owner: ApiUser,
) -> None:
    make_point(name="Catedral de León")
    team = signed_in(make_member("equipo@example.com", "places.view"))
    owner = signed_in(business_owner)

    everything = body(team.get("/place/", {"page_size": 100}))
    own = body(owner.get("/place/"))

    assert {item["name"] for item in everything["results"]} >= {
        "Catedral de León",
        "El Sacuanjoche",
    }
    assert [item["name"] for item in own["results"]] == ["El Sacuanjoche"]


def test_a_place_of_someone_else_does_not_exist_for_an_owner(
    business_owner: ApiUser,
) -> None:
    other = make_point()
    client = signed_in(business_owner)

    assert client.get(f"/place/{other.pk}/").status_code == HTTPStatus.NOT_FOUND
    assert (
        client.patch(f"/place/{other.pk}/", {"name": "Mío"}).status_code
        == HTTPStatus.NOT_FOUND
    )


########################################################################################
# Crear


@pytest.mark.usefixtures("memory")
def test_the_team_creates_a_place_in_any_city(
    make_member: Callable[..., ApiUser],
) -> None:
    client = signed_in(make_member("equipo@example.com", "places.manage"))

    response = client.post(
        "/place/",
        new_place(
            city_id=str(city("granada").pk), has_badge=True, images=[PLACE_PHOTO]
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["city"]["code"] == "granada"
    assert body(response)["owner"] is None
    assert body(response)["has_badge"] is True
    assert body(response)["images"][0]["key"] == PLACE_PHOTO


def test_the_team_has_to_say_the_city(make_member: Callable[..., ApiUser]) -> None:
    client = signed_in(make_member("equipo@example.com", "places.manage"))

    response = client.post("/place/", new_place())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.city_id" in body(response)["field_errors"]


def test_a_municipality_creates_places_in_its_city_as_their_owner(
    mayor: ApiUser,
) -> None:
    client = signed_in(mayor)

    created = client.post("/place/", new_place())
    elsewhere = client.post("/place/", new_place(city_id=str(city("granada").pk)))

    assert created.status_code == HTTPStatus.CREATED, created.content
    assert body(created)["owner"]["kind"] == "municipality"
    assert body(created)["city"]["code"] == "leon"
    assert elsewhere.status_code == HTTPStatus.BAD_REQUEST


def test_a_business_does_not_create_other_places(business_owner: ApiUser) -> None:
    client = signed_in(business_owner)

    assert client.post("/place/", new_place()).status_code == HTTPStatus.FORBIDDEN


def test_only_the_team_turns_on_the_badge_of_a_place(mayor: ApiUser) -> None:
    client = signed_in(mayor)

    response = client.post("/place/", new_place(has_badge=True))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.has_badge" in body(response)["field_errors"]


@pytest.mark.parametrize(
    "hours",
    [{"opens_at": "08:00"}, {"closes_at": "08:00", "opens_at": "17:00"}],
)
def test_the_hours_go_both_and_in_order(
    make_member: Callable[..., ApiUser],
    hours: dict[str, str],
) -> None:
    client = signed_in(make_member("equipo@example.com", "places.manage"))

    response = client.post("/place/", new_place(city_id=str(city().pk), **hours))

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content


@pytest.mark.usefixtures("memory")
def test_a_photo_has_to_be_uploaded_first(make_member: Callable[..., ApiUser]) -> None:
    client = signed_in(make_member("equipo@example.com", "places.manage"))

    response = client.post(
        "/place/",
        new_place(city_id=str(city().pk), images=["place-photo/nunca-subida.jpg"]),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.images" in body(response)["field_errors"]


########################################################################################
# Editar y retirar


def test_a_business_edits_its_place_and_it_shows_at_once(
    client: DMRClient,
    business_owner: ApiUser,
) -> None:
    point = place_of(business_owner)
    owner = signed_in(business_owner)

    response = owner.patch(
        f"/place/{point.pk}/",
        {"description": "La mejor sopa de mondongo de León.", "tip": "Ve temprano"},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(client.get(f"/stop/{point.pk}/"))["tip"] == "Ve temprano"


def test_a_business_does_not_turn_on_its_badge(business_owner: ApiUser) -> None:
    point = place_of(business_owner)

    response = signed_in(business_owner).patch(
        f"/place/{point.pk}/", {"has_badge": True}
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_whoever_only_sees_places_does_not_edit_them(
    make_member: Callable[..., ApiUser],
) -> None:
    point = make_point()
    client = signed_in(make_member("equipo@example.com", "places.view"))

    response = client.patch(f"/place/{point.pk}/", {"name": "Otra"})

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_a_place_in_a_published_circuit_is_not_retired(
    make_member: Callable[..., ApiUser],
) -> None:
    first, second = make_point(name="Uno"), make_point(name="Dos")
    make_circuit([first, second])
    client = signed_in(make_member("equipo@example.com", "places.manage"))

    response = client.delete(f"/place/{first.pk}/")

    assert response.status_code == HTTPStatus.CONFLICT


def test_the_team_retires_a_place_and_the_app_stops_seeing_it(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    point = make_point()
    team = signed_in(make_member("equipo@example.com", "places.manage"))

    assert team.delete(f"/place/{point.pk}/").status_code == HTTPStatus.NO_CONTENT
    assert client.get(f"/stop/{point.pk}/").status_code == HTTPStatus.NOT_FOUND


def test_a_business_does_not_retire_its_own_place(business_owner: ApiUser) -> None:
    point = place_of(business_owner)

    response = signed_in(business_owner).delete(f"/place/{point.pk}/")

    assert response.status_code == HTTPStatus.FORBIDDEN


########################################################################################
# Dueño


def test_the_team_gives_a_place_to_a_verified_municipality(
    make_member: Callable[..., ApiUser],
) -> None:
    point = make_point()
    municipality = verified_municipality()
    client = signed_in(make_member("equipo@example.com", "organizations.manage"))

    response = client.put(
        f"/place/{point.pk}/owner/",
        {"id": str(municipality.pk), "kind": "municipality"},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["owner"]["id"] == str(municipality.pk)


def test_a_business_keeps_a_single_place(
    make_member: Callable[..., ApiUser],
    business_owner: ApiUser,
) -> None:
    business = place_of(business_owner).business
    point = make_point()
    client = signed_in(make_member("equipo@example.com", "places.manage"))

    response = client.put(
        f"/place/{point.pk}/owner/",
        {"id": str(business.pk), "kind": "business"},  # ty: ignore[unresolved-attribute]
    )

    assert response.status_code == HTTPStatus.CONFLICT


########################################################################################
# Ficha y novedades


def test_the_owner_fills_the_profile_of_its_place(
    client: DMRClient,
    business_owner: ApiUser,
) -> None:
    point = place_of(business_owner)
    owner = signed_in(business_owner)

    response = owner.put(
        f"/place/{point.pk}/profile/",
        {
            "amenities": ["card", "wifi"],
            "contact": {"phone": "+505 2311 0000", "instagram": "sacuanjoche"},
            "languages": ["Español", "Inglés"],
            "offerings": [{"name": "Vigorón", "price": 120}, {"name": "Fresco"}],
        },
    )

    assert response.status_code == HTTPStatus.OK, response.content
    profile = body(client.get(f"/stop/{point.pk}/"))["profile"]
    assert [item["name"] for item in profile["offerings"]] == ["Vigorón", "Fresco"]
    assert profile["offerings"][1]["price"] is None
    assert profile["contact"]["instagram"] == "sacuanjoche"


def test_the_owner_publishes_and_hides_posts(
    client: DMRClient,
    business_owner: ApiUser,
) -> None:
    point = place_of(business_owner)
    owner = signed_in(business_owner)

    created = owner.post(
        "/post/",
        {
            "body": "Desde hoy abrimos los domingos al mediodía.",
            "place_id": str(point.pk),
            "title": "Abrimos domingos",
        },
    )
    post_id = body(created)["id"]
    hidden = owner.patch(f"/post/{post_id}/", {"visible": False})

    assert created.status_code == HTTPStatus.CREATED, created.content
    assert hidden.status_code == HTTPStatus.OK, hidden.content
    assert body(client.get(f"/stop/{point.pk}/"))["posts"] == []


def test_a_moderator_removes_a_post_of_any_place(
    make_member: Callable[..., ApiUser],
) -> None:
    point = make_point()
    publication = Publication.objects.create(
        body="Algo que no corresponde publicar.", point=point, title="Spam"
    )
    client = signed_in(
        make_member("equipo@example.com", "content.moderate", "places.view")
    )

    response = client.delete(f"/post/{publication.pk}/")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not Publication.objects.filter(pk=publication.pk).exists()


########################################################################################
# El lugar de un comercio aprobado


def test_approving_a_business_gives_it_its_place(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
) -> None:
    business = verified_business(verified=False)
    Photo.objects.create(business=business, file_key="signature-dish-photo/vigoron.jpg")
    request = VerificationRequest.objects.create(
        business=business,
        status=VerificationStatus.objects.get(code=VerificationStates.SUBMITTED),
    )
    operator(make_user(email="negocio@example.com"), business, "Negocio")
    client = signed_in(make_member("equipo@example.com", "organizations.manage"))

    response = client.post(f"/verification-request/{request.pk}/approve/", {})

    assert response.status_code == HTTPStatus.OK, response.content
    point = PointOfInterest.objects.get(business=business)
    assert point.name == "El Sacuanjoche"
    assert point.pillar.code == "gastronomia"
    assert list(point.photos.values_list("file_key", flat=True)) == [
        "signature-dish-photo/vigoron.jpg"
    ]


def test_the_place_of_a_business_is_created_once() -> None:
    business = verified_business()

    first = ensure_business_place_sync(business)
    second = ensure_business_place_sync(business)

    assert first.pk == second.pk
    assert PointOfInterest.objects.filter(business=business).count() == 1


def test_a_place_keeps_a_single_owner() -> None:
    with pytest.raises(IntegrityError), atomic():
        make_point(
            business=verified_business(),
            municipality=verified_municipality(),
        )
