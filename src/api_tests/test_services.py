from datetime import time, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group
from django.utils.timezone import localdate, localtime, now

from api_auth.models import ApiUserGroups
from api_catalogs.models import ServiceType
from api_itineraries.models import Itinerary, ItineraryStatus, ItineraryStop
from api_profiles.models import ProviderProfile, ProviderService, ProviderStatus
from api_services.models import Booking, GuidedDeparture
from api_territory.models import Circuit
from api_tests.helpers import body
from api_tests.territory_helpers import (
    city,
    make_circuit,
    make_point,
    mobile_headers,
    signed_in,
    tourist,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db


def make_guide(user: ApiUser, *, code: str | None = "leon") -> ProviderProfile:
    provider = ProviderProfile.objects.create(
        city=None if code is None else city(code),
        phone="8888-0000",
        presentation="Guía de León desde hace diez años.",
        status=ProviderStatus.objects.get(code="activo"),
        user=user,
    )
    ProviderService.objects.create(
        provider=provider, service=ServiceType.objects.get(code="guia")
    )
    ApiUserGroups.objects.create(api_user=user, group=Group.objects.get(name="Guía"))

    return provider


def days(offset: int) -> date:
    return localdate() + timedelta(days=offset)


@pytest.fixture
def circuit() -> Circuit:
    circuit = make_circuit([make_point(name="Uno"), make_point(name="Dos")])
    Circuit.objects.filter(pk=circuit.pk).update(price_adult=250, price_child=100)

    return circuit


@pytest.fixture
def group_circuit() -> Circuit:
    circuit = make_circuit(
        [make_point(name="Tres"), make_point(name="Cuatro")], title="En grupo"
    )
    Circuit.objects.filter(pk=circuit.pk).update(booking_mode="group")

    return circuit


@pytest.fixture
def guide_user(make_user: Callable[..., ApiUser]) -> ApiUser:
    user = make_user(email="guia@example.com", first_name="Pedro")
    make_guide(user)

    return user


@pytest.fixture
def guide(guide_user: ApiUser) -> dict[str, str]:
    return mobile_headers(guide_user)


@pytest.fixture
def ana(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user(email="turista@example.com", first_name="Ana")


@pytest.fixture
def headers(ana: ApiUser) -> dict[str, str]:
    return tourist(ana)


def publish_departure(
    client: DMRClient,
    guide: dict[str, str],
    circuit: Circuit,
    **override: object,
) -> dict:
    response = client.post(
        "/departure/",
        {
            "capacity": 4,
            "circuit_id": str(circuit.pk),
            "date": days(3).isoformat(),
            "start_time": "08:30",
            **override,
        },
        headers=guide,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


def book(
    client: DMRClient, headers: dict[str, str], departure: dict, **party: int
) -> dict:
    response = client.post(
        "/booking/",
        {"departure_id": departure["id"], **party},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


def own_itinerary(user: ApiUser) -> Itinerary:
    itinerary = Itinerary.objects.create(
        adjusted=True,
        status=ItineraryStatus.objects.get(code="planificado"),
        title="Mi León",
        user=user,
    )
    point = make_point(name="Mi parada")
    ItineraryStop.objects.create(
        itinerary=itinerary,
        latitude=point.latitude,
        longitude=point.longitude,
        name=point.name,
        order=0,
        point=point,
    )

    return itinerary


########################################################################################
# Los guías que ve el turista


def test_the_tourist_sees_the_approved_guides(
    client: DMRClient,
    guide_user: ApiUser,
    make_user: Callable[..., ApiUser],
) -> None:
    suspended = make_guide(make_user(email="otro@example.com"))
    ProviderProfile.objects.filter(pk=suspended.pk).update(
        status=ProviderStatus.objects.get(code="suspendido")
    )

    listed = body(client.get("/guide/", {"city": "leon"}))

    assert [item["name"] for item in listed["results"]] == ["Pedro"]
    assert listed["results"][0]["services"] == ["guia"]
    assert listed["results"][0]["rating"] is None
    # la cuenta, para reportarlo
    assert listed["results"][0]["user_id"] == str(guide_user.pk)


########################################################################################
# Salidas del guía en circuitos oficiales


def test_a_guide_publishes_a_departure_of_an_official_circuit(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)

    public = body(client.get(f"/circuit/{circuit.pk}/departure/"))

    assert departure["exclusive"] is True
    assert [item["id"] for item in public] == [departure["id"]]
    assert public[0]["guide"]["name"] == "Pedro"


def test_a_guide_of_another_city_does_not_guide_here(
    client: DMRClient,
    circuit: Circuit,
    make_user: Callable[..., ApiUser],
) -> None:
    user = make_user(email="granada@example.com")
    make_guide(user, code="granada")

    response = client.post(
        "/departure/",
        {
            "circuit_id": str(circuit.pk),
            "date": days(2).isoformat(),
            "start_time": "08:30",
        },
        headers=mobile_headers(user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_only_an_approved_guide_publishes_departures(
    client: DMRClient,
    circuit: Circuit,
    headers: dict[str, str],
) -> None:
    response = client.post(
        "/departure/",
        {
            "circuit_id": str(circuit.pk),
            "date": days(2).isoformat(),
            "start_time": "09:00",
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_a_guide_does_not_go_out_twice_at_the_same_time(
    client: DMRClient,
    circuit: Circuit,
    group_circuit: Circuit,
    guide: dict[str, str],
) -> None:
    publish_departure(client, guide, circuit)

    response = client.post(
        "/departure/",
        {
            "circuit_id": str(group_circuit.pk),
            "date": days(3).isoformat(),
            "start_time": "08:30",
        },
        headers=guide,
    )

    assert response.status_code == HTTPStatus.CONFLICT


########################################################################################
# Reservar una salida


def test_a_tourist_books_a_private_departure_with_a_frozen_price(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)

    booking = book(client, headers, departure, adults=2, children=1)
    Circuit.objects.filter(pk=circuit.pk).update(price_adult=999)
    again = body(client.get(f"/booking/{booking['id']}/", headers=headers))

    assert booking["status"] == "confirmed"
    assert booking["amount"] == 600
    assert again["amount"] == 600
    assert booking["payment_status"] == "pendiente"
    assert booking["role"] == "tourist"


def test_a_private_departure_takes_a_single_booking(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
) -> None:
    departure = publish_departure(client, guide, circuit)
    book(client, headers, departure)
    other = tourist(make_user(email="otra@example.com"))

    response = client.post(
        "/booking/", {"departure_id": departure["id"]}, headers=other
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_a_group_departure_fills_its_spots(
    client: DMRClient,
    group_circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
) -> None:
    departure = publish_departure(client, guide, group_circuit, capacity=3)
    book(client, headers, departure, adults=2)
    other = tourist(make_user(email="otra@example.com"))

    too_many = client.post(
        "/booking/", {"adults": 2, "departure_id": departure["id"]}, headers=other
    )
    fits = client.post(
        "/booking/", {"adults": 1, "departure_id": departure["id"]}, headers=other
    )

    assert too_many.status_code == HTTPStatus.CONFLICT
    assert fits.status_code == HTTPStatus.CREATED


########################################################################################
# Cancelar


def test_the_tourist_cancels_up_to_24_hours_before(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)

    response = client.post(
        f"/booking/{booking['id']}/cancel/",
        {"reason": "Cambio de planes"},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["status"] == "cancelled"


def test_the_tourist_does_not_cancel_on_the_same_day(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    later = localtime(now() + timedelta(hours=3))
    departure = publish_departure(
        client,
        guide,
        circuit,
        date=later.date().isoformat(),
        start_time=later.strftime("%H:%M"),
    )
    booking = book(client, headers, departure)

    response = client.post(f"/booking/{booking['id']}/cancel/", {}, headers=headers)

    assert response.status_code == HTTPStatus.CONFLICT
    assert booking["can_cancel"] is False


def test_the_guide_cancels_with_a_reason(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)

    without = client.post(f"/booking/{booking['id']}/cancel/", {}, headers=guide)
    with_reason = client.post(
        f"/booking/{booking['id']}/cancel/", {"reason": "Estoy enfermo"}, headers=guide
    )

    assert without.status_code == HTTPStatus.BAD_REQUEST
    assert body(with_reason)["status"] == "cancelled"


def test_cancelling_a_departure_cancels_its_bookings(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)

    response = client.post(
        f"/departure/{departure['id']}/cancel/",
        {"reason": "Lluvia fuerte"},
        headers=guide,
    )

    assert body(response)["cancelled"] is True
    assert body(client.get(f"/booking/{booking['id']}/", headers=headers))[
        "status"
    ] == ("cancelled")


def test_a_booking_of_someone_else_does_not_exist(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)
    other = tourist(make_user(email="otra@example.com"))

    response = client.get(f"/booking/{booking['id']}/", headers=other)

    assert response.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Convocatorias en un itinerario propio


def test_a_tourist_posts_a_request_and_picks_a_guide(
    ana: ApiUser,
    client: DMRClient,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    itinerary = own_itinerary(ana)

    request = client.post(
        "/service-request/",
        {
            "adults": 2,
            "date": days(5).isoformat(),
            "itinerary_id": str(itinerary.pk),
            "max_fee": 900,
            "start_time": "09:00",
        },
        headers=headers,
    )
    assert request.status_code == HTTPStatus.CREATED, request.content
    request_id = body(request)["id"]

    seen = body(client.get("/open-request/", headers=guide))
    assert [item["id"] for item in seen] == [request_id]

    too_much = client.post(
        f"/open-request/{request_id}/apply/", {"fee": 1000}, headers=guide
    )
    applied = client.post(
        f"/open-request/{request_id}/apply/",
        {"fee": 800, "message": "Conozco cada rincón."},
        headers=guide,
    )
    assert too_much.status_code == HTTPStatus.BAD_REQUEST
    assert applied.status_code == HTTPStatus.CREATED, applied.content

    mine = body(client.get("/application/mine/", headers=guide))
    assert mine[0]["request"]["itinerary"]["title"] == "Mi León"
    assert mine[0]["request"]["start_time"] == "09:00"
    assert mine[0]["request"]["adults"] == 2

    accepted = client.post(
        f"/service-request/{request_id}/accept/",
        {"application_id": body(applied)["id"]},
        headers=headers,
    )

    assert accepted.status_code == HTTPStatus.CREATED, accepted.content
    assert body(accepted)["amount"] == 800
    assert body(accepted)["itinerary"]["title"] == "Mi León"
    assert (
        body(client.get(f"/service-request/{request_id}/", headers=headers))["status"]
        == "awarded"
    )


def test_an_official_circuit_is_booked_not_requested(
    ana: ApiUser,
    circuit: Circuit,
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    following = Itinerary.objects.create(
        followed_circuit=circuit,
        status=ItineraryStatus.objects.get(code="planificado"),
        title="Sigue",
        user=ana,
    )

    response = client.post(
        "/service-request/",
        {
            "date": days(5).isoformat(),
            "itinerary_id": str(following.pk),
            "start_time": "09:00",
        },
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


########################################################################################
# Empezar, terminar, chat y reseñas


def delivered_booking(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> dict:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)
    GuidedDeparture.objects.filter(pk=departure["id"]).update(date=localdate())
    Booking.objects.filter(pk=booking["id"]).update(
        date=localdate(), start_time=time(0)
    )

    started = client.post(f"/booking/{booking['id']}/start/", {}, headers=guide)
    finished = client.post(f"/booking/{booking['id']}/finish/", {}, headers=guide)

    assert body(started)["status"] == "in_progress", started.content
    assert body(finished)["status"] == "delivered", finished.content

    return booking


def test_the_tourist_does_not_start_the_tour(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)

    response = client.post(f"/booking/{booking['id']}/start/", {}, headers=headers)

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_tourist_and_the_guide_chat(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)
    path = f"/booking/{booking['id']}/message/"

    first = client.post(path, {"body": "¿Dónde nos vemos?"}, headers=headers)
    client.post(path, {"body": "Frente a la catedral."}, headers=guide)

    unread = body(client.get(f"/booking/{booking['id']}/", headers=headers))
    after = body(client.get(path, {"after": body(first)["sent_at"]}, headers=headers))
    client.post(f"{path}read/", {}, headers=headers)
    read = body(client.get(f"/booking/{booking['id']}/", headers=headers))

    assert first.status_code == HTTPStatus.CREATED, first.content
    assert unread["unread_messages"] == 1
    assert [item["body"] for item in after] == ["Frente a la catedral."]
    assert after[0]["mine"] is False
    assert read["unread_messages"] == 0


def test_the_reviews_feed_the_guide_and_the_circuit(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    guide_user: ApiUser,
    headers: dict[str, str],
) -> None:
    booking = delivered_booking(client, circuit, guide, headers)
    path = f"/booking/{booking['id']}/review/"

    from_tourist = client.post(
        path, {"comment": "Excelente guía.", "rating": 5}, headers=headers
    )
    from_guide = client.post(path, {"rating": 4}, headers=guide)
    twice = client.post(path, {"rating": 1}, headers=headers)

    assert from_tourist.status_code == HTTPStatus.CREATED, from_tourist.content
    assert from_guide.status_code == HTTPStatus.CREATED
    assert twice.status_code == HTTPStatus.CONFLICT

    provider = ProviderProfile.objects.get(user=guide_user)
    profile = body(client.get(f"/guide/{provider.pk}/"))
    assert profile["rating"] == 5
    assert profile["reviews"][0]["comment"] == "Excelente guía."
    assert profile["reviews"][0]["id"] == body(from_tourist)["id"]
    assert body(client.get(f"/circuit/{circuit.pk}/"))["reviews_count"] == 1


def test_a_review_waits_for_the_end_of_the_tour(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    departure = publish_departure(client, guide, circuit)
    booking = book(client, headers, departure)

    response = client.post(
        f"/booking/{booking['id']}/review/", {"rating": 5}, headers=headers
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_the_team_hides_an_unfair_review(
    client: DMRClient,
    circuit: Circuit,
    guide: dict[str, str],
    guide_user: ApiUser,
    headers: dict[str, str],
    make_member: Callable[..., ApiUser],
) -> None:
    booking = delivered_booking(client, circuit, guide, headers)
    review = body(
        client.post(
            f"/booking/{booking['id']}/review/",
            {"comment": "Insultos.", "rating": 1},
            headers=headers,
        )
    )

    dispute = client.post(
        f"/review/{review['id']}/dispute/",
        {"reason": "La reseña tiene insultos y es falsa."},
        headers=guide,
    )
    team = signed_in(make_member("equipo@example.com", "content.moderate"))
    queue = body(team.get("/review-dispute/", {"status": "pending"}))
    resolved = team.post(
        f"/review-dispute/{body(dispute)['id']}/resolve/",
        {"note": "Viola las normas.", "upheld": True},
    )

    assert dispute.status_code == HTTPStatus.CREATED, dispute.content
    assert queue["elements"] == 1
    assert body(resolved)["status"] == "upheld"
    provider = ProviderProfile.objects.get(user=guide_user)
    assert body(client.get(f"/guide/{provider.pk}/"))["reviews"] == []
    assert body(client.get(f"/guide/{provider.pk}/"))["rating"] is None
