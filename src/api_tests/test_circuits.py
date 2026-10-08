from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.db.models import F

from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_notifications.models import Notification
from api_services.models import Booking, GuidedDeparture
from api_territory.models import Circuit, CircuitStatus, CircuitStop, PointOfInterest
from api_tests.helpers import body
from api_tests.services_helpers import book, make_guide, publish_departure
from api_tests.territory_helpers import (
    CIRCUIT_PHOTO,
    PLACE_PHOTO,
    circuit_body,
    city,
    make_circuit,
    make_point,
    mobile_headers,
    operator,
    signed_in,
    tourist,
    verified_municipality,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db

CIRCUITS = "/official-circuit/"


@pytest.fixture(autouse=True)
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    storage.put(CIRCUIT_PHOTO, content_type="image/jpeg")
    storage.put(PLACE_PHOTO, content_type="image/jpeg")
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


def test_the_list_brings_the_route_to_draw_and_time_it(
    client: DMRClient,
    points: list[PointOfInterest],
) -> None:
    make_circuit(points[:2])

    listed = body(client.get("/circuit/"))

    assert [item["name"] for item in listed[0]["route"]] == [
        "Catedral de León",
        "Iglesia La Recolección",
    ]
    assert listed[0]["route"][0]["visit_minutes"] == 30


def test_the_photos_of_public_content_last_a_day(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    team = signed_in(make_member("equipo@example.com", "places.manage"))
    place = body(
        team.post(
            "/place/",
            {
                "city_id": str(city().pk),
                "images": [PLACE_PHOTO],
                "latitude": 12.435,
                "longitude": -86.879,
                "name": "Museo de Leyendas",
                "pillar": "cultura",
            },
        )
    )

    detail = body(client.get(f"/stop/{place['id']}/"))

    assert detail["images"][0]["url"].endswith("expires=86400")


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


########################################################################################
# Las salidas de guía de un circuito que sale de la app


@pytest.fixture
def guide_user(make_user: Callable[..., ApiUser]) -> ApiUser:
    user = make_user(email="guia@example.com", first_name="Pedro")
    make_guide(user)

    return user


def booked(
    client: DMRClient,
    circuit: Circuit,
    guide_user: ApiUser,
    tourist_user: ApiUser,
) -> dict:
    departure = publish_departure(client, mobile_headers(guide_user), circuit)

    return book(client, tourist(tourist_user), departure)


def test_retiring_a_circuit_cancels_its_departures_and_bookings(
    client: DMRClient,
    guide_user: ApiUser,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit(points[:2])
    Circuit.objects.filter(pk=circuit.pk).update(price_adult=500)
    ana = make_user(email="turista@example.com")
    booking = booked(client, circuit, guide_user, ana)

    manager(make_member, "circuits.manage").delete(f"{CIRCUITS}{circuit.pk}/")

    found = Booking.objects.select_related("status").get(pk=booking["id"])
    title = "Se canceló tu recorrido"
    assert found.status.code == "cancelada"
    assert found.payment_status == "anulado"
    assert GuidedDeparture.objects.get(circuit=circuit).cancelled_at is not None
    assert Notification.objects.filter(title=title, user=ana).exists()
    assert Notification.objects.filter(title=title, user=guide_user).exists()


def test_unpublishing_a_circuit_cancels_its_bookings(
    client: DMRClient,
    guide_user: ApiUser,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit(points[:2])
    booking = booked(client, circuit, guide_user, make_user(email="t@example.com"))
    team = manager(make_member, "circuits.manage")

    response = team.put(f"{CIRCUITS}{circuit.pk}/", circuit_body(points[:2]))

    assert body(response)["status"] == "unpublished"
    assert Booking.objects.get(pk=booking["id"]).cancelled_at is not None


def test_editing_a_published_circuit_keeps_its_bookings(
    client: DMRClient,
    guide_user: ApiUser,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit(points[:2])
    booking = booked(client, circuit, guide_user, make_user(email="t@example.com"))
    team = manager(make_member, "circuits.manage")

    team.put(f"{CIRCUITS}{circuit.pk}/", circuit_body(points[:2], status="published"))

    assert Booking.objects.get(pk=booking["id"]).cancelled_at is None


def test_the_portal_sees_the_departures_of_an_unpublished_circuit(
    client: DMRClient,
    guide_user: ApiUser,
    make_member: Callable[..., ApiUser],
    mayor: ApiUser,
    points: list[PointOfInterest],
) -> None:
    circuit = make_circuit(points[:2])
    departure = publish_departure(client, mobile_headers(guide_user), circuit)
    Circuit.objects.filter(pk=circuit.pk).update(
        status=CircuitStatus.objects.get(code="despublicado")
    )
    path = f"{CIRCUITS}{circuit.pk}/departure/"

    team = body(manager(make_member, "circuits.view").get(path))
    municipality = body(signed_in(mayor).get(path))
    public = body(client.get(f"/circuit/{circuit.pk}/departure/"))

    assert [item["id"] for item in team] == [departure["id"]]
    assert [item["id"] for item in municipality] == [departure["id"]]
    assert public == []


def test_the_departures_of_another_city_do_not_exist_for_a_municipality(
    mayor: ApiUser,
) -> None:
    granada = [make_point("granada", name="Uno"), make_point("granada", name="Dos")]
    elsewhere = make_circuit(granada, title="Granada a pie")

    response = signed_in(mayor).get(f"{CIRCUITS}{elsewhere.pk}/departure/")

    assert response.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Lo que se calcula


def test_a_circuit_with_one_stop_says_why(
    make_member: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    team = manager(make_member, "circuits.manage")

    response = team.post(CIRCUITS, circuit_body(points[:1]))

    assert body(response)["field_errors"]["body.stops"] == (
        "Este campo necesita al menos 2 elemento(s)."
    )


def test_the_duration_counts_the_estimated_walks(
    client: DMRClient,
    points: list[PointOfInterest],
) -> None:
    first, second, third = points
    # a un kilómetro en línea recta: 1,3 km por calle, 20 minutos a pie
    PointOfInterest.objects.filter(pk=second.pk).update(
        latitude=F("latitude") + Decimal("0.009")
    )
    circuit = make_circuit([first, second, third])
    # el tramo escrito a mano manda sobre el estimado
    CircuitStop.objects.filter(circuit=circuit, point=third).update(leg_minutes=12)

    listed = body(client.get("/circuit/"))

    assert listed[0]["duration_minutes"] == 30 + 20 + 30 + 12 + 30


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
