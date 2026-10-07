from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group

from api_auth.enums import ApiUserStatus, ApiUserTypes
from api_auth.models import ApiUser, ApiUserGroups
from api_catalogs.models import BusinessType
from api_organizations.models import Business
from api_roles.services import grant_role_sync
from api_territory.models import City
from api_tests.helpers import body, web_login

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Final

    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

ACCOUNTS: Final[str] = "/auth/account/"

########################################################################################


def join(user: ApiUser, group_name: str) -> None:
    ApiUserGroups.objects.create(
        api_user=user, group=Group.objects.get(name=group_name)
    )


@pytest.fixture
def tourist(make_user: Callable[..., ApiUser]) -> ApiUser:
    user = make_user(email="turista@example.com", first_name="José", last_name="Pérez")
    join(user, ApiUserTypes.CLIENT.value)

    return user


@pytest.fixture
def operator(make_user: Callable[..., ApiUser]) -> ApiUser:
    city = City.objects.get(code="leon")
    business = Business.objects.create(
        address="Frente a la catedral",
        business_type=BusinessType.objects.get(code="restaurante"),
        city=city,
        latitude=Decimal("12.437900"),
        longitude=Decimal("-86.878000"),
        name="El Sacuanjoche",
        phone="2311-0000",
        ruc="J0310000000001",
    )
    user = make_user(email="negocio@example.com", first_name="Marta")

    grant_role_sync(
        granted_by=user,
        role=Group.objects.get(name="Negocio"),
        scope_object=business,
        user=user,
    )

    return user


def emails(response_body: dict) -> set[str]:
    return {item["email"] for item in response_body["results"]}


########################################################################################
# Quién entra


@pytest.mark.parametrize(
    ("permissions", "status"),
    [
        ((), HTTPStatus.FORBIDDEN),
        (("users.view",), HTTPStatus.OK),
        (("users.manage",), HTTPStatus.OK),
        (("staff.manage",), HTTPStatus.OK),
        (("guides.view",), HTTPStatus.FORBIDDEN),
    ],
)
def test_the_directory_opens_with_users_view_or_staff_manage(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    permissions: tuple[str, ...],
    status: HTTPStatus,
) -> None:
    web_login(client, make_member("miembro@example.com", *permissions))

    assert client.get(ACCOUNTS).status_code == status


def test_the_directory_needs_a_session(client: DMRClient, tourist: ApiUser) -> None:
    assert client.get(ACCOUNTS).status_code == HTTPStatus.UNAUTHORIZED
    assert client.get(f"{ACCOUNTS}{tourist.pk}/").status_code == HTTPStatus.UNAUTHORIZED


########################################################################################
# Lo que se ve


@pytest.mark.usefixtures("operator", "tourist")
def test_whoever_sees_users_sees_every_account_with_its_role(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    viewer = make_member("miembro@example.com", "users.view")
    web_login(client, viewer)

    response = client.get(ACCOUNTS, {"page_size": 100})

    assert response.status_code == HTTPStatus.OK, response.content
    by_email = {item["email"]: item for item in body(response)["results"]}

    assert by_email["turista@example.com"]["role"] == "turista"
    assert by_email["turista@example.com"]["organization"] is None
    assert by_email["negocio@example.com"]["role"] == "negocio"
    assert by_email["negocio@example.com"]["organization"]["kind"] == "business"
    assert by_email["negocio@example.com"]["city"]["code"] == "leon"
    assert by_email["miembro@example.com"]["role"] == "admin"
    assert by_email["miembro@example.com"]["staff_role"]["name"] == (
        "Rol de miembro@example.com"
    )


@pytest.mark.usefixtures("operator", "tourist")
def test_the_directory_filters_by_role_status_and_name_without_accents(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
) -> None:
    suspended = make_user(email="suspendida@example.com")
    join(suspended, ApiUserTypes.CLIENT.value)
    ApiUser.objects.filter(pk=suspended.pk).update(
        is_active=False, status=ApiUserStatus.SUSPENDED
    )
    web_login(client, make_member("miembro@example.com", "users.view"))

    by_role = body(client.get(ACCOUNTS, {"role": "negocio"}))
    by_status = body(client.get(ACCOUNTS, {"status": "suspended"}))
    by_name = body(client.get(ACCOUNTS, {"search": "jose"}))
    team = body(client.get(ACCOUNTS, {"role": "admin"}))

    assert emails(by_role) == {"negocio@example.com"}
    assert emails(by_status) == {"suspendida@example.com"}
    assert emails(by_name) == {"turista@example.com"}
    assert "miembro@example.com" in emails(team)
    assert "turista@example.com" not in emails(team)


def test_the_directory_is_paginated(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
) -> None:
    for index in range(3):
        join(make_user(email=f"t{index}@example.com"), ApiUserTypes.CLIENT.value)
    web_login(client, make_member("miembro@example.com", "users.view"))

    first = body(client.get(ACCOUNTS, {"page_size": 2, "role": "turista"}))
    second = body(client.get(ACCOUNTS, {"page": 2, "page_size": 2, "role": "turista"}))

    assert first["elements"] == 3
    assert first["next"] is True
    assert len(first["results"]) == 2
    assert len(second["results"]) == 1
    assert second["previous"] is True


def test_whoever_only_manages_the_team_only_sees_the_team(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    tourist: ApiUser,
) -> None:
    web_login(client, make_member("miembro@example.com", "staff.manage"))

    listed = body(client.get(ACCOUNTS, {"page_size": 100}))
    detail = client.get(f"{ACCOUNTS}{tourist.pk}/")

    assert "turista@example.com" not in emails(listed)
    assert "miembro@example.com" in emails(listed)
    assert detail.status_code == HTTPStatus.NOT_FOUND


def test_the_detail_shows_one_account(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    tourist: ApiUser,
) -> None:
    web_login(client, make_member("miembro@example.com", "users.view"))

    response = client.get(f"{ACCOUNTS}{tourist.pk}/")

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["name"] == "José Pérez"
    assert body(response)["status"] == "active"


########################################################################################
# Cambios


def test_whoever_manages_users_edits_the_name_of_an_account(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    tourist: ApiUser,
) -> None:
    web_login(client, make_member("miembro@example.com", "users.manage"))

    response = client.patch(f"{ACCOUNTS}{tourist.pk}/", {"first_name": "Josefa"})

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["first_name"] == "Josefa"
    assert body(response)["last_name"] == "Pérez"


def test_editing_the_team_needs_staff_manage(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    colleague = make_member("colega@example.com", "guides.view")
    web_login(client, make_member("miembro@example.com", "users.manage"))

    response = client.patch(f"{ACCOUNTS}{colleague.pk}/", {"first_name": "Otra"})

    assert response.status_code == HTTPStatus.FORBIDDEN, response.content


def test_whoever_manages_the_team_edits_a_colleague(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    colleague = make_member("colega@example.com", "guides.view")
    web_login(client, make_member("miembro@example.com", "staff.manage"))

    response = client.patch(f"{ACCOUNTS}{colleague.pk}/", {"last_name": "Ruiz"})

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["last_name"] == "Ruiz"


def test_nobody_edits_their_own_account_or_a_superuser_from_here(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
) -> None:
    member = make_member(
        "miembro@example.com", "users.manage", "staff.manage", "users.view"
    )
    root = make_user(email="root@example.com", is_superuser=True)
    web_login(client, member)

    own = client.patch(f"{ACCOUNTS}{member.pk}/", {"first_name": "Yo"})
    superuser = client.patch(f"{ACCOUNTS}{root.pk}/", {"first_name": "Raíz"})

    assert own.status_code == HTTPStatus.FORBIDDEN
    assert superuser.status_code == HTTPStatus.FORBIDDEN


def test_the_email_is_not_edited_from_the_directory(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    tourist: ApiUser,
) -> None:
    web_login(client, make_member("miembro@example.com", "users.manage"))

    response = client.patch(f"{ACCOUNTS}{tourist.pk}/", {"email": "otro@example.com"})

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
