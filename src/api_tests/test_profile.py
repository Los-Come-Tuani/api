from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from api_auth.models import ApiUser
from api_tests.helpers import bearer, body, credentials

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

########################################################################################


def access_for(client: DMRClient, user: ApiUser) -> dict[str, str]:
    session = body(client.post("/auth/mobile/login/", credentials(user)))

    return bearer(session["access"])


########################################################################################


def test_patch_updates_only_the_fields_that_come(
    client: DMRClient,
    user: ApiUser,
) -> None:
    response = client.patch(
        "/auth/profile/",
        {"first_name": "Ana", "last_name": "Gómez", "nationality": "ni"},
        headers=access_for(client, user),
    )

    assert response.status_code == HTTPStatus.OK, response.content
    data = body(response)
    assert data["first_name"] == "Ana"
    assert data["last_name"] == "Gómez"
    assert data["name"] == "Ana Gómez"
    assert data["nationality"] == "NI"
    assert data["email"] == user.email


def test_patch_with_no_fields_changes_nothing(
    client: DMRClient,
    user: ApiUser,
) -> None:
    response = client.patch("/auth/profile/", {}, headers=access_for(client, user))

    assert response.status_code == HTTPStatus.OK
    assert body(response)["email"] == user.email


def test_the_email_cannot_be_changed_from_the_profile(
    client: DMRClient,
    user: ApiUser,
) -> None:
    response = client.patch(
        "/auth/profile/",
        {"email": "otro@example.com"},
        headers=access_for(client, user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert ApiUser.objects.get(pk=user.pk).email == user.email


@pytest.mark.parametrize(
    "extra",
    [{"status": "active"}, {"is_staff": True}, {"birth_date": "1990-01-01"}],
)
def test_privileged_fields_cannot_be_patched(
    client: DMRClient,
    extra: dict,
    user: ApiUser,
) -> None:
    response = client.patch(
        "/auth/profile/",
        extra,
        headers=access_for(client, user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_the_username_can_be_set_and_cleared(
    client: DMRClient,
    user: ApiUser,
) -> None:
    headers = access_for(client, user)

    set_it = client.patch("/auth/profile/", {"username": "ana.g"}, headers=headers)
    assert body(set_it)["username"] == "ana.g"

    clear = client.patch("/auth/profile/", {"username": None}, headers=headers)
    assert clear.status_code == HTTPStatus.OK, clear.content
    assert body(clear)["username"] is None


def test_a_taken_username_is_a_conflict(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
    user: ApiUser,
) -> None:
    make_user(email="otra@example.com", username="ocupado")

    response = client.patch(
        "/auth/profile/",
        {"username": "ocupado"},
        headers=access_for(client, user),
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_an_invalid_nationality_is_rejected(client: DMRClient, user: ApiUser) -> None:
    response = client.patch(
        "/auth/profile/",
        {"nationality": "Nicaragua"},
        headers=access_for(client, user),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
