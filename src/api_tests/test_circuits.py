from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_territory.models import Circuit
from api_tests.helpers import body
from api_tests.territory_helpers import (
    CIRCUIT_PHOTO,
    circuit_body,
    city,
    make_circuit,
    make_point,
    operator,
    signed_in,
    verified_municipality,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_auth.models import ApiUser
    from api_territory.models import PointOfInterest

########################################################################################

pytestmark = pytest.mark.django_db

CIRCUITS = "/official-circuit/"


@pytest.fixture(autouse=True)
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    storage.put(CIRCUIT_PHOTO, content_type="image/jpeg")
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


@pytest.fixture
def points() -> list[PointOfInterest]:
    return [
        make_point(name="Catedral de León"),
        make_point(name="Iglesia La Recolección"),
        make_point(name="Museo de Leyendas"),
    ]


@pytest.fixture
def mayor(make_user: Callable[..., ApiUser]) -> ApiUser:
    return operator(
        make_user(email="alcaldia@example.com"),
        verified_municipality(),
        "Alcaldía",
    )


def manager(make_member: Callable[..., ApiUser], *permissions: str) -> DMRClient:
    return signed_in(make_member("equipo@example.com", *permissions))


########################################################################################
# Lo que ve la app


def test_the_app_only_sees_published_circuits(
    client: DMRClient,
    points: list[PointOfInterest],
) -> None:
    published = make_circuit(points[:2], title="Publicado")
    draft = make_circuit(points[:2], status="borrador", title="Borrador")

    listed = body(client.get("/circuit/"))

    assert [item["id"] for item in listed] == [str(published.pk)]
    assert client.get(f"/circuit/{draft.pk}/").status_code == HTTPStatus.NOT_FOUND


def test_the_detail_brings_the_stops_in_order(
    client: DMRClient,
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit([points[2], points[0]])

    detail = body(client.get(f"/circuit/{circuit.pk}/"))

    assert [stop["point"]["name"] for stop in detail["stops"]] == [
        "Museo de Leyendas",
        "Catedral de León",
    ]
    assert detail["stop_ids"] == [str(points[2].pk), str(points[0].pk)]


def test_the_app_filters_circuits_by_city(
    client: DMRClient,
    points: list[PointOfInterest],
) -> None:
    make_circuit(points[:2])
    granada = [make_point("granada", name="Uno"), make_point("granada", name="Dos")]
    make_circuit(granada, title="Granada a pie")

    listed = body(client.get("/circuit/", {"city": "granada"}))

    assert [item["title"] for item in listed] == ["Granada a pie"]


########################################################################################
# Quién entra al portal


def test_the_portal_circuits_need_a_session(client: DMRClient) -> None:
    assert client.get(CIRCUITS).status_code == HTTPStatus.UNAUTHORIZED


def test_whoever_only_sees_circuits_does_not_create_them(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    client = manager(make_member, "circuits.view")

    assert client.get(CIRCUITS).status_code == HTTPStatus.OK
    assert (
        client.post(CIRCUITS, circuit_body(points)).status_code == HTTPStatus.FORBIDDEN
    )


def test_without_permission_or_municipality_there_is_no_access(
    make_member: Callable[..., ApiUser],
) -> None:
    client = manager(make_member, "places.view")

    assert client.get(CIRCUITS).status_code == HTTPStatus.FORBIDDEN


########################################################################################
# Crear


def test_the_team_creates_and_publishes_a_circuit(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")

    response = team.post(CIRCUITS, circuit_body(points, status="published"))

    assert response.status_code == HTTPStatus.CREATED, response.content
    created = body(response)
    assert created["status"] == "published"
    assert created["version"] == 1
    assert created["start_times"] == ["08:30", "14:00"]
    assert created["images"][0]["key"] == CIRCUIT_PHOTO
    assert client.get(f"/circuit/{created['id']}/").status_code == HTTPStatus.OK


def test_a_special_needs_bonus_badges(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")

    without = team.post(CIRCUITS, circuit_body(points, kind="kplan"))
    with_bonus = team.post(
        CIRCUITS,
        circuit_body(
            points,
            available_from="2026-12-01",
            available_until="2026-12-31",
            bonus_badges=2,
            kind="kplan",
        ),
    )

    assert without.status_code == HTTPStatus.BAD_REQUEST
    assert with_bonus.status_code == HTTPStatus.CREATED, with_bonus.content
    assert body(with_bonus)["bonus_badges"] == 2
    assert body(with_bonus)["available_until"] == "2026-12-31"


def test_a_creative_circuit_belongs_to_the_verified_municipality(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")

    orphan = team.post(CIRCUITS, circuit_body(points, kind="creative"))
    municipality = verified_municipality()
    created = team.post(CIRCUITS, circuit_body(points, kind="creative"))

    assert orphan.status_code == HTTPStatus.BAD_REQUEST
    assert created.status_code == HTTPStatus.CREATED, created.content
    assert body(created)["municipality"]["id"] == str(municipality.pk)
    assert body(created)["booking_mode"] == "group"
    assert body(created)["bonus_badges"] == 3


def test_a_municipality_creates_creative_circuits_of_its_city(
    mayor: ApiUser,
    points: list[PointOfInterest],
) -> None:
    client = signed_in(mayor)

    response = client.post(CIRCUITS, circuit_body(points, kind="private"))

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["kind"] == "creative"
    assert body(response)["city"]["code"] == "leon"


def test_a_municipality_does_not_publish_in_another_city(
    mayor: ApiUser,
    points: list[PointOfInterest],
) -> None:
    client = signed_in(mayor)

    response = client.post(
        CIRCUITS,
        circuit_body(points, city_id=str(city("granada").pk)),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    "override",
    [
        {"stops": "one"},
        {"stops": "repeated"},
        {"stops": "elsewhere"},
        {"start_times": ["08:30", "08:30"]},
    ],
)
def test_the_route_has_to_make_sense(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
    override: dict,
) -> None:
    team = manager(make_member, "circuits.manage")
    stops = {
        "elsewhere": [*points[:1], make_point("granada", name="Lejos")],
        "one": points[:1],
        "repeated": [points[0], points[0]],
    }
    chosen = stops.get(override.get("stops", ""), points)
    extra = {key: value for key, value in override.items() if key != "stops"}

    response = team.post(CIRCUITS, circuit_body(chosen, **extra))

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content


def test_publishing_needs_a_photo(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")

    draft = team.post(CIRCUITS, circuit_body(points, images=[]))
    published = team.post(CIRCUITS, circuit_body(points, images=[], status="published"))

    assert draft.status_code == HTTPStatus.CREATED, draft.content
    assert published.status_code == HTTPStatus.BAD_REQUEST
    assert "body.images" in body(published)["field_errors"]


########################################################################################
# Ámbito de la alcaldía (RF-A-03)


def test_a_municipality_does_not_see_circuits_of_another_city(
    mayor: ApiUser,
) -> None:
    granada = [make_point("granada", name="Uno"), make_point("granada", name="Dos")]
    elsewhere = make_circuit(granada, title="Granada a pie")
    client = signed_in(mayor)

    assert client.get(f"{CIRCUITS}{elsewhere.pk}/").status_code == HTTPStatus.NOT_FOUND
    assert body(client.get(CIRCUITS))["elements"] == 0


def test_a_municipality_sees_but_does_not_edit_the_team_circuits_of_its_city(
    mayor: ApiUser,
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit(points[:2])
    client = signed_in(mayor)

    seen = client.get(f"{CIRCUITS}{circuit.pk}/")
    edited = client.put(f"{CIRCUITS}{circuit.pk}/", circuit_body(points))

    assert seen.status_code == HTTPStatus.OK
    assert edited.status_code == HTTPStatus.FORBIDDEN


########################################################################################
# Editar, versión y retiro


def test_the_version_only_rises_when_the_route_changes(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")
    created = body(team.post(CIRCUITS, circuit_body(points)))
    path = f"{CIRCUITS}{created['id']}/"

    renamed = team.put(path, circuit_body(points, title="León colonial y sus murales"))
    reordered = team.put(path, circuit_body(list(reversed(points))))

    assert body(renamed)["version"] == 1
    assert body(reordered)["version"] == 2


def test_drafting_a_published_circuit_unpublishes_it(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")
    created = body(team.post(CIRCUITS, circuit_body(points, status="published")))

    response = team.put(f"{CIRCUITS}{created['id']}/", circuit_body(points))

    assert body(response)["status"] == "unpublished"
    assert client.get(f"/circuit/{created['id']}/").status_code == HTTPStatus.NOT_FOUND


def test_a_retired_circuit_leaves_the_app_and_is_not_edited(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit(points[:2])
    team = manager(make_member, "circuits.manage")

    retired = team.delete(f"{CIRCUITS}{circuit.pk}/")
    edited = team.put(f"{CIRCUITS}{circuit.pk}/", circuit_body(points))

    assert retired.status_code == HTTPStatus.NO_CONTENT
    assert edited.status_code == HTTPStatus.CONFLICT
    assert client.get(f"/circuit/{circuit.pk}/").status_code == HTTPStatus.NOT_FOUND
    assert Circuit.objects.filter(pk=circuit.pk).exists()


def test_the_list_leaves_out_the_retired_unless_asked(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    make_circuit(points[:2], status="retirado", title="Viejo")
    make_circuit(points[:2], title="Vigente")
    team = manager(make_member, "circuits.view")

    current = body(team.get(CIRCUITS))
    retired = body(team.get(CIRCUITS, {"status": "retired"}))

    assert [item["title"] for item in current["results"]] == ["Vigente"]
    assert [item["title"] for item in retired["results"]] == ["Viejo"]
