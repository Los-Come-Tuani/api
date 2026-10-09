from http import HTTPStatus
from time import sleep
from typing import TYPE_CHECKING

import pytest

from django.core import mail

from api_auth.enums import ApiUserStatus
from api_auth.models import ApiUser
from api_auth.services.account import change_status_sync
from api_core.config import CONFIG
from api_tests.helpers import PASSWORD, bearer, body, credentials, extract_code

if TYPE_CHECKING:
    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Otra-Clave-2026"

########################################################################################


def ask_for_a_reset_code(client: DMRClient, user: ApiUser) -> str:
    response = client.post("/auth/password-forgot/", {"email": user.email})

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content
    assert len(mail.outbox) == 1

    return extract_code(mail.outbox[0])


def reset(client: DMRClient, user: ApiUser, code: str, password: str) -> object:
    return client.post(
        "/auth/password-reset/",
        {"code": code, "email": user.email, "password": password},
    )


########################################################################################


def test_forgot_password_emails_a_code_to_an_existing_account(
    client: DMRClient,
    user: ApiUser,
) -> None:
    ask_for_a_reset_code(client, user)

    assert mail.outbox[0].to == [user.email]


def test_forgot_password_is_silent_about_unknown_accounts(client: DMRClient) -> None:
    response = client.post("/auth/password-forgot/", {"email": "nadie@example.com"})

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert mail.outbox == []


@pytest.mark.parametrize("status", ["closing", "expelled", "pending", "suspended"])
def test_an_account_that_cannot_operate_cannot_recover_its_password(
    client: DMRClient,
    make_user: object,
    status: str,
) -> None:
    blocked = make_user(email="bloqueada@example.com", status=status)  # ty: ignore[call-non-callable]

    response = client.post("/auth/password-forgot/", {"email": blocked.email})

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert mail.outbox == []


def test_resetting_changes_the_password_and_closes_every_session(
    client: DMRClient,
    user: ApiUser,
) -> None:
    session = body(client.post("/auth/mobile/login/", credentials(user)))
    code = ask_for_a_reset_code(client, user)

    response = reset(client, user, code, NEW_PASSWORD)
    assert response.status_code == HTTPStatus.NO_CONTENT, response.content  # ty: ignore[unresolved-attribute]

    # la sesión que ya estaba abierta quedó cerrada
    assert client.get(
        "/auth/profile/",
        headers=bearer(session["access"]),
    ).status_code == (HTTPStatus.UNAUTHORIZED)

    # la contraseña vieja ya no entra y la nueva sí
    old = client.post("/auth/mobile/login/", credentials(user))
    assert old.status_code == HTTPStatus.UNAUTHORIZED

    sleep(1.1)  # el `iat` de las credenciales llega al segundo
    new = client.post("/auth/mobile/login/", credentials(user, NEW_PASSWORD))
    assert new.status_code == HTTPStatus.OK, new.content


def test_a_code_resets_only_once(client: DMRClient, user: ApiUser) -> None:
    code = ask_for_a_reset_code(client, user)

    first = reset(client, user, code, NEW_PASSWORD)
    second = reset(client, user, code, "Tercera-Clave-2026")

    assert first.status_code == HTTPStatus.NO_CONTENT  # ty: ignore[unresolved-attribute]
    assert second.status_code == HTTPStatus.BAD_REQUEST  # ty: ignore[unresolved-attribute]


def test_a_wrong_reset_code_is_rejected_and_five_of_them_burn_the_real_one(
    client: DMRClient,
    user: ApiUser,
) -> None:
    code = ask_for_a_reset_code(client, user)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        response = reset(client, user, wrong, NEW_PASSWORD)
        assert response.status_code == HTTPStatus.BAD_REQUEST  # ty: ignore[unresolved-attribute]

    assert reset(client, user, code, NEW_PASSWORD).status_code == (  # ty: ignore[unresolved-attribute]
        HTTPStatus.BAD_REQUEST
    )


def test_a_test_api_that_takes_any_signup_code_still_checks_reset_codes(
    client: DMRClient,
    user: ApiUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        CONFIG.__dict__,
        "VERIFICATION_ACCEPT_ANY_SIGNUP_CODE",
        value=True,
    )
    code = ask_for_a_reset_code(client, user)
    wrong = "000000" if code != "000000" else "111111"

    response = reset(client, user, wrong, NEW_PASSWORD)

    assert response.status_code == HTTPStatus.BAD_REQUEST  # ty: ignore[unresolved-attribute]


def test_a_weak_new_password_does_not_spend_the_code(
    client: DMRClient,
    user: ApiUser,
) -> None:
    code = ask_for_a_reset_code(client, user)

    weak = reset(client, user, code, "sinnumero")
    assert weak.status_code == HTTPStatus.BAD_REQUEST  # ty: ignore[unresolved-attribute]

    retry = reset(client, user, code, NEW_PASSWORD)
    assert retry.status_code == HTTPStatus.NO_CONTENT, retry.content  # ty: ignore[unresolved-attribute]


def test_resetting_an_unknown_account_looks_like_a_wrong_code(
    client: DMRClient,
) -> None:
    response = client.post(
        "/auth/password-reset/",
        {"code": "123456", "email": "nadie@example.com", "password": NEW_PASSWORD},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_reset_code_does_not_work_after_the_account_is_suspended(
    client: DMRClient,
    user: ApiUser,
) -> None:
    code = ask_for_a_reset_code(client, user)
    change_status_sync(user, ApiUserStatus.SUSPENDED)

    assert reset(client, user, code, NEW_PASSWORD).status_code == (  # ty: ignore[unresolved-attribute]
        HTTPStatus.BAD_REQUEST
    )


########################################################################################


def test_changing_the_password_needs_the_current_one(
    client: DMRClient,
    user: ApiUser,
) -> None:
    session = body(client.post("/auth/mobile/login/", credentials(user)))

    response = client.post(
        "/auth/password-change/",
        {"current_password": "incorrecta", "password": NEW_PASSWORD},
        headers=bearer(session["access"]),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.current_password" in body(response)["field_errors"]
    assert ApiUser.objects.get(pk=user.pk).check_password(PASSWORD)


def test_changing_the_password_closes_the_sessions(
    client: DMRClient,
    user: ApiUser,
) -> None:
    session = body(client.post("/auth/mobile/login/", credentials(user)))

    response = client.post(
        "/auth/password-change/",
        {"current_password": PASSWORD, "password": NEW_PASSWORD},
        headers=bearer(session["access"]),
    )
    assert response.status_code == HTTPStatus.NO_CONTENT, response.content

    assert client.get(
        "/auth/profile/",
        headers=bearer(session["access"]),
    ).status_code == (HTTPStatus.UNAUTHORIZED)

    sleep(1.1)
    assert client.post(
        "/auth/mobile/login/",
        credentials(user, NEW_PASSWORD),
    ).status_code == (HTTPStatus.OK)


def test_changing_to_a_weak_password_is_rejected(
    client: DMRClient,
    user: ApiUser,
) -> None:
    session = body(client.post("/auth/mobile/login/", credentials(user)))

    response = client.post(
        "/auth/password-change/",
        {"current_password": PASSWORD, "password": "corta"},
        headers=bearer(session["access"]),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.password" in body(response)["field_errors"]


def test_changing_the_password_requires_a_session(client: DMRClient) -> None:
    response = client.post(
        "/auth/password-change/",
        {"current_password": PASSWORD, "password": NEW_PASSWORD},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
