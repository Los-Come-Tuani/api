from http import HTTPStatus
from time import time
from typing import TYPE_CHECKING

import jwt
import pytest

from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import Group

from api_auth.models import ApiExternalIdentity, ApiUser
from api_auth.services import google, totp
from api_core.config import CONFIG
from api_tests.helpers import PASSWORD, bearer, body, credentials

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_tests.conftest import Clock

########################################################################################

pytestmark = pytest.mark.django_db

CLIENT_ID = "123-test.apps.googleusercontent.com"

EMAIL = "luis@example.com"

ADULT = "1990-05-17"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)

########################################################################################


def google_token(*, key: rsa.RSAPrivateKey = KEY, **claims: object) -> str:
    issued = int(time())

    payload: dict = {
        "aud": CLIENT_ID,
        "email": EMAIL,
        "email_verified": True,
        "exp": issued + 3600,
        "family_name": "Pérez",
        "given_name": "Luis",
        "iat": issued,
        "iss": "https://accounts.google.com",
        "sub": "110169484474386276334",
    }

    return jwt.encode({**payload, **claims}, key, algorithm="RS256")


def sign_in(client: DMRClient, token: str | None = None, **extra: object) -> object:
    return client.post(
        "/auth/mobile/google/",
        {"id_token": token or google_token(), **extra},
    )


def profile_data() -> dict[str, str]:
    return {"birth_date": ADULT, "nationality": "ni"}


@pytest.fixture(autouse=True)
def _google_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # `CONFIG` es un modelo congelado: se reemplaza el valor en su `__dict__`
    monkeypatch.setitem(CONFIG.__dict__, "GOOGLE_OAUTH_CLIENT_IDS", (CLIENT_ID,))
    # las llaves de Google se reemplazan por una propia de la prueba
    monkeypatch.setattr(google, "signing_key_for", lambda _: KEY.public_key())


def tourist(make_user: Callable[..., ApiUser], **extra: object) -> ApiUser:
    user = make_user(email=EMAIL, **extra)
    user.groups.add(Group.objects.get(name="Cliente"))  # ty: ignore[unresolved-attribute]

    return user


########################################################################################


def test_google_is_disabled_until_a_client_id_is_configured(
    client: DMRClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(CONFIG.__dict__, "GOOGLE_OAUTH_CLIENT_IDS", ())

    response = sign_in(client, **profile_data())

    assert response.status_code == HTTPStatus.NOT_FOUND  # ty: ignore[unresolved-attribute]


def test_a_new_person_must_complete_the_profile_first(client: DMRClient) -> None:
    response = sign_in(client)

    assert response.status_code == HTTPStatus.BAD_REQUEST  # ty: ignore[unresolved-attribute]
    errors = body(response)["field_errors"]  # ty: ignore[invalid-argument-type]
    assert {"body.birth_date", "body.nationality"} <= set(errors)
    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_a_new_person_gets_a_verified_tourist_account(client: DMRClient) -> None:
    response = sign_in(client, **profile_data())

    assert response.status_code == HTTPStatus.OK, response.content  # ty: ignore[unresolved-attribute]
    data = body(response)  # ty: ignore[invalid-argument-type]
    assert data["access"]
    assert data["user"]["email"] == EMAIL
    assert data["user"]["name"] == "Luis Pérez"
    assert data["user"]["nationality"] == "NI"
    assert data["user"]["verified"] is True
    assert data["user"]["role"] == "turista"

    user = ApiUser.objects.get(email=EMAIL)
    assert not user.has_usable_password()
    identity = ApiExternalIdentity.objects.get(user=user)
    assert (identity.provider, identity.subject) == ("google", "110169484474386276334")


def test_the_returning_person_signs_in_without_the_profile(
    client: DMRClient,
) -> None:
    sign_in(client, **profile_data())

    again = sign_in(client)

    assert again.status_code == HTTPStatus.OK, again.content  # ty: ignore[unresolved-attribute]
    assert ApiUser.objects.filter(email=EMAIL).count() == 1
    assert ApiExternalIdentity.objects.count() == 1


def test_the_returning_person_is_found_by_subject_even_if_the_email_changed(
    client: DMRClient,
) -> None:
    sign_in(client, **profile_data())

    renamed = google_token(email="nuevo@example.com")
    response = sign_in(client, renamed)

    assert response.status_code == HTTPStatus.OK  # ty: ignore[unresolved-attribute]
    assert body(response)["user"]["email"] == EMAIL  # ty: ignore[invalid-argument-type]


def test_minors_cannot_create_an_account_with_google(client: DMRClient) -> None:
    response = sign_in(client, birth_date="2020-01-01", nationality="NI")

    assert response.status_code == HTTPStatus.BAD_REQUEST  # ty: ignore[unresolved-attribute]
    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_a_verified_account_with_the_same_email_gets_linked(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    user = tourist(make_user)

    response = sign_in(client)

    assert response.status_code == HTTPStatus.OK, response.content  # ty: ignore[unresolved-attribute]
    assert ApiExternalIdentity.objects.get(user=user).subject
    # la contraseña sigue sirviendo
    assert client.post("/auth/mobile/login/", credentials(user)).status_code == (
        HTTPStatus.OK
    )


def test_an_unverified_account_is_never_linked_by_email(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    # quien creó esa cuenta nunca probó que el correo fuera suyo: vincularla le
    # regalaría la cuenta de la persona que entra con Google
    pending = tourist(make_user, status="pending")
    assert pending.verified_at is None

    response = sign_in(client)

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert not ApiExternalIdentity.objects.exists()
    assert pending.verified_at is None


def test_team_accounts_cannot_use_google(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(email=EMAIL, is_staff=True, is_superuser=True)

    response = sign_in(client)

    assert response.status_code == HTTPStatus.FORBIDDEN  # ty: ignore[unresolved-attribute]


def test_an_account_that_cannot_operate_is_refused(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    tourist(make_user, status="suspended")

    response = sign_in(client)

    assert response.status_code == HTTPStatus.FORBIDDEN  # ty: ignore[unresolved-attribute]


########################################################################################


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda: "no-es-un-jwt-pero-es-largo-de-sobra", id="garbage"),
        pytest.param(
            lambda: google_token(aud="otra-app.apps.googleusercontent.com"),
            id="audience",
        ),
        pytest.param(lambda: google_token(iss="https://evil.example.com"), id="issuer"),
        pytest.param(
            lambda: google_token(exp=int(time()) - 3600, iat=int(time()) - 7200),
            id="expired",
        ),
        pytest.param(lambda: google_token(key=OTHER_KEY), id="signature"),
        pytest.param(lambda: google_token(email_verified=False), id="unverified"),
        pytest.param(lambda: google_token(email=""), id="no-email"),
    ],
)
def test_invalid_google_tokens_are_rejected(
    client: DMRClient,
    token: Callable[[], str],
) -> None:
    response = sign_in(client, token(), **profile_data())

    assert response.status_code == HTTPStatus.UNAUTHORIZED  # ty: ignore[unresolved-attribute]
    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_an_unsigned_token_is_rejected(client: DMRClient) -> None:
    unsigned = jwt.encode({"aud": CLIENT_ID, "sub": "1"}, key="", algorithm="none")

    response = sign_in(client, unsigned, **profile_data())

    assert response.status_code == HTTPStatus.UNAUTHORIZED  # ty: ignore[unresolved-attribute]


def test_the_email_verified_claim_may_come_as_text(client: DMRClient) -> None:
    response = sign_in(client, google_token(email_verified="true"), **profile_data())

    assert response.status_code == HTTPStatus.OK  # ty: ignore[unresolved-attribute]


########################################################################################


def test_google_still_asks_for_the_second_factor(
    client: DMRClient,
    clock: Clock,
    make_user: Callable[..., ApiUser],
) -> None:
    user = tourist(make_user)
    session = body(client.post("/auth/mobile/login/", credentials(user)))
    secret = body(
        client.post("/auth/two-factor-setup/", headers=bearer(session["access"])),
    )["secret"]
    client.post(
        "/auth/two-factor-confirm/",
        {"code": totp.build_totp(secret, clock.step)},
        headers=bearer(session["access"]),
    )

    response = sign_in(client)

    assert response.status_code == HTTPStatus.ACCEPTED, response.content  # ty: ignore[unresolved-attribute]
    challenge = body(response)["challenge"]  # ty: ignore[invalid-argument-type]

    clock.advance()
    done = client.post(
        "/auth/mobile/two-factor/",
        {"challenge": challenge, "code": totp.build_totp(secret, clock.step)},
    )
    assert done.status_code == HTTPStatus.OK, done.content


def test_the_web_endpoint_sets_cookies_and_requires_csrf(
    csrf_client: DMRClient,
) -> None:
    payload = {"id_token": google_token(), **profile_data()}

    blocked = csrf_client.post("/auth/web/google/", payload)
    assert blocked.status_code == HTTPStatus.FORBIDDEN

    token = csrf_client.get("/auth/csrf/").headers["x-csrftoken"]
    response = csrf_client.post(
        "/auth/web/google/",
        payload,
        headers={"X-CSRFToken": token},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["user"]["email"] == EMAIL
    assert response.cookies["access"]["httponly"]
    assert csrf_client.get("/auth/profile/").status_code == HTTPStatus.OK


def test_a_google_only_account_has_no_password_to_log_in_with(
    client: DMRClient,
) -> None:
    sign_in(client, **profile_data())

    response = client.post(
        "/auth/mobile/login/",
        {"email": EMAIL, "password": PASSWORD},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_the_audience_may_be_any_of_the_configured_client_ids(
    client: DMRClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        CONFIG.__dict__,
        "GOOGLE_OAUTH_CLIENT_IDS",
        ("otro.apps.googleusercontent.com", CLIENT_ID),
    )

    response = sign_in(client, **profile_data())

    assert response.status_code == HTTPStatus.OK  # ty: ignore[unresolved-attribute]
