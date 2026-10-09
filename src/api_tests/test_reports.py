from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.utils.timezone import now

from api_auth.enums import ApiUserStatus
from api_notifications.models import Notification
from api_reports.models import Sanction
from api_reports.services import expire_sanctions
from api_tests.helpers import body
from api_tests.territory_helpers import make_point, signed_in, tourist

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user(email="turista@example.com", first_name="Ana")


@pytest.fixture
def headers(ana: ApiUser) -> dict[str, str]:
    return tourist(ana)


@pytest.fixture
def troll(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user(email="troll@example.com", first_name="Troll")


########################################################################################
# Reportar


def test_a_tourist_reports_a_person_and_the_team_sees_it(
    client: DMRClient,
    headers: dict[str, str],
    make_member: Callable[..., ApiUser],
    troll: ApiUser,
) -> None:
    reasons = body(client.get("/report/reason/", headers=headers))
    sent = client.post(
        "/report/",
        {"reason": "acoso", "target_id": str(troll.pk), "target_kind": "user"},
        headers=headers,
    )
    team = signed_in(make_member("equipo@example.com", "content.moderate"))
    queue = body(team.get("/report/", {"status": "pending"}))

    assert "acoso" in {item["code"] for item in reasons}
    assert sent.status_code == HTTPStatus.NO_CONTENT, sent.content
    assert queue["results"][0]["target"] == {
        "id": str(troll.pk),
        "kind": "user",
        "label": "Troll",
    }
    assert queue["results"][0]["reporter"] == "Ana"


def test_a_place_can_be_reported_and_other_needs_a_note(
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    place = make_point()

    without = client.post(
        "/report/",
        {"reason": "otro", "target_id": str(place.pk), "target_kind": "place"},
        headers=headers,
    )
    with_note = client.post(
        "/report/",
        {
            "note": "Ese lugar cerró hace un año.",
            "reason": "otro",
            "target_id": str(place.pk),
            "target_kind": "place",
        },
        headers=headers,
    )

    assert without.status_code == HTTPStatus.BAD_REQUEST
    assert with_note.status_code == HTTPStatus.NO_CONTENT


def test_nobody_reports_themselves(
    ana: ApiUser,
    client: DMRClient,
    headers: dict[str, str],
) -> None:
    response = client.post(
        "/report/",
        {"reason": "acoso", "target_id": str(ana.pk), "target_kind": "user"},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_the_queue_is_for_the_team(client: DMRClient, headers: dict[str, str]) -> None:
    assert client.get("/report/", headers=headers).status_code == HTTPStatus.FORBIDDEN


def test_the_team_resolves_a_report(
    client: DMRClient,
    headers: dict[str, str],
    make_member: Callable[..., ApiUser],
    troll: ApiUser,
) -> None:
    client.post(
        "/report/",
        {"reason": "acoso", "target_id": str(troll.pk), "target_kind": "user"},
        headers=headers,
    )
    team = signed_in(make_member("equipo@example.com", "users.manage"))
    report = body(team.get("/report/"))["results"][0]

    resolved = team.post(
        f"/report/{report['id']}/resolve/",
        {"note": "No es acoso.", "status": "dismissed"},
    )
    again = team.post(f"/report/{report['id']}/resolve/", {"status": "handled"})

    assert body(resolved)["status"] == "dismissed"
    assert again.status_code == HTTPStatus.CONFLICT


########################################################################################
# Sanciones


def test_a_suspension_cuts_the_account_and_lifting_it_gives_it_back(
    make_member: Callable[..., ApiUser],
    troll: ApiUser,
) -> None:
    team = signed_in(make_member("equipo@example.com", "users.manage"))

    created = team.post(
        "/sanction/",
        {
            "days": 7,
            "kind": "suspension",
            "reason": "Acoso a un guía.",
            "user_id": str(troll.pk),
        },
    )
    troll.refresh_from_db()
    suspended = troll.status
    lifted = team.post(f"/sanction/{body(created)['id']}/lift/", {})
    troll.refresh_from_db()

    assert created.status_code == HTTPStatus.CREATED, created.content
    assert body(created)["active"] is True
    assert suspended == ApiUserStatus.SUSPENDED
    assert Notification.objects.filter(kind="cuenta", user=troll).exists()
    assert body(lifted)["active"] is False
    assert troll.status == ApiUserStatus.ACTIVE


def test_an_expulsion_closes_the_account(
    make_member: Callable[..., ApiUser],
    troll: ApiUser,
) -> None:
    team = signed_in(make_member("equipo@example.com", "users.manage"))

    team.post(
        "/sanction/",
        {"kind": "expulsion", "reason": "Fraude comprobado.", "user_id": str(troll.pk)},
    )
    troll.refresh_from_db()

    assert troll.status == ApiUserStatus.EXPELLED


def test_a_finished_suspension_lifts_itself(
    make_member: Callable[..., ApiUser],
    troll: ApiUser,
) -> None:
    team = signed_in(make_member("equipo@example.com", "users.manage"))
    created = body(
        team.post(
            "/sanction/",
            {
                "days": 1,
                "kind": "suspension",
                "reason": "Lenguaje ofensivo.",
                "user_id": str(troll.pk),
            },
        )
    )
    Sanction.objects.filter(pk=created["id"]).update(
        ends_at=now() - timedelta(minutes=1)
    )

    lifted = expire_sanctions()
    troll.refresh_from_db()

    assert lifted == 1
    assert troll.status == ApiUserStatus.ACTIVE


def test_only_users_manage_sanctions(
    make_member: Callable[..., ApiUser],
    troll: ApiUser,
) -> None:
    team = signed_in(make_member("equipo@example.com", "content.moderate"))

    response = team.post(
        "/sanction/",
        {"kind": "warning", "reason": "Por si acaso.", "user_id": str(troll.pk)},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
