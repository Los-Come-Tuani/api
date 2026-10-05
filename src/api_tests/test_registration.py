from datetime import date, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.core import mail
from django.utils.timezone import localdate, now

from api_auth.models import ApiUser, ApiVerificationCode
from api_tests.helpers import PASSWORD, body, extract_code

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

EMAIL = "luis@example.com"

ADULT = date(1990, 5, 17)

########################################################################################


def registration(code: str, **overrides: object) -> dict:
    return {
        "birth_date": ADULT.isoformat(),
        "code": code,
        "email": EMAIL,
        "first_name": "Luis",
        "last_name": "Pérez",
        "nationality": "ni",
        "password": PASSWORD,
        **overrides,
    }


def ask_for_a_code(client: DMRClient, email: str = EMAIL) -> str:
    response = client.post("/auth/register-code/", {"email": email})

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content
    assert len(mail.outbox) == 1

    return extract_code(mail.outbox[0])


########################################################################################


def test_the_code_is_emailed_and_stored_hashed(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    row = ApiVerificationCode.objects.get(destination=EMAIL)

    assert mail.outbox[0].to == [EMAIL]
    assert row.purpose == "email"
    assert code not in row.code_hash
    assert row.expires_at > now()


def test_asking_for_a_code_is_silent_about_registered_emails(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(email=EMAIL)

    response = client.post("/auth/register-code/", {"email": EMAIL})

    # misma respuesta que con un correo nuevo, pero no se manda nada
    assert response.status_code == HTTPStatus.NO_CONTENT
    assert mail.outbox == []


def test_a_second_request_inside_the_cooldown_does_not_send_another_email(
    client: DMRClient,
) -> None:
    ask_for_a_code(client)

    again = client.post("/auth/register-code/", {"email": EMAIL})

    assert again.status_code == HTTPStatus.NO_CONTENT
    assert len(mail.outbox) == 1


def test_the_email_is_normalized_before_issuing_the_code(client: DMRClient) -> None:
    client.post("/auth/register-code/", {"email": "  Luis@Example.COM "})

    assert mail.outbox[0].to == [EMAIL]


def test_an_invalid_email_is_rejected(client: DMRClient) -> None:
    response = client.post("/auth/register-code/", {"email": "no-es-un-correo"})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert mail.outbox == []


########################################################################################


def test_verifying_a_code_does_not_spend_it(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    for _ in range(2):
        response = client.post("/auth/register-verify/", {"code": code, "email": EMAIL})
        assert response.status_code == HTTPStatus.NO_CONTENT, response.content


def test_a_wrong_code_is_rejected(client: DMRClient) -> None:
    code = ask_for_a_code(client)
    wrong = "000000" if code != "000000" else "111111"

    response = client.post("/auth/register-verify/", {"code": wrong, "email": EMAIL})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.code" in body(response)["field_errors"]


def test_five_wrong_codes_burn_the_code_even_for_the_right_one(
    client: DMRClient,
) -> None:
    code = ask_for_a_code(client)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        client.post("/auth/register-verify/", {"code": wrong, "email": EMAIL})

    response = client.post("/auth/register-verify/", {"code": code, "email": EMAIL})

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_code_does_not_work_for_another_email(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    response = client.post(
        "/auth/register-verify/",
        {"code": code, "email": "otra@example.com"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_an_expired_code_is_rejected(client: DMRClient) -> None:
    code = ask_for_a_code(client)
    ApiVerificationCode.objects.update(expires_at=now() - timedelta(seconds=1))

    response = client.post("/auth/register-verify/", {"code": code, "email": EMAIL})

    assert response.status_code == HTTPStatus.BAD_REQUEST


########################################################################################


def test_registering_creates_an_active_verified_tourist(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    response = client.post("/auth/register/", registration(code))

    assert response.status_code == HTTPStatus.CREATED, response.content
    data = body(response)
    assert data["email"] == EMAIL
    assert data["name"] == "Luis Pérez"
    assert data["nationality"] == "NI"
    assert data["birth_date"] == ADULT.isoformat()
    assert data["status"] == "active"
    assert data["verified"] is True
    assert data["role"] == "turista"
    assert [g["name"] for g in data["groups"]] == ["Cliente"]

    user = ApiUser.objects.get(email=EMAIL)
    assert user.is_active
    assert user.check_password(PASSWORD)
    assert not user.is_staff
    assert not user.is_superuser


def test_a_registered_user_can_log_in_and_the_code_is_spent(client: DMRClient) -> None:
    code = ask_for_a_code(client)
    client.post("/auth/register/", registration(code))

    login = client.post("/auth/mobile/login/", {"email": EMAIL, "password": PASSWORD})
    reuse = client.post("/auth/register-verify/", {"code": code, "email": EMAIL})

    assert login.status_code == HTTPStatus.OK, login.content
    assert reuse.status_code == HTTPStatus.BAD_REQUEST


def test_registering_accepts_an_optional_username(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    response = client.post("/auth/register/", registration(code, username="luis.p"))

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["username"] == "luis.p"


def test_registering_with_a_wrong_code_creates_nothing(client: DMRClient) -> None:
    ask_for_a_code(client)

    response = client.post("/auth/register/", registration("000000"))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_a_weak_password_does_not_spend_the_code(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    weak = client.post("/auth/register/", registration(code, password="corta1A"))
    assert weak.status_code == HTTPStatus.BAD_REQUEST
    assert "body.password" in body(weak)["field_errors"]

    # el mismo código sigue sirviendo para reintentar con una contraseña buena
    retry = client.post("/auth/register/", registration(code))
    assert retry.status_code == HTTPStatus.CREATED, retry.content


@pytest.mark.parametrize(
    "password",
    ["sinmayuscula1", "SinNumeroAlguno", "12345678", "Password1"],
)
def test_the_password_policy_requires_length_uppercase_and_a_number(
    client: DMRClient,
    password: str,
) -> None:
    code = ask_for_a_code(client)

    response = client.post("/auth/register/", registration(code, password=password))

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_minors_cannot_register(client: DMRClient) -> None:
    code = ask_for_a_code(client)
    today = localdate()
    minor = today.replace(year=today.year - 17).isoformat()

    response = client.post("/auth/register/", registration(code, birth_date=minor))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.birth_date" in body(response)["field_errors"]


def test_someone_who_just_turned_eighteen_can_register(client: DMRClient) -> None:
    code = ask_for_a_code(client)
    today = localdate()
    adult = today.replace(year=today.year - 18).isoformat()

    response = client.post("/auth/register/", registration(code, birth_date=adult))

    assert response.status_code == HTTPStatus.CREATED, response.content


@pytest.mark.parametrize("nationality", ["N", "NIC", "1A", ""])
def test_the_nationality_must_be_a_two_letter_country_code(
    client: DMRClient,
    nationality: str,
) -> None:
    code = ask_for_a_code(client)

    response = client.post(
        "/auth/register/",
        registration(code, nationality=nationality),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_registering_cannot_pick_a_group_or_status(client: DMRClient) -> None:
    code = ask_for_a_code(client)

    for extra in ({"group": "Administrador"}, {"status": "active"}, {"is_staff": True}):
        response = client.post("/auth/register/", registration(code, **extra))

        assert response.status_code == HTTPStatus.BAD_REQUEST
