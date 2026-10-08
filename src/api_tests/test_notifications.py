from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from api_notifications import push
from api_notifications.models import DeviceToken, Notification
from api_notifications.services import notify
from api_territory.models import Circuit
from api_tests.helpers import body
from api_tests.services_helpers import book, make_guide, publish_departure
from api_tests.territory_helpers import (
    make_circuit,
    make_point,
    mobile_headers,
    tourist,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient
    from pytest_django import DjangoCaptureOnCommitCallbacks

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db

TOKEN = "token-de-firebase-1234567890"


@pytest.fixture
def ana(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user(email="turista@example.com", first_name="Ana")


@pytest.fixture
def headers(ana: ApiUser) -> dict[str, str]:
    return tourist(ana)


########################################################################################
# La bandeja


def test_a_chat_message_reaches_the_inbox_of_the_other(
    client: DMRClient,
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
) -> None:
    guide_user = make_user(email="guia@example.com", first_name="Pedro")
    make_guide(guide_user)
    guide = mobile_headers(guide_user)
    circuit = make_circuit([make_point(name="Uno"), make_point(name="Dos")])
    Circuit.objects.filter(pk=circuit.pk).update(price_adult=0)
    booking = book(client, headers, publish_departure(client, guide, circuit))

    client.post(
        f"/booking/{booking['id']}/message/", {"body": "¡Hola!"}, headers=headers
    )
    inbox = body(client.get("/notification/", {"unread": True}, headers=guide))

    kinds = [item["kind"] for item in inbox["results"]]
    assert "mensaje" in kinds
    assert "reserva" in kinds
    message = next(item for item in inbox["results"] if item["kind"] == "mensaje")
    assert message["title"] == "Ana"
    assert message["data"]["booking_id"] == booking["id"]


def test_reading_one_and_reading_all(
    ana: ApiUser,
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    for index in range(3):
        notify(ana.pk, "cuenta", f"Aviso {index}", "Algo pasó.")

    first = body(client.get("/notification/", headers=headers))["results"][0]
    read = client.post(f"/notification/{first['id']}/read/", {}, headers=headers)
    after_one = body(client.get("/notification/", {"unread": True}, headers=headers))
    client.post("/notification/read-all/", {}, headers=headers)
    after_all = body(client.get("/notification/", {"unread": True}, headers=headers))

    assert body(read)["read"] is True
    assert after_one["elements"] == 2
    assert after_all["elements"] == 0


def test_the_bell_counts_the_unread(
    ana: ApiUser,
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    for index in range(2):
        notify(ana.pk, "cuenta", f"Aviso {index}", "Algo pasó.")

    before = body(client.get("/notification/unread/", headers=headers))
    client.post("/notification/read-all/", {}, headers=headers)
    after = body(client.get("/notification/unread/", headers=headers))

    assert (before, after) == ({"count": 2}, {"count": 0})


def test_an_inbox_of_someone_else_does_not_exist(
    ana: ApiUser,
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    notify(ana.pk, "cuenta", "Privado", "Solo para Ana.")
    other = tourist(make_user(email="otra@example.com"))
    notification = Notification.objects.get(user=ana)

    listed = body(client.get("/notification/", headers=other))
    read = client.post(f"/notification/{notification.pk}/read/", {}, headers=other)

    assert listed["elements"] == 0
    assert read.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Preferencias y teléfonos


def test_the_preferences_turn_off_a_kind_of_push(
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    response = client.put(
        "/notification-preference/",
        {"preferences": [{"kind": "mensaje", "push_enabled": False}]},
        headers=headers,
    )

    by_kind = {item["kind"]: item["push_enabled"] for item in body(response)}
    assert by_kind["mensaje"] is False
    assert by_kind["reserva"] is True


def test_a_phone_is_registered_and_removed(
    ana: ApiUser,
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    registered = client.post(
        "/device-token/", {"platform": "android", "token": TOKEN}, headers=headers
    )
    removed = client.post("/device-token/remove/", {"token": TOKEN}, headers=headers)

    assert registered.status_code == HTTPStatus.NO_CONTENT
    assert removed.status_code == HTTPStatus.NO_CONTENT
    assert not DeviceToken.objects.filter(user=ana).exists()


########################################################################################
# Firebase


def test_with_firebase_the_notice_goes_to_the_phone(
    ana: ApiUser,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str]] = []

    def send(token: str, title: str, *_: object) -> bool:
        sent.append((token, title))

        return True

    DeviceToken.objects.create(platform="android", token=TOKEN, user=ana)
    monkeypatch.setattr(push, "enabled", lambda: True)
    monkeypatch.setattr(push, "send", send)

    with django_capture_on_commit_callbacks(execute=True):
        notify(ana.pk, "pago", "Pago confirmado", "Listo.")

    assert sent == [(TOKEN, "Pago confirmado")]
    assert Notification.objects.get(user=ana).push_status == "enviado"


def test_a_dead_phone_is_forgotten(
    ana: ApiUser,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    DeviceToken.objects.create(platform="android", token=TOKEN, user=ana)
    monkeypatch.setattr(push, "enabled", lambda: True)
    monkeypatch.setattr(push, "send", lambda *_: False)

    with django_capture_on_commit_callbacks(execute=True):
        notify(ana.pk, "pago", "Pago confirmado", "Listo.")

    assert not DeviceToken.objects.filter(token=TOKEN).exists()


def test_without_firebase_the_notice_stays_in_the_inbox(ana: ApiUser) -> None:
    notify(ana.pk, "pago", "Pago confirmado", "Listo.")

    assert Notification.objects.get(user=ana).push_status == "omitido"
