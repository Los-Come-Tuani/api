from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group
from django.db import DatabaseError
from django.db.transaction import atomic

from api_auth.enums import ApiUserTypes
from api_auth.models import ApiUserGroups
from api_itineraries.models import Itinerary, ItineraryStatus, ItineraryStop
from api_territory.models import CircuitStop
from api_tests.helpers import body
from api_tests.territory_helpers import make_circuit, make_point, mobile_headers

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_auth.models import ApiUser
    from api_territory.models import Circuit, PointOfInterest

########################################################################################

pytestmark = pytest.mark.django_db

ITINERARIES = "/itinerary/"


def tourist(make_user: Callable[..., ApiUser], email: str) -> dict[str, str]:
    user = make_user(email=email)
    ApiUserGroups.objects.create(
        api_user=user, group=Group.objects.get(name=ApiUserTypes.CLIENT.value)
    )

    return mobile_headers(user)


@pytest.fixture
def headers(make_user: Callable[..., ApiUser]) -> dict[str, str]:
    return tourist(make_user, "turista@example.com")


@pytest.fixture
def points() -> list[PointOfInterest]:
    return [
        make_point(name="Catedral de León"),
        make_point(name="Iglesia La Recolección"),
        make_point(name="Museo de Leyendas"),
    ]


@pytest.fixture
def circuit(points: list[PointOfInterest]) -> Circuit:
    return make_circuit(points[:2])


def ids(response_body: dict) -> list[str]:
    return [stop["point_id"] for stop in response_body["stops"]]


########################################################################################
# Seguir un circuito tal cual


def test_following_a_circuit_reads_its_stops_without_copying(
    client: DMRClient,
    circuit: Circuit,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    response = client.post(
        ITINERARIES,
        {"circuit_id": str(circuit.pk), "title": "Mi León"},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    created = body(response)
    assert created["adjusted"] is False
    assert created["followed_circuit"]["id"] == str(circuit.pk)
    assert created["origin_circuit_ids"] == [str(circuit.pk)]
    assert ids(created) == [str(points[0].pk), str(points[1].pk)]
    assert not ItineraryStop.objects.exists()


def test_a_correction_of_the_circuit_reaches_whoever_follows_it(
    client: DMRClient,
    circuit: Circuit,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    created = body(
        client.post(
            ITINERARIES,
            {"circuit_id": str(circuit.pk), "title": "Mi León"},
            headers=headers,
        )
    )
    CircuitStop.objects.create(circuit=circuit, order=2, point=points[2])

    again = body(client.get(f"{ITINERARIES}{created['id']}/", headers=headers))

    assert ids(again)[-1] == str(points[2].pk)


def test_a_draft_circuit_is_not_followed(
    client: DMRClient,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    draft = make_circuit(points[:2], status="borrador")

    response = client.post(
        ITINERARIES,
        {"circuit_id": str(draft.pk), "title": "Borrador"},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


########################################################################################
# Ajustar: la copia propia de D-33


def test_changing_the_stops_makes_an_own_copy_for_good(
    client: DMRClient,
    circuit: Circuit,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    created = body(
        client.post(
            ITINERARIES,
            {"circuit_id": str(circuit.pk), "title": "Mi León"},
            headers=headers,
        )
    )
    path = f"{ITINERARIES}{created['id']}/"

    adjusted = client.patch(
        path,
        {"stop_ids": [str(points[1].pk), str(points[0].pk), str(points[2].pk)]},
        headers=headers,
    )
    CircuitStop.objects.filter(circuit=circuit).delete()
    later = body(client.get(path, headers=headers))

    assert adjusted.status_code == HTTPStatus.OK, adjusted.content
    assert body(adjusted)["adjusted"] is True
    assert body(adjusted)["followed_circuit"] is None
    assert body(adjusted)["origin_circuit_ids"] == [str(circuit.pk)]
    # ya no lee el circuito: lo copiado se queda
    assert ids(later) == [str(points[1].pk), str(points[0].pk), str(points[2].pk)]
    assert later["stops"][0]["name"] == "Iglesia La Recolección"


def test_the_same_stops_as_the_circuit_are_not_an_adjustment(
    client: DMRClient,
    circuit: Circuit,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    created = body(
        client.post(
            ITINERARIES,
            {"circuit_id": str(circuit.pk), "title": "Mi León"},
            headers=headers,
        )
    )

    response = client.patch(
        f"{ITINERARIES}{created['id']}/",
        {"stop_ids": [str(points[0].pk), str(points[1].pk)], "pace": "relaxed"},
        headers=headers,
    )

    assert body(response)["adjusted"] is False
    assert body(response)["pace"] == "relaxed"


def test_a_tourist_builds_an_itinerary_from_scratch(
    client: DMRClient,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    response = client.post(
        ITINERARIES,
        {
            "start_time": "08:00",
            "stop_ids": [str(points[2].pk)],
            "title": "Por mi cuenta",
            "travel_mode": "vehicle",
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["adjusted"] is True
    assert body(response)["start_time"] == "08:00"
    assert body(response)["travel_mode"] == "vehicle"
    assert ids(body(response)) == [str(points[2].pk)]


def test_the_plan_keeps_the_fixed_arrivals(
    client: DMRClient,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    created = body(
        client.post(
            ITINERARIES,
            {"stop_ids": [str(points[0].pk)], "title": "Con hora fija"},
            headers=headers,
        )
    )

    response = client.patch(
        f"{ITINERARIES}{created['id']}/",
        {"fixed_arrivals": {"0": 600}, "title": "Con la hora fijada"},
        headers=headers,
    )

    assert body(response)["fixed_arrivals"] == {"0": 600}
    assert body(response)["title"] == "Con la hora fijada"


########################################################################################
# De quién es


def test_an_itinerary_of_someone_else_does_not_exist(
    client: DMRClient,
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
    points: list[PointOfInterest],
) -> None:
    created = body(
        client.post(
            ITINERARIES,
            {"stop_ids": [str(points[0].pk)], "title": "Mío"},
            headers=headers,
        )
    )
    other = tourist(make_user, "otra@example.com")

    assert body(client.get(ITINERARIES, headers=other)) == []
    assert (
        client.get(f"{ITINERARIES}{created['id']}/", headers=other).status_code
        == HTTPStatus.NOT_FOUND
    )


def test_deleting_an_itinerary_takes_it_out_of_the_collection(
    client: DMRClient,
    headers: dict[str, str],
    points: list[PointOfInterest],
) -> None:
    created = body(
        client.post(
            ITINERARIES,
            {"stop_ids": [str(points[0].pk)], "title": "Se va"},
            headers=headers,
        )
    )

    response = client.delete(f"{ITINERARIES}{created['id']}/", headers=headers)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert body(client.get(ITINERARIES, headers=headers)) == []
    assert Itinerary.objects.filter(pk=created["id"]).exists()


def test_the_itineraries_need_a_session(client: DMRClient) -> None:
    assert client.get(ITINERARIES).status_code == HTTPStatus.UNAUTHORIZED


########################################################################################
# Lo que impone la base


def test_an_itinerary_that_follows_a_circuit_has_no_own_stops(
    make_user: Callable[..., ApiUser],
    circuit: Circuit,
) -> None:
    itinerary = Itinerary.objects.create(
        followed_circuit=circuit,
        status=ItineraryStatus.objects.get(code="planificado"),
        title="Sigue",
        user=make_user(email="base@example.com"),
    )

    with pytest.raises(DatabaseError), atomic():
        ItineraryStop.objects.create(
            itinerary=itinerary,
            latitude=Decimal("12.4"),
            longitude=Decimal("-86.8"),
            name="Propia",
            order=0,
        )


def test_an_adjusted_itinerary_does_not_go_back(
    make_user: Callable[..., ApiUser],
) -> None:
    itinerary = Itinerary.objects.create(
        adjusted=True,
        status=ItineraryStatus.objects.get(code="planificado"),
        title="Propio",
        user=make_user(email="base@example.com"),
    )

    with pytest.raises(DatabaseError), atomic():
        Itinerary.objects.filter(pk=itinerary.pk).update(adjusted=False)
