from datetime import timedelta
from http import HTTPStatus
from time import sleep
from typing import TYPE_CHECKING

import pytest

from django.core import mail
from django.utils.timezone import now

from api_auth.models import ApiUser
from api_core.config import CONFIG
from api_tests.helpers import PASSWORD, bearer, body, credentials

if TYPE_CHECKING:
    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

########################################################################################


def close(client: DMRClient, user: ApiUser, password: str = PASSWORD) -> tuple:
    session = body(client.post("/auth/mobile/login/", credentials(user)))

    response = client.post(
        "/auth/account-close/",
        {"password": password},
        headers=bearer(session["access"]),
    )

    return session, response


########################################################################################


def test_closing_needs_the_current_password(client: DMRClient, user: ApiUser) -> None:
    _, response = close(client, user, "incorrecta")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert ApiUser.objects.get(pk=user.pk).status == "active"
    assert mail.outbox == []


def test_closing_leaves_the_account_inactive_for_thirty_days(
    client: DMRClient,
    user: ApiUser,
) -> None:
    session, response = close(client, user)

    assert response.status_code == HTTPStatus.OK, response.content

    stored = ApiUser.objects.get(pk=user.pk)
    assert stored.status == "closing"
    assert not stored.is_active
    assert stored.closing_effective_at is not None
    assert abs(
        stored.closing_effective_at - (now() + CONFIG.ACCOUNT_CLOSING_DELAY),
    ) < timedelta(minutes=1)
    assert timedelta(days=30) == CONFIG.ACCOUNT_CLOSING_DELAY

    # la respuesta dice cuándo se destruyen los datos, y llega un correo de aviso
    assert body(response)["effective_at"]
    assert mail.outbox[0].to == [user.email]

    # la sesión desde la que se pidió la baja ya no sirve, ni se puede volver a entrar
    assert client.get(
        "/auth/profile/",
        headers=bearer(session["access"]),
    ).status_code == (HTTPStatus.UNAUTHORIZED)
    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.FORBIDDEN
    )


def test_restoring_inside_the_period_reactivates_the_account(
    client: DMRClient,
    user: ApiUser,
) -> None:
    close(client, user)

    response = client.post(
        "/auth/account-restore/",
        {"email": user.email, "password": PASSWORD},
    )
    assert response.status_code == HTTPStatus.NO_CONTENT, response.content

    stored = ApiUser.objects.get(pk=user.pk)
    assert stored.status == "active"
    assert stored.is_active
    assert stored.closing_effective_at is None

    sleep(1.1)  # el `iat` de las credenciales llega al segundo
    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_restoring_needs_the_right_password(client: DMRClient, user: ApiUser) -> None:
    close(client, user)

    response = client.post(
        "/auth/account-restore/",
        {"email": user.email, "password": "incorrecta"},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert ApiUser.objects.get(pk=user.pk).status == "closing"


def test_restoring_after_the_period_is_refused(
    client: DMRClient,
    user: ApiUser,
) -> None:
    close(client, user)
    ApiUser.objects.filter(pk=user.pk).update(
        closing_effective_at=now() - timedelta(days=1),
    )

    response = client.post(
        "/auth/account-restore/",
        {"email": user.email, "password": PASSWORD},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_restoring_an_account_that_is_not_closing_looks_like_bad_credentials(
    client: DMRClient,
    user: ApiUser,
) -> None:
    response = client.post(
        "/auth/account-restore/",
        {"email": user.email, "password": PASSWORD},
    )
    unknown = client.post(
        "/auth/account-restore/",
        {"email": "nadie@example.com", "password": PASSWORD},
    )

    assert response.status_code == unknown.status_code == HTTPStatus.UNAUTHORIZED
    assert body(response) == body(unknown)
