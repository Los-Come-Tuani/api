from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from api_auth.catalog import ALL_IDS, expand_implied
from api_auth.enums import AccountRoles, ApiUserStatus, GroupKinds
from api_auth.models import (
    ApiGroupProfile,
    ApiUser,
    ApiUserGroups,
    ApiUserPermissions,
)
from api_auth.seeder import EXAMPLE_ROLES, SYSTEM_ROLES, execute
from api_auth.services import totp
from api_auth.services.roles import (
    TWO_FACTOR_REQUIRED_DETAIL,
    functional_permissions_sync,
)
from api_tests.helpers import PASSWORD, body, credentials, web_login

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_tests.conftest import Clock

########################################################################################

pytestmark = pytest.mark.django_db

# - los identificadores que ya usa el portal (`src/data/models/access.ts`): si uno
#   cambia de nombre, el portal deja de entender los permisos de la sesión
PORTAL_IDS = frozenset({
    "agenda.view",
    "billing.manage",
    "billing.view",
    "circuits.manage",
    "circuits.view",
    "content.moderate",
    "guides.decide",
    "guides.review",
    "guides.view",
    "organizations.manage",
    "organizations.review",
    "organizations.view",
    "places.manage",
    "places.view",
    "staff.manage",
    "users.manage",
    "users.view",
})

########################################################################################
# Catálogo y siembra


def test_the_catalog_keeps_the_ids_the_portal_uses() -> None:
    assert ALL_IDS == PORTAL_IDS


def test_a_stronger_permission_implies_viewing() -> None:
    assert expand_implied({"guides.decide"}) == {"guides.decide", "guides.view"}
    assert expand_implied({"users.manage"}) == {"users.manage", "users.view"}
    # lo que no es de lectura no se deduce hacia arriba
    assert expand_implied({"guides.view"}) == {"guides.view"}


def test_seeding_creates_the_catalog_and_every_role() -> None:
    execute()

    # con el tipo de contenido de `ApiGroupProfile` conviven los permisos de modelo de
    # Django y los funcionales
    content_type = ContentType.objects.get_for_model(ApiGroupProfile)
    seeded = set(
        Permission.objects.filter(content_type=content_type).values_list(
            "codename", flat=True
        )
    )
    assert seeded >= ALL_IDS

    profiles = {
        str(profile.group.name): profile
        for profile in ApiGroupProfile.objects.select_related("group")
    }

    for spec in (*SYSTEM_ROLES, *EXAMPLE_ROLES):
        profile = profiles[spec.name]

        assert profile.kind == spec.kind, spec.name
        assert profile.role == spec.role, spec.name
        assert profile.is_system is spec.is_system, spec.name
        assert profile.requires_two_factor is spec.requires_two_factor, spec.name


def test_the_super_admin_group_has_every_functional_permission() -> None:
    execute()

    admin = Group.objects.get(name="Administrador")
    granted = set(
        admin.permissions.filter(codename__in=ALL_IDS).values_list(
            "codename", flat=True
        )
    )

    assert granted == ALL_IDS


def test_seeding_again_restores_system_roles_but_leaves_edited_examples_alone() -> None:
    execute()

    Group.objects.get(name="Verificador").permissions.clear()
    ApiGroupProfile.objects.filter(group__name="Negocio").update(
        requires_two_factor=True,
    )
    total = ApiGroupProfile.objects.count()

    execute()

    assert ApiGroupProfile.objects.count() == total
    # un rol de ejemplo lo edita el equipo y volver a sembrar no lo pisa
    assert not Group.objects.get(name="Verificador").permissions.exists()
    # uno de sistema se vuelve a dejar como el sistema lo garantiza
    negocio = ApiGroupProfile.objects.get(group__name="Negocio")
    assert negocio.requires_two_factor is False


def test_an_example_role_deleted_by_the_team_comes_back_only_by_seeding() -> None:
    execute()
    Group.objects.filter(name="Moderador de contenido").delete()

    assert not Group.objects.filter(name="Moderador de contenido").exists()

    execute()

    assert Group.objects.filter(name="Moderador de contenido").exists()


########################################################################################
# Permisos de la sesión


def test_the_session_carries_the_role_and_the_functional_permissions(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    member = make_member("equipo@example.com", "guides.decide", "users.view")

    session = web_login(client, member)

    assert session["user"]["role"] == "admin"
    # decidir sobre las solicitudes incluye verlas
    assert session["user"]["permissions"] == [
        "guides.decide",
        "guides.view",
        "users.view",
    ]
    assert body(client.get("/auth/profile/"))["permissions"] == [
        "guides.decide",
        "guides.view",
        "users.view",
    ]


def test_a_tourist_session_has_a_public_role_and_no_permissions(
    client: DMRClient,
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> None:
    tourist = make_user(email="turista@example.com")
    ApiUserGroups.objects.create(
        api_user=tourist,
        group=make_role(
            "Turistas",
            kind=GroupKinds.PUBLIC,
            role=AccountRoles.TURISTA,
        ),
    )

    response = client.post("/auth/mobile/login/", credentials(tourist))

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["user"]["role"] == "turista"
    assert body(response)["user"]["permissions"] == []


def test_the_session_follows_the_role_as_it_changes(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    member = make_member("equipo@example.com", "users.view")
    web_login(client, member)

    assert body(client.get("/auth/profile/"))["permissions"] == ["users.view"]

    Group.objects.get(name="Rol de equipo@example.com").permissions.clear()

    assert body(client.get("/auth/profile/"))["permissions"] == []


def test_a_permission_given_straight_to_the_user_does_not_count(
    make_role: Callable[..., Group],
    user: ApiUser,
) -> None:
    make_role("Cualquiera")
    ApiUserPermissions.objects.create(
        api_user=user,
        permission=Permission.objects.get(codename="staff.manage"),
    )

    assert functional_permissions_sync(user) == frozenset()


def test_an_account_that_cannot_operate_has_no_permissions(
    make_member: Callable[..., ApiUser],
) -> None:
    member = make_member("equipo@example.com", "staff.manage")

    assert functional_permissions_sync(member) == {"staff.manage"}

    ApiUser.objects.filter(pk=member.pk).update(
        is_active=False,
        status=ApiUserStatus.SUSPENDED,
    )
    member.refresh_from_db()

    assert functional_permissions_sync(member) == frozenset()


########################################################################################
# Por dónde entra cada rol (RF-S-08)

DENIED = "Las credenciales proporcionadas no son válidas."


@pytest.mark.parametrize(
    ("kind", "role", "allowed", "denied"),
    [
        (GroupKinds.STAFF, AccountRoles.ADMIN, "web", "mobile"),
        (GroupKinds.OPERATOR, AccountRoles.NEGOCIO, "web", "mobile"),
        (GroupKinds.PUBLIC, AccountRoles.GUIA, "mobile", "web"),
        (GroupKinds.PUBLIC, AccountRoles.TURISTA, "mobile", "web"),
    ],
)
def test_each_kind_of_role_enters_only_by_its_own_surface(
    client: DMRClient,
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
    allowed: str,
    denied: str,
    kind: str,
    role: str,
) -> None:
    holder = make_user(email="alguien@example.com")
    ApiUserGroups.objects.create(
        api_user=holder,
        group=make_role("Rol", kind=kind, role=role),
    )

    enters = client.post(f"/auth/{allowed}/login/", credentials(holder))
    refused = client.post(f"/auth/{denied}/login/", credentials(holder))

    assert enters.status_code == HTTPStatus.OK, enters.content
    # por la otra superficie se responde como si la contraseña fuera mala: no se
    # revela que la cuenta existe
    assert refused.status_code == HTTPStatus.UNAUTHORIZED
    assert body(refused)["detail"] == DENIED


@pytest.mark.parametrize("surface", ["mobile", "web"])
def test_a_user_without_groups_and_a_superuser_enter_by_both_surfaces(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
    surface: str,
) -> None:
    plain = make_user(email="sin-rol@example.com")
    root = make_user(email="root@example.com", is_superuser=True)

    for account in (plain, root):
        response = client.post(f"/auth/{surface}/login/", credentials(account))

        assert response.status_code == HTTPStatus.OK, response.content


def test_a_blocked_surface_counts_as_a_failed_attempt(
    client: DMRClient,
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> None:
    holder = make_user(email="alguien@example.com")
    ApiUserGroups.objects.create(
        api_user=holder,
        group=make_role("Equipo"),
    )

    for _ in range(5):
        client.post("/auth/mobile/login/", credentials(holder))

    # tantear otra superficie también cuenta para el bloqueo por intentos
    locked = client.post("/auth/web/login/", credentials(holder))

    assert locked.status_code == HTTPStatus.TOO_MANY_REQUESTS


########################################################################################
# Segundo factor obligatorio


def enroll_over_the_web(client: DMRClient, clock: Clock) -> str:
    setup = client.post("/auth/two-factor-setup/")
    assert setup.status_code == HTTPStatus.CREATED, setup.content
    secret: str = body(setup)["secret"]

    confirm = client.post(
        "/auth/two-factor-confirm/",
        {"code": totp.build_totp(secret, clock.step)},
    )
    assert confirm.status_code == HTTPStatus.CREATED, confirm.content

    return secret


def test_a_role_that_requires_two_factor_works_only_after_enrolling(
    client: DMRClient,
    clock: Clock,
    make_member: Callable[..., ApiUser],
) -> None:
    member = make_member("equipo@example.com", "staff.manage", requires_two_factor=True)

    session = web_login(client, member)
    assert session["user"]["two_factor"] == {"enabled": False, "required": True}

    blocked = client.get("/auth/staff-role/")
    assert blocked.status_code == HTTPStatus.FORBIDDEN
    assert body(blocked)["detail"] == TWO_FACTOR_REQUIRED_DETAIL

    # lo mínimo de la cuenta sigue funcionando para poder activarlo
    assert client.get("/auth/profile/").status_code == HTTPStatus.OK
    assert client.get("/auth/two-factor/").status_code == HTTPStatus.OK

    enroll_over_the_web(client, clock)

    assert client.get("/auth/staff-role/").status_code == HTTPStatus.OK


def test_a_role_without_the_requirement_works_without_two_factor(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    member = make_member("equipo@example.com", "staff.manage")

    session = web_login(client, member)

    assert session["user"]["two_factor"] == {"enabled": False, "required": False}
    assert client.get("/auth/staff-role/").status_code == HTTPStatus.OK


def test_two_factor_cannot_be_disabled_when_the_role_requires_it(
    client: DMRClient,
    clock: Clock,
    make_member: Callable[..., ApiUser],
) -> None:
    member = make_member("equipo@example.com", "staff.manage", requires_two_factor=True)
    web_login(client, member)
    secret = enroll_over_the_web(client, clock)

    clock.advance()
    response = client.post(
        "/auth/two-factor-disable/",
        {"code": totp.build_totp(secret, clock.step), "password": PASSWORD},
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "dos pasos" in body(response)["detail"]
    assert client.get("/auth/two-factor/").status_code == HTTPStatus.OK


def test_the_requirement_does_not_reach_people_without_such_a_role(
    client: DMRClient,
    user: ApiUser,
) -> None:
    session = body(client.post("/auth/mobile/login/", credentials(user)))

    assert session["user"]["two_factor"] == {"enabled": False, "required": False}


########################################################################################
# `users.view` sobre el listado de usuarios


def test_users_view_opens_the_user_listing_but_not_its_writes(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    user: ApiUser,
) -> None:
    viewer = make_member("lector@example.com", "users.view")
    web_login(client, viewer)

    assert client.get("/auth/user/").status_code == HTTPStatus.OK
    assert client.get("/auth/user/all/").status_code == HTTPStatus.OK
    assert client.get(f"/auth/user/{user.pk}/").status_code == HTTPStatus.OK

    # leer no es escribir
    assert client.delete(f"/auth/user/{user.pk}/").status_code == HTTPStatus.FORBIDDEN
    assert client.patch(
        f"/auth/user/{user.pk}/",
        {"first_name": "Otro"},
    ).status_code == (HTTPStatus.FORBIDDEN)

    # los grupos y permisos sueltos de una persona son de administración: siguen
    # pidiendo los permisos del modelo
    assert client.get(f"/auth/user/{user.pk}/groups/").status_code == (
        HTTPStatus.FORBIDDEN
    )
    assert client.get(f"/auth/user/{user.pk}/permissions/").status_code == (
        HTTPStatus.FORBIDDEN
    )


def test_a_role_without_users_view_does_not_see_the_user_listing(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    other = make_member("otra@example.com", "guides.view")
    web_login(client, other)

    assert client.get("/auth/user/").status_code == HTTPStatus.FORBIDDEN
    assert client.get("/auth/user/all/").status_code == HTTPStatus.FORBIDDEN
