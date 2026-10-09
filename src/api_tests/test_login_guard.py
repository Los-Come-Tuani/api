from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.core.cache import cache
from django.db.models import F
from django.utils.timezone import now
from pgtrigger import ignore

from api_auth.models import ApiLoginAttempt, ApiLoginLock
from api_core.config import CONFIG
from api_tests.helpers import PASSWORD, body, credentials

if TYPE_CHECKING:
    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db

########################################################################################


def fail(client: DMRClient, email: str, times: int) -> None:
    for _ in range(times):
        response = client.post(
            "/auth/mobile/login/",
            {"email": email, "password": "incorrecta"},
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED, response.content


########################################################################################


def test_five_failures_in_a_row_lock_the_account_even_for_the_right_password(
    client: DMRClient,
    user: ApiUser,
) -> None:
    assert CONFIG.LOGIN_MAX_FAILURES == 5

    fail(client, str(user.email), 5)

    locked = client.post("/auth/mobile/login/", credentials(user))

    assert locked.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert int(locked.headers["Retry-After"]) > 0
    assert int(locked.headers["Retry-After"]) <= CONFIG.LOGIN_LOCKOUT.total_seconds()


def test_four_failures_do_not_lock(client: DMRClient, user: ApiUser) -> None:
    fail(client, str(user.email), 4)

    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_a_success_resets_the_count(client: DMRClient, user: ApiUser) -> None:
    fail(client, str(user.email), 4)
    client.post("/auth/mobile/login/", credentials(user))

    # tras el acierto, cuatro fallos más siguen sin bloquear
    fail(client, str(user.email), 4)

    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_an_unknown_email_is_locked_too_so_the_lock_reveals_nothing(
    client: DMRClient,
    user: ApiUser,
) -> None:
    fail(client, "nadie@example.com", 5)
    unknown = client.post(
        "/auth/mobile/login/",
        {"email": "nadie@example.com", "password": PASSWORD},
    )

    # el límite por dirección IP (10 por minuto) es otro mecanismo; se reinicia
    # para que no se confunda con el bloqueo por identificador
    cache.clear()

    fail(client, str(user.email), 5)
    known = client.post("/auth/mobile/login/", credentials(user))

    assert unknown.status_code == known.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert body(unknown) == body(known)


def test_the_lock_is_per_identifier(client: DMRClient, user: ApiUser) -> None:
    fail(client, "otra@example.com", 5)

    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_the_lock_counts_the_email_however_it_was_typed(
    client: DMRClient,
    user: ApiUser,
) -> None:
    for typed in (str(user.email).upper(), f" {user.email} ", user.email) * 2:
        client.post("/auth/mobile/login/", {"email": typed, "password": "incorrecta"})

    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.TOO_MANY_REQUESTS
    )


def test_the_lock_expires(client: DMRClient, user: ApiUser) -> None:
    fail(client, str(user.email), 5)
    ApiLoginLock.objects.update(locked_until=now() - timedelta(seconds=1))

    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_after_a_lock_expires_the_count_starts_again(
    client: DMRClient,
    user: ApiUser,
) -> None:
    fail(client, str(user.email), 5)

    # pasan veinte minutos: el bloqueo venció y los intentos quedaron atrás
    with ignore("apiauth.ApiLoginAttempt:trg_apiloginattempt_noupdate"):
        ApiLoginAttempt.objects.update(
            created_at=F("created_at") - timedelta(minutes=20),
        )
    ApiLoginLock.objects.update(locked_until=now() - timedelta(minutes=5))

    # un solo fallo nuevo no vuelve a bloquear: los cinco anteriores ya cumplieron
    fail(client, str(user.email), 1)

    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_every_attempt_is_recorded_with_the_identifier_as_typed(
    client: DMRClient,
    user: ApiUser,
) -> None:
    client.post(
        "/auth/mobile/login/",
        {"email": " Ana@Example.COM ", "password": "incorrecta"},
    )
    client.post("/auth/mobile/login/", credentials(user))

    failed, succeeded = ApiLoginAttempt.objects.order_by("created_at")

    # se guarda como se tecleó (salvo los espacios de los extremos, que el DTO quita)
    assert (failed.identifier, failed.key, failed.succeeded) == (
        "Ana@Example.COM",
        "ana@example.com",
        False,
    )
    assert succeeded.succeeded
    assert succeeded.ip_address == "127.0.0.1"


def test_attempts_cannot_be_rewritten(client: DMRClient, user: ApiUser) -> None:
    client.post("/auth/mobile/login/", credentials(user))

    with pytest.raises(Exception, match="update"):
        ApiLoginAttempt.objects.update(succeeded=False)
