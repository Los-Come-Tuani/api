from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.utils.timezone import now

from api_auth.models import ApiUserRecoveryCode, ApiUserTotpDevice
from api_auth.services import crypto, totp
from api_tests.helpers import PASSWORD, bearer, body, credentials

if TYPE_CHECKING:
    from dmr.test import DMRClient

    from api_auth.models import ApiUser
    from api_tests.conftest import Clock

########################################################################################

pytestmark = pytest.mark.django_db

########################################################################################


class Enrolled:
    """Un usuario con el 2FA confirmado, y lo necesario para hablar con el API."""

    def __init__(self, secret: str, recovery_codes: list[str], tokens: dict) -> None:
        self.secret: str = secret
        self.recovery_codes: list[str] = recovery_codes
        self.tokens: dict = tokens

    def headers(self) -> dict[str, str]:
        return bearer(self.tokens["access"])


def enroll(client: DMRClient, user: ApiUser, clock: Clock) -> Enrolled:
    login = client.post("/auth/mobile/login/", credentials(user))
    tokens = body(login)

    setup = client.post("/auth/two-factor-setup/", headers=bearer(tokens["access"]))
    assert setup.status_code == HTTPStatus.CREATED, setup.content
    secret = body(setup)["secret"]

    confirm = client.post(
        "/auth/two-factor-confirm/",
        {"code": totp.build_totp(secret, clock.step)},
        headers=bearer(tokens["access"]),
    )
    assert confirm.status_code == HTTPStatus.CREATED, confirm.content

    return Enrolled(secret, body(confirm)["codes"], tokens)


def challenge_for(client: DMRClient, user: ApiUser) -> str:
    response = client.post("/auth/mobile/login/", credentials(user))

    assert response.status_code == HTTPStatus.ACCEPTED, response.content

    return body(response)["challenge"]


########################################################################################


def test_status_before_enrolling(client: DMRClient, user: ApiUser) -> None:
    tokens = body(client.post("/auth/mobile/login/", credentials(user)))

    status = body(client.get("/auth/two-factor/", headers=bearer(tokens["access"])))

    assert status == {
        "confirmed_at": None,
        "enabled": False,
        "pending": False,
        "recovery_codes": 0,
    }


def test_setup_stores_the_secret_encrypted_and_hands_it_over_once(
    client: DMRClient,
    user: ApiUser,
) -> None:
    tokens = body(client.post("/auth/mobile/login/", credentials(user)))

    response = client.post(
        "/auth/two-factor-setup/",
        headers=bearer(tokens["access"]),
    )

    assert response.status_code == HTTPStatus.CREATED
    data = body(response)
    assert data["uri"].startswith("otpauth://totp/")
    assert data["secret"] in data["uri"]

    stored = ApiUserTotpDevice.objects.get(api_user=user).secret

    # lo que queda en la base es un token Fernet, nunca el secreto en claro
    assert stored != data["secret"]
    assert data["secret"] not in stored
    assert crypto.decrypt_secret(stored) == data["secret"]


def test_the_setup_requires_authentication(client: DMRClient) -> None:
    assert client.post("/auth/two-factor-setup/").status_code == (
        HTTPStatus.UNAUTHORIZED
    )


def test_confirming_with_a_wrong_code_does_not_enable_two_factor(
    client: DMRClient,
    user: ApiUser,
    clock: Clock,
) -> None:
    tokens = body(client.post("/auth/mobile/login/", credentials(user)))
    secret = body(
        client.post("/auth/two-factor-setup/", headers=bearer(tokens["access"])),
    )["secret"]

    wrong = totp.build_totp(secret, clock.step - 10)
    response = client.post(
        "/auth/two-factor-confirm/",
        {"code": wrong},
        headers=bearer(tokens["access"]),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert ApiUserTotpDevice.objects.get(api_user=user).confirmed_at is None


def test_enrolling_hands_out_ten_recovery_codes_hashed_in_the_database(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)

    assert len(enrolled.recovery_codes) == 10

    stored = set(ApiUserRecoveryCode.objects.values_list("code", flat=True))
    assert stored.isdisjoint(enrolled.recovery_codes)
    assert totp.hash_recovery_code(enrolled.recovery_codes[0]) in stored

    status = body(client.get("/auth/two-factor/", headers=enrolled.headers()))
    assert status["enabled"]
    assert status["recovery_codes"] == 10


def test_login_asks_for_a_code_once_two_factor_is_on(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enroll(client, user, clock)

    response = client.post("/auth/mobile/login/", credentials(user))

    assert response.status_code == HTTPStatus.ACCEPTED
    data = body(response)
    assert data["challenge"]
    assert "access" not in data


def test_the_challenge_plus_a_valid_code_opens_the_session(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    challenge = challenge_for(client, user)

    # el código con el que se confirmó ya se gastó: hace falta el del paso siguiente
    clock.advance()

    response = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge, "code": totp.build_totp(enrolled.secret, clock.step)},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    session = body(response)
    profile = client.get("/auth/profile/", headers=bearer(session["access"]))
    assert profile.status_code == HTTPStatus.OK


def test_a_used_code_cannot_be_replayed(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    clock.advance()
    code = totp.build_totp(enrolled.secret, clock.step)

    first = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge_for(client, user), "code": code},
    )
    replay = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge_for(client, user), "code": code},
    )

    assert first.status_code == HTTPStatus.OK
    assert replay.status_code == HTTPStatus.UNAUTHORIZED


def test_a_challenge_can_only_be_used_once(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    challenge = challenge_for(client, user)

    clock.advance()
    first = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge, "code": totp.build_totp(enrolled.secret, clock.step)},
    )

    clock.advance()
    second = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge, "code": totp.build_totp(enrolled.secret, clock.step)},
    )

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.UNAUTHORIZED


def test_a_challenge_is_not_an_access_token(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enroll(client, user, clock)
    challenge = challenge_for(client, user)

    response = client.get("/auth/profile/", headers=bearer(challenge))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_a_recovery_code_works_once(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    recovery = enrolled.recovery_codes[0]

    first = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge_for(client, user), "code": recovery},
    )
    again = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge_for(client, user), "code": recovery},
    )

    assert first.status_code == HTTPStatus.OK, first.content
    assert again.status_code == HTTPStatus.UNAUTHORIZED
    assert ApiUserRecoveryCode.objects.filter(used_at__isnull=False).count() == 1


def test_five_wrong_codes_lock_the_device_even_for_the_right_code(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    clock.advance()

    for _ in range(5):
        wrong = client.post(
            "/auth/mobile/two-factor/",
            {"challenge": challenge_for(client, user), "code": "000000"},
        )
        assert wrong.status_code == HTTPStatus.UNAUTHORIZED

    locked = client.post(
        "/auth/mobile/two-factor/",
        {
            "challenge": challenge_for(client, user),
            "code": totp.build_totp(enrolled.secret, clock.step),
        },
    )

    assert locked.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert ApiUserTotpDevice.objects.get(api_user=user).locked_until > now()


def test_regenerating_recovery_codes_invalidates_the_old_ones(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    clock.advance()

    response = client.post(
        "/auth/two-factor-recovery/",
        {"code": totp.build_totp(enrolled.secret, clock.step)},
        headers=enrolled.headers(),
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    fresh = body(response)["codes"]
    assert len(fresh) == 10
    assert set(fresh).isdisjoint(enrolled.recovery_codes)
    assert ApiUserRecoveryCode.objects.count() == 10


def test_disabling_needs_the_password_and_a_code(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)
    clock.advance()
    code = totp.build_totp(enrolled.secret, clock.step)

    wrong_password = client.post(
        "/auth/two-factor-disable/",
        {"code": code, "password": "incorrecta"},
        headers=enrolled.headers(),
    )
    assert wrong_password.status_code == HTTPStatus.BAD_REQUEST
    assert ApiUserTotpDevice.objects.filter(api_user=user).exists()

    clock.advance()
    disabled = client.post(
        "/auth/two-factor-disable/",
        {"code": totp.build_totp(enrolled.secret, clock.step), "password": PASSWORD},
        headers=enrolled.headers(),
    )
    assert disabled.status_code == HTTPStatus.NO_CONTENT, disabled.content
    assert not ApiUserTotpDevice.objects.filter(api_user=user).exists()
    assert not ApiUserRecoveryCode.objects.exists()

    # sin 2FA, el inicio de sesión vuelve a entregar la sesión directamente
    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_enrolling_twice_is_a_conflict(
    client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    enrolled = enroll(client, user, clock)

    response = client.post("/auth/two-factor-setup/", headers=enrolled.headers())

    assert response.status_code == HTTPStatus.CONFLICT


########################################################################################


def test_web_login_with_two_factor_goes_through_the_challenge_cookie(
    csrf_client: DMRClient,
    clock: Clock,
    user: ApiUser,
) -> None:
    csrf = {"X-CSRFToken": csrf_client.get("/auth/csrf/").headers["x-csrftoken"]}

    # alta del 2FA desde una sesión web
    csrf_client.post("/auth/web/login/", credentials(user), headers=csrf)
    secret = body(csrf_client.post("/auth/two-factor-setup/", headers=csrf))["secret"]
    confirm = csrf_client.post(
        "/auth/two-factor-confirm/",
        {"code": totp.build_totp(secret, clock.step)},
        headers=csrf,
    )
    assert confirm.status_code == HTTPStatus.CREATED, confirm.content
    csrf_client.post("/auth/web/logout/", headers=csrf)

    # el nuevo inicio de sesión deja solo la cookie del reto, no la sesión
    login = csrf_client.post("/auth/web/login/", credentials(user), headers=csrf)
    assert login.status_code == HTTPStatus.ACCEPTED, login.content
    assert "challenge" in login.cookies
    assert (
        "access" not in csrf_client.cookies or not csrf_client.cookies["access"].value
    )
    assert csrf_client.get("/auth/profile/").status_code == HTTPStatus.UNAUTHORIZED

    clock.advance()
    done = csrf_client.post(
        "/auth/web/two-factor/",
        {"code": totp.build_totp(secret, clock.step)},
        headers=csrf,
    )

    assert done.status_code == HTTPStatus.OK, done.content
    assert csrf_client.get("/auth/profile/").status_code == HTTPStatus.OK
