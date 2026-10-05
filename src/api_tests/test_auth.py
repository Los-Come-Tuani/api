from datetime import timedelta
from http import HTTPStatus
from time import sleep
from typing import TYPE_CHECKING

import pytest

from asgiref.sync import async_to_sync
from django.utils.timezone import now
from dmr.test import DMRAsyncRequestFactory, assert_async_throttling
from dmr.throttling import Rate

from api_auth.controllers.login import MobileLoginController
from api_auth.enums import ApiUserStatus
from api_auth.models import ApiUser
from api_auth.services.account import change_status_sync
from api_tests.helpers import PASSWORD, bearer, body, credentials

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

########################################################################################


def mobile_login(client: DMRClient, user: ApiUser) -> dict:
    response = client.post("/auth/mobile/login/", credentials(user))

    assert response.status_code == HTTPStatus.OK, response.content

    return body(response)


########################################################################################


def test_mobile_login_returns_a_token_pair_and_the_session_user(
    client: DMRClient,
    user: ApiUser,
) -> None:
    data = mobile_login(client, user)

    assert data["access"]
    assert data["refresh"]
    assert data["user"]["email"] == user.email
    assert data["user"]["status"] == "active"
    assert data["user"]["two_factor"] == {"enabled": False, "required": False}


def test_login_ignores_case_and_surrounding_spaces_in_the_email(
    client: DMRClient,
    user: ApiUser,
) -> None:
    response = client.post(
        "/auth/mobile/login/",
        {"email": f"  {str(user.email).upper()} ", "password": PASSWORD},
    )

    assert response.status_code == HTTPStatus.OK, response.content


def test_the_username_is_not_a_login_identifier(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(username="ana")

    response = client.post(
        "/auth/mobile/login/",
        {"password": PASSWORD, "username": "ana"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize("password", ["incorrecta", "x"])
def test_login_rejects_a_wrong_password(
    client: DMRClient,
    password: str,
    user: ApiUser,
) -> None:
    response = client.post("/auth/mobile/login/", credentials(user, password))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_login_rejects_an_unknown_email_like_a_wrong_password(
    client: DMRClient,
    user: ApiUser,
) -> None:
    unknown = client.post(
        "/auth/mobile/login/",
        {"email": "nadie@example.com", "password": PASSWORD},
    )
    wrong = client.post("/auth/mobile/login/", credentials(user, "incorrecta"))

    # el mensaje no distingue entre cuenta inexistente y contraseña incorrecta
    assert unknown.status_code == wrong.status_code == HTTPStatus.UNAUTHORIZED
    assert body(unknown) == body(wrong)


@pytest.mark.parametrize(
    "status",
    ["closing", "expelled", "pending", "suspended"],
)
def test_an_account_that_cannot_operate_is_told_why_only_with_the_right_password(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
    status: str,
) -> None:
    blocked = make_user(email="baja@example.com", status=status)

    right = client.post("/auth/mobile/login/", credentials(blocked))
    wrong = client.post("/auth/mobile/login/", credentials(blocked, "incorrecta"))

    assert right.status_code == HTTPStatus.FORBIDDEN
    assert body(right)["detail"]
    # a quien tantea se le responde igual que si la cuenta no existiera
    assert wrong.status_code == HTTPStatus.UNAUTHORIZED


def test_login_is_throttled(user: ApiUser) -> None:
    factory = DMRAsyncRequestFactory()

    async_to_sync(assert_async_throttling)(
        MobileLoginController,
        lambda: factory.post("/auth/mobile/login/", credentials(user)),
        max_requests=2,
        rate=Rate.hour,
        success_status=HTTPStatus.OK,
    )


########################################################################################


def test_profile_requires_a_token(client: DMRClient) -> None:
    assert client.get("/auth/profile/").status_code == HTTPStatus.UNAUTHORIZED


def test_profile_returns_the_session_user(client: DMRClient, user: ApiUser) -> None:
    tokens = mobile_login(client, user)

    response = client.get("/auth/profile/", headers=bearer(tokens["access"]))

    assert response.status_code == HTTPStatus.OK, response.content
    data = body(response)
    assert data["email"] == user.email
    assert data["name"] == "ana"
    assert data["verified"] is True
    assert data["permissions"] == []


def test_a_refresh_token_is_not_accepted_as_an_access_token(
    client: DMRClient,
    user: ApiUser,
) -> None:
    tokens = mobile_login(client, user)

    response = client.get("/auth/profile/", headers=bearer(tokens["refresh"]))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


########################################################################################


def test_refresh_rotates_the_pair_and_refuses_to_reuse_the_old_one(
    client: DMRClient,
    user: ApiUser,
) -> None:
    tokens = mobile_login(client, user)

    rotated = client.post(
        "/auth/mobile/refresh/",
        {"access": tokens["access"], "refresh": tokens["refresh"]},
    )

    assert rotated.status_code == HTTPStatus.OK, rotated.content
    fresh = body(rotated)
    assert fresh["refresh"] != tokens["refresh"]

    # la credencial de renovación es de un solo uso
    reused = client.post("/auth/mobile/refresh/", {"refresh": tokens["refresh"]})
    assert reused.status_code == HTTPStatus.UNAUTHORIZED

    # el acceso anterior quedó revocado y el nuevo sirve
    old = client.get("/auth/profile/", headers=bearer(tokens["access"]))
    new = client.get("/auth/profile/", headers=bearer(fresh["access"]))
    assert old.status_code == HTTPStatus.UNAUTHORIZED
    assert new.status_code == HTTPStatus.OK


def test_logout_revokes_the_whole_session(client: DMRClient, user: ApiUser) -> None:
    tokens = mobile_login(client, user)

    response = client.post(
        "/auth/mobile/logout/",
        {"access": tokens["access"], "refresh": tokens["refresh"]},
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    profile = client.get("/auth/profile/", headers=bearer(tokens["access"]))
    refresh = client.post("/auth/mobile/refresh/", {"refresh": tokens["refresh"]})
    assert profile.status_code == HTTPStatus.UNAUTHORIZED
    assert refresh.status_code == HTTPStatus.UNAUTHORIZED


def test_verify_tells_whether_a_token_is_still_active(
    client: DMRClient,
    user: ApiUser,
) -> None:
    tokens = mobile_login(client, user)
    payload = {"token": tokens["access"], "type": "access"}

    assert client.post("/auth/mobile/verify/", payload).status_code == (
        HTTPStatus.NO_CONTENT
    )

    client.post("/auth/mobile/logout/", {"access": tokens["access"]})

    assert client.post("/auth/mobile/verify/", payload).status_code == (
        HTTPStatus.UNAUTHORIZED
    )


########################################################################################


def test_revoking_all_sessions_cuts_every_credential_issued_before(
    client: DMRClient,
    user: ApiUser,
) -> None:
    phone = mobile_login(client, user)
    tablet = mobile_login(client, user)

    response = client.post(
        "/auth/session-revoke/",
        headers=bearer(phone["access"]),
    )
    assert response.status_code == HTTPStatus.NO_CONTENT

    # ninguna de las dos sesiones sirve, ni para operar ni para renovarse
    for tokens in (phone, tablet):
        profile = client.get("/auth/profile/", headers=bearer(tokens["access"]))
        refresh = client.post("/auth/mobile/refresh/", {"refresh": tokens["refresh"]})
        assert profile.status_code == HTTPStatus.UNAUTHORIZED
        assert refresh.status_code == HTTPStatus.UNAUTHORIZED

    # el `iat` de las credenciales llega al segundo: una nueva, pasado ese tiempo, sirve
    sleep(1.1)
    fresh = mobile_login(client, user)
    assert client.get(
        "/auth/profile/",
        headers=bearer(fresh["access"]),
    ).status_code == (HTTPStatus.OK)


def test_a_suspension_cuts_the_open_sessions_immediately(
    client: DMRClient,
    user: ApiUser,
) -> None:
    tokens = mobile_login(client, user)

    change_status_sync(user, ApiUserStatus.SUSPENDED)

    assert client.get(
        "/auth/profile/",
        headers=bearer(tokens["access"]),
    ).status_code == (HTTPStatus.UNAUTHORIZED)
    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.FORBIDDEN
    )


########################################################################################


def csrf_headers(client: DMRClient) -> dict[str, str]:
    response = client.get("/auth/csrf/")

    assert response.status_code == HTTPStatus.NO_CONTENT

    return {"X-CSRFToken": response.headers["x-csrftoken"]}


def test_web_login_sets_http_only_cookies_and_requires_csrf(
    csrf_client: DMRClient,
    user: ApiUser,
) -> None:
    # sin la cabecera CSRF, el navegador no puede iniciar sesión
    blocked = csrf_client.post("/auth/web/login/", credentials(user))
    assert blocked.status_code == HTTPStatus.FORBIDDEN

    response = csrf_client.post(
        "/auth/web/login/",
        credentials(user),
        headers=csrf_headers(csrf_client),
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["user"]["email"] == user.email
    assert "access" not in body(response)

    for name in ("access", "refresh"):
        assert response.cookies[name]["httponly"]


def test_web_session_works_with_cookies_until_logout(
    csrf_client: DMRClient,
    user: ApiUser,
) -> None:
    headers = csrf_headers(csrf_client)
    csrf_client.post("/auth/web/login/", credentials(user), headers=headers)

    assert csrf_client.get("/auth/profile/").status_code == HTTPStatus.OK

    logout = csrf_client.post("/auth/web/logout/", headers=headers)
    assert logout.status_code == HTTPStatus.NO_CONTENT, logout.content

    assert csrf_client.get("/auth/profile/").status_code == HTTPStatus.UNAUTHORIZED


def test_web_refresh_rotates_the_cookies(csrf_client: DMRClient, user: ApiUser) -> None:
    headers = csrf_headers(csrf_client)
    csrf_client.post("/auth/web/login/", credentials(user), headers=headers)
    before = csrf_client.cookies["refresh"].value

    response = csrf_client.post("/auth/web/refresh/", headers=headers)

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content
    assert csrf_client.cookies["refresh"].value != before
    assert csrf_client.get("/auth/profile/").status_code == HTTPStatus.OK


def test_a_web_refresh_after_a_suspension_is_refused(
    csrf_client: DMRClient,
    user: ApiUser,
) -> None:
    headers = csrf_headers(csrf_client)
    csrf_client.post("/auth/web/login/", credentials(user), headers=headers)

    ApiUser.objects.filter(pk=user.pk).update(
        sessions_revoked_at=now() + timedelta(seconds=5),
    )

    response = csrf_client.post("/auth/web/refresh/", headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
