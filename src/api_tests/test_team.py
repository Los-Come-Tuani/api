from datetime import timedelta
from http import HTTPStatus
from time import sleep
from typing import TYPE_CHECKING, NamedTuple
from uuid import uuid4

import pytest

from django.contrib.auth.models import Group, Permission
from django.core import mail
from dmr.test import DMRClient

from api_auth.catalog import ALL_IDS
from api_auth.enums import AccountRoles, ApiUserStatus, GroupKinds
from api_auth.models import ApiUser, ApiUserGroups
from api_auth.seeder import execute
from api_auth.services import verification
from api_auth.services.team import LAST_ADMIN_DETAIL, SYSTEM_ROLE_DETAIL
from api_core.config import CONFIG
from api_tests.helpers import (
    PASSWORD,
    bearer,
    body,
    credentials,
    extract_code,
    web_login,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Final

    from django.http import HttpResponse

########################################################################################

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Otra-Clave-2026"

########################################################################################
# Qué abre cada permiso


class Ids(NamedTuple):
    role: int
    target: str


# - método, ruta, cuerpo y quiénes pasan. `users.manage` incluye `users.view`
MATRIX: Final[
    tuple[tuple[str, str, Callable[[Ids], dict | None], frozenset[str]], ...]
] = (
    ("get", "/auth/staff-permission/", lambda _: None, frozenset({"staff"})),
    (
        "get",
        "/auth/staff-role/",
        lambda _: None,
        frozenset({"staff", "users", "viewer"}),
    ),
    (
        "post",
        "/auth/staff-role/",
        lambda _: {"name": "Nuevo", "permissions": []},
        frozenset({"staff"}),
    ),
    (
        "get",
        "/auth/staff-role/{role}/",
        lambda _: None,
        frozenset({"staff", "users", "viewer"}),
    ),
    (
        "put",
        "/auth/staff-role/{role}/",
        lambda _: {"name": "Editado", "permissions": []},
        frozenset({"staff"}),
    ),
    ("delete", "/auth/staff-role/{role}/", lambda _: None, frozenset({"staff"})),
    (
        "get",
        "/auth/staff-member/",
        lambda _: None,
        frozenset({"staff", "users", "viewer"}),
    ),
    (
        "post",
        "/auth/staff-invite/",
        lambda ids: {
            "email": "nueva@example.com",
            "first_name": "Nueva",
            "role_id": ids.role,
        },
        frozenset({"staff"}),
    ),
    (
        "post",
        "/auth/user-status/",
        lambda ids: {"status": "suspended", "user_id": ids.target},
        frozenset({"users"}),
    ),
    (
        "post",
        "/auth/user-role/",
        lambda ids: {"role_id": ids.role, "user_id": ids.target},
        frozenset({"staff"}),
    ),
    (
        "post",
        "/auth/user-password-reset/",
        lambda ids: {"user_id": ids.target},
        frozenset({"users"}),
    ),
)

MATRIX_IDS: Final[list[str]] = [f"{m.upper()} {p}" for m, p, *_ in MATRIX]

HOLDERS: Final[dict[str, tuple[str, ...]]] = {
    "nobody": (),
    "staff": ("staff.manage",),
    "users": ("users.manage",),
    "viewer": ("users.view",),
}


def prepare(
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> Ids:
    # un rol del equipo y una persona del equipo sobre la cual actuar
    target = make_user(email="destino@example.com")
    ApiUserGroups.objects.create(api_user=target, group=make_role("Rol de destino"))

    return Ids(role=make_role("Rol de prueba").pk, target=str(target.pk))


def call(
    client: DMRClient,
    method: str,
    path: str,
    payload: dict | None,
    **extra: object,
) -> HttpResponse:
    send = getattr(client, method)

    if payload is None:
        return send(path, **extra)

    return send(path, payload, **extra)


@pytest.mark.parametrize("holder", HOLDERS)
@pytest.mark.parametrize(
    ("method", "path", "payload", "allowed"),
    MATRIX,
    ids=MATRIX_IDS,
)
def test_each_role_reaches_only_what_its_permissions_open(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
    allowed: frozenset[str],
    holder: str,
    method: str,
    path: str,
    payload: Callable[[Ids], dict | None],
) -> None:
    web_login(client, make_member("miembro@example.com", *HOLDERS[holder]))
    ids = prepare(make_role, make_user)

    response = call(
        client,
        method,
        path.format(role=ids.role),
        payload(ids),
    )

    if holder in allowed:
        assert response.status_code not in {
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        }, response.content
    else:
        assert response.status_code == HTTPStatus.FORBIDDEN, response.content


@pytest.mark.parametrize(
    ("method", "path", "payload", "allowed"),
    MATRIX,
    ids=MATRIX_IDS,
)
def test_the_team_endpoints_need_a_session(
    client: DMRClient,
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
    allowed: frozenset[str],  # ruff: ignore[unused-function-argument]
    method: str,
    path: str,
    payload: Callable[[Ids], dict | None],
) -> None:
    ids = prepare(make_role, make_user)

    response = call(client, method, path.format(role=ids.role), payload(ids))

    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.content


@pytest.mark.parametrize(
    ("method", "path", "payload", "allowed"),
    MATRIX,
    ids=MATRIX_IDS,
)
def test_a_tourist_cannot_use_the_team_endpoints(
    client: DMRClient,
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
    allowed: frozenset[str],  # ruff: ignore[unused-function-argument]
    method: str,
    path: str,
    payload: Callable[[Ids], dict | None],
) -> None:
    tourist = make_user(email="turista@example.com")
    ApiUserGroups.objects.create(
        api_user=tourist,
        group=make_role("Turistas", kind=GroupKinds.PUBLIC, role=AccountRoles.TURISTA),
    )
    access = body(client.post("/auth/mobile/login/", credentials(tourist)))["access"]
    ids = prepare(make_role, make_user)

    response = call(
        client,
        method,
        path.format(role=ids.role),
        payload(ids),
        headers=bearer(access),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, response.content


########################################################################################


@pytest.fixture
def manager(client: DMRClient, make_member: Callable[..., ApiUser]) -> ApiUser:
    # quien administra el equipo y las cuentas, con la sesión web ya abierta
    member = make_member("jefa@example.com", "staff.manage", "users.manage")

    web_login(client, member)

    return member


def role_of_manager(manager: ApiUser) -> Group:
    return ApiUserGroups.objects.get(api_user=manager).group


def link(user: ApiUser, group: Group) -> None:
    ApiUserGroups.objects.create(api_user=user, group=group)


########################################################################################
# Catálogo y roles


def test_the_permission_catalog_lists_every_permission(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    response = client.get("/auth/staff-permission/")

    assert response.status_code == HTTPStatus.OK, response.content
    catalog = body(response)
    assert {item["id"] for item in catalog} == ALL_IDS
    assert all(item["label"] and item["module"] for item in catalog)


def test_the_role_list_shows_team_roles_with_their_members_and_permissions(
    client: DMRClient,
    manager: ApiUser,
    make_role: Callable[..., Group],
) -> None:
    make_role("Pública", kind=GroupKinds.PUBLIC, role=AccountRoles.TURISTA)

    response = client.get("/auth/staff-role/")

    assert response.status_code == HTTPStatus.OK, response.content
    roles = body(response)
    # los roles de la calle no se administran desde el equipo
    assert "Pública" not in {role["name"] for role in roles}

    mine = next(role for role in roles if role["id"] == role_of_manager(manager).pk)
    assert mine["members"] == 1
    assert mine["permissions"] == ["staff.manage", "users.manage"]
    assert mine["system"] is False
    assert mine["requires_two_factor"] is False


def test_the_team_list_shows_each_member_with_their_team_role(
    client: DMRClient,
    manager: ApiUser,
    make_member: Callable[..., ApiUser],
    user: ApiUser,
) -> None:
    viewer = make_member("observa@example.com", "users.view")

    response = client.get("/auth/staff-member/")

    assert response.status_code == HTTPStatus.OK, response.content
    members = {member["email"]: member for member in body(response)}
    # el equipo, con su rol del equipo; una cuenta de la calle no aparece
    assert members[str(manager.email)]["role"]["id"] == role_of_manager(manager).pk
    assert members[str(viewer.email)]["status"] == "active"
    assert str(user.email) not in members
    assert set(members[str(viewer.email)]) == {
        "created_at",
        "email",
        "id",
        "name",
        "role",
        "status",
    }


def test_the_team_list_includes_superusers_even_without_a_team_role(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    root = ApiUser.objects.create_superuser(email="raiz@example.com", password=PASSWORD)

    members = {
        member["email"]: member for member in body(client.get("/auth/staff-member/"))
    }

    assert members[str(root.email)]["role"] is None


def test_system_roles_are_listed_first_and_marked(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    execute()

    roles = body(client.get("/auth/staff-role/"))

    assert roles[0]["name"] == "Administrador"
    assert roles[0]["system"] is True
    assert {role["name"] for role in roles if role["system"]} == {"Administrador"}


def test_creating_a_role_returns_it_with_sorted_permissions(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    response = client.post(
        "/auth/staff-role/",
        {
            "description": "Mira las solicitudes",
            "name": "Auditoría",
            "permissions": ["users.view", "guides.view"],
        },
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    created = body(response)
    assert created["name"] == "Auditoría"
    assert created["description"] == "Mira las solicitudes"
    assert created["permissions"] == ["guides.view", "users.view"]
    assert created["members"] == 0
    assert created["system"] is False
    # el segundo factor es obligatorio salvo que se diga lo contrario
    assert created["requires_two_factor"] is True

    stored = Group.objects.get(name="Auditoría")
    assert stored.profile.kind == GroupKinds.STAFF
    assert {item["name"] for item in body(client.get("/auth/staff-role/"))} >= {
        "Auditoría"
    }


def test_a_role_cannot_ask_for_a_permission_that_does_not_exist(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    response = client.post(
        "/auth/staff-role/",
        {"name": "Raro", "permissions": ["no.existe", "guides.view"]},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.permissions" in body(response)["field_errors"]
    assert not Group.objects.filter(name="Raro").exists()


def test_two_roles_cannot_share_a_name(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    make_role("Repetido")

    response = client.post("/auth/staff-role/", {"name": "Repetido", "permissions": []})

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert "body.name" in body(response)["field_errors"]


def test_a_role_needs_a_name(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    response = client.post("/auth/staff-role/", {"name": "", "permissions": []})

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_role_can_be_read_by_its_id(
    client: DMRClient,
    manager: ApiUser,
) -> None:
    own = role_of_manager(manager)

    response = client.get(f"/auth/staff-role/{own.pk}/")

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["name"] == own.name


def test_only_team_roles_are_reachable_through_the_team_endpoints(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    public = make_role("Pública", kind=GroupKinds.PUBLIC, role=AccountRoles.TURISTA)
    path = f"/auth/staff-role/{public.pk}/"

    assert client.get(path).status_code == HTTPStatus.NOT_FOUND
    assert client.put(path, {"name": "X", "permissions": []}).status_code == (
        HTTPStatus.NOT_FOUND
    )
    assert client.delete(path).status_code == HTTPStatus.NOT_FOUND
    assert Group.objects.filter(pk=public.pk).exists()


def test_editing_a_role_changes_what_its_members_can_do(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> None:
    readers = make_role("Lectores", "users.view")
    reader = make_user(email="lector@example.com")
    link(reader, readers)
    their_client = DMRClient()
    web_login(their_client, reader)
    assert their_client.get("/auth/user/").status_code == HTTPStatus.OK

    response = client.put(
        f"/auth/staff-role/{readers.pk}/",
        {
            "description": "Ahora ven guías",
            "name": "Lectores de guías",
            "permissions": ["guides.view"],
            "requires_two_factor": False,
        },
    )

    assert response.status_code == HTTPStatus.OK, response.content
    updated = body(response)
    assert updated["name"] == "Lectores de guías"
    assert updated["permissions"] == ["guides.view"]
    assert updated["members"] == 1
    # el cambio se nota en la siguiente petición, sin volver a iniciar sesión
    assert their_client.get("/auth/user/").status_code == HTTPStatus.FORBIDDEN


def test_editing_a_role_keeps_the_model_permissions_the_group_already_had(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    role = make_role("Con extras", "users.view")
    model_permission = Permission.objects.get(codename="view_apiuser")
    role.permissions.add(model_permission)  # ty: ignore[unresolved-attribute]

    response = client.put(
        f"/auth/staff-role/{role.pk}/",
        {"name": "Con extras", "permissions": ["guides.view"]},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    kept = Permission.objects.filter(group=role).values_list("codename", flat=True)
    assert set(kept) == {"guides.view", "view_apiuser"}


def test_a_person_cannot_take_staff_manage_away_from_their_own_role(
    client: DMRClient,
    manager: ApiUser,
) -> None:
    own = role_of_manager(manager)
    path = f"/auth/staff-role/{own.pk}/"

    locked_out = client.put(path, {"name": own.name, "permissions": ["users.manage"]})
    assert locked_out.status_code == HTTPStatus.FORBIDDEN, locked_out.content

    kept = client.put(
        path,
        {"name": own.name, "permissions": ["staff.manage", "guides.view"]},
    )
    assert kept.status_code == HTTPStatus.OK, kept.content


def test_staff_manage_can_move_to_another_role_the_person_also_holds(
    client: DMRClient,
    manager: ApiUser,
    make_role: Callable[..., Group],
) -> None:
    # quien conserva `staff.manage` por otro de sus roles puede quitarlo de este
    link(manager, make_role("Segundo rol", "staff.manage"))
    own = role_of_manager_by_name(manager)

    response = client.put(
        f"/auth/staff-role/{own.pk}/",
        {"name": own.name, "permissions": ["users.manage"]},
    )

    assert response.status_code == HTTPStatus.OK, response.content


def role_of_manager_by_name(manager: ApiUser) -> Group:
    return Group.objects.get(name=f"Rol de {manager.email}")


def test_system_roles_cannot_be_edited_or_deleted(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    execute()
    admin = Group.objects.get(name="Administrador")
    path = f"/auth/staff-role/{admin.pk}/"

    edit = client.put(path, {"name": "Otro nombre", "permissions": []})
    delete = client.delete(path)

    assert edit.status_code == delete.status_code == HTTPStatus.FORBIDDEN
    assert body(edit)["detail"] == SYSTEM_ROLE_DETAIL
    assert Group.objects.get(pk=admin.pk).name == "Administrador"


def test_a_role_with_members_cannot_be_deleted(
    client: DMRClient,
    manager: ApiUser,
) -> None:
    own = role_of_manager(manager)

    response = client.delete(f"/auth/staff-role/{own.pk}/")

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert Group.objects.filter(pk=own.pk).exists()


def test_an_empty_role_can_be_deleted(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    role = make_role("Vacío")

    response = client.delete(f"/auth/staff-role/{role.pk}/")

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content
    assert not Group.objects.filter(pk=role.pk).exists()


def test_an_unknown_role_is_not_found(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    assert client.get("/auth/staff-role/999999/").status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Invitación


def invite(
    client: DMRClient,
    role: Group,
    email: str = "nueva@example.com",
) -> HttpResponse:
    return client.post(
        "/auth/staff-invite/",
        {
            "email": email,
            "first_name": "Nueva",
            "last_name": "Persona",
            "role_id": role.pk,
        },
    )


def accept(
    guest: DMRClient, code: str, email: str = "nueva@example.com"
) -> HttpResponse:
    return guest.post(
        "/auth/staff-accept/",
        {"code": code, "email": email, "password": NEW_PASSWORD},
    )


def test_inviting_creates_a_pending_member_and_emails_the_code(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    role = make_role("Revisores", "guides.review")

    response = invite(client, role)

    assert response.status_code == HTTPStatus.CREATED, response.content
    data = body(response)
    assert data["email"] == "nueva@example.com"
    assert data["name"] == "Nueva Persona"
    assert data["status"] == "pending"
    assert data["role"] == {"id": role.pk, "name": "Revisores"}
    assert data["sent"] is True

    invited = ApiUser.objects.get(email="nueva@example.com")
    assert invited.status == ApiUserStatus.PENDING
    assert not invited.is_active
    assert not invited.has_usable_password()
    assert ApiUserGroups.objects.filter(api_user=invited, group=role).exists()

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["nueva@example.com"]
    assert extract_code(mail.outbox[0])


def test_the_invited_person_accepts_with_the_code_and_picks_a_password(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    invite(client, make_role("Revisores", "guides.review"))
    code = extract_code(mail.outbox[0])
    guest = DMRClient()

    response = accept(guest, code)

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content
    accepted = ApiUser.objects.get(email="nueva@example.com")
    assert accepted.status == ApiUserStatus.ACTIVE
    assert accepted.is_active
    assert accepted.verified_at is not None

    session = web_login(guest, accepted, NEW_PASSWORD)
    assert session["user"]["role"] == "admin"
    # revisar las solicitudes incluye verlas
    assert session["user"]["permissions"] == ["guides.review", "guides.view"]


def test_an_invitation_code_works_only_once(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    invite(client, make_role("Revisores"))
    code = extract_code(mail.outbox[0])

    first = accept(DMRClient(), code)
    again = accept(DMRClient(), code)

    assert first.status_code == HTTPStatus.NO_CONTENT
    assert again.status_code == HTTPStatus.BAD_REQUEST


def test_a_wrong_code_and_a_missing_invitation_get_the_same_answer(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    invite(client, make_role("Revisores"))
    real = extract_code(mail.outbox[0])
    wrong = "000000" if real != "000000" else "111111"
    guest = DMRClient()

    bad_code = accept(guest, wrong)
    nobody = accept(guest, real, email="nadie@example.com")

    assert bad_code.status_code == nobody.status_code == HTTPStatus.BAD_REQUEST
    assert body(bad_code) == body(nobody)
    assert ApiUser.objects.get(email="nueva@example.com").status == (
        ApiUserStatus.PENDING
    )


def test_five_wrong_codes_burn_the_invitation_code(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    invite(client, make_role("Revisores"))
    real = extract_code(mail.outbox[0])
    wrong = "000000" if real != "000000" else "111111"
    guest = DMRClient()

    for _ in range(5):
        assert accept(guest, wrong).status_code == HTTPStatus.BAD_REQUEST

    assert accept(guest, real).status_code == HTTPStatus.BAD_REQUEST


def test_accepting_needs_a_strong_password(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    invite(client, make_role("Revisores"))
    code = extract_code(mail.outbox[0])

    response = DMRClient().post(
        "/auth/staff-accept/",
        {"code": code, "email": "nueva@example.com", "password": "12345678"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert ApiUser.objects.get(email="nueva@example.com").status == (
        ApiUserStatus.PENDING
    )
    # el código no se gasta con una contraseña floja: se puede volver a intentar
    assert accept(DMRClient(), code).status_code == HTTPStatus.NO_CONTENT


def test_accepting_does_not_need_a_session(client: DMRClient) -> None:
    response = client.post(
        "/auth/staff-accept/",
        {"code": "123456", "email": "nadie@example.com", "password": NEW_PASSWORD},
    )

    # la respuesta es la de un código malo, no la de falta de sesión
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_inviting_an_existing_account_is_a_conflict(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(email="ya@example.com")

    response = invite(client, make_role("Revisores"), email="ya@example.com")

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert "body.email" in body(response)["field_errors"]
    assert mail.outbox == []


def roles_of(user: ApiUser) -> list[int]:
    return list(
        ApiUserGroups.objects.filter(api_user=user).values_list("group_id", flat=True)
    )


def test_inviting_again_after_the_wait_resends_the_code_and_swaps_the_role(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = make_role("Uno", "guides.view")
    second = make_role("Dos", "users.view")

    invite(client, first)
    # ya pasó la espera entre un correo y el siguiente (la fila del código no se
    # puede editar, así que se acorta la espera)
    monkeypatch.setattr(
        verification,
        "CONFIG",
        CONFIG.model_copy(update={"VERIFICATION_RESEND_AFTER": timedelta(0)}),
    )

    again = invite(client, second)

    assert again.status_code == HTTPStatus.CREATED, again.content
    assert body(again)["sent"] is True
    assert len(mail.outbox) == 2
    assert roles_of(ApiUser.objects.get(email="nueva@example.com")) == [second.pk]

    # el código nuevo reemplaza al anterior
    guest = DMRClient()
    assert accept(guest, extract_code(mail.outbox[0])).status_code == (
        HTTPStatus.BAD_REQUEST
    )
    assert accept(guest, extract_code(mail.outbox[1])).status_code == (
        HTTPStatus.NO_CONTENT
    )


def test_inviting_again_inside_the_wait_swaps_the_role_without_a_new_email(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    first = make_role("Uno", "guides.view")
    second = make_role("Dos", "users.view")

    invite(client, first)
    again = invite(client, second)

    assert again.status_code == HTTPStatus.CREATED, again.content
    # el portal sabe que no salió otro correo y le dice a la persona que use el último
    assert body(again)["sent"] is False
    assert len(mail.outbox) == 1
    assert roles_of(ApiUser.objects.get(email="nueva@example.com")) == [second.pk]
    assert accept(DMRClient(), extract_code(mail.outbox[0])).status_code == (
        HTTPStatus.NO_CONTENT
    )


def test_an_invitation_needs_an_existing_team_role(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    public = make_role("Pública", kind=GroupKinds.PUBLIC, role=AccountRoles.TURISTA)

    for role_id in (public.pk, 999_999):
        response = client.post(
            "/auth/staff-invite/",
            {"email": "nueva@example.com", "first_name": "Nueva", "role_id": role_id},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
        assert "body.role_id" in body(response)["field_errors"]

    assert not ApiUser.objects.filter(email="nueva@example.com").exists()
    assert mail.outbox == []


########################################################################################
# Estado de una cuenta


def set_status(client: DMRClient, user: ApiUser, status: str) -> HttpResponse:
    return client.post(
        "/auth/user-status/",
        {"status": status, "user_id": str(user.pk)},
    )


def test_suspending_cuts_the_sessions_and_reactivating_lets_the_person_back(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
) -> None:
    target = make_user(email="objetivo@example.com")
    theirs = DMRClient()
    access = body(theirs.post("/auth/mobile/login/", credentials(target)))["access"]
    assert theirs.get("/auth/profile/", headers=bearer(access)).status_code == (
        HTTPStatus.OK
    )

    suspended = set_status(client, target, "suspended")

    assert suspended.status_code == HTTPStatus.OK, suspended.content
    assert body(suspended)["status"] == "suspended"
    # la sesión que ya estaba abierta se corta de inmediato
    assert theirs.get("/auth/profile/", headers=bearer(access)).status_code == (
        HTTPStatus.UNAUTHORIZED
    )
    assert theirs.post("/auth/mobile/login/", credentials(target)).status_code == (
        HTTPStatus.FORBIDDEN
    )

    reactivated = set_status(client, target, "active")

    assert reactivated.status_code == HTTPStatus.OK, reactivated.content
    assert body(reactivated)["status"] == "active"
    sleep(1.1)  # el `iat` de las credenciales llega al segundo
    assert theirs.post("/auth/mobile/login/", credentials(target)).status_code == (
        HTTPStatus.OK
    )


@pytest.mark.parametrize("status", ["closing", "expelled", "pending"])
def test_only_active_and_suspended_can_be_asked_for(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
    status: str,
) -> None:
    target = make_user(email="objetivo@example.com")

    response = set_status(client, target, status)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert ApiUser.objects.get(pk=target.pk).status == ApiUserStatus.ACTIVE


def test_a_person_cannot_change_their_own_status(
    client: DMRClient,
    manager: ApiUser,
) -> None:
    response = set_status(client, manager, "suspended")

    assert response.status_code == HTTPStatus.FORBIDDEN, response.content
    assert ApiUser.objects.get(pk=manager.pk).status == ApiUserStatus.ACTIVE


def test_a_pending_invitation_has_no_status_to_change(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
) -> None:
    invite(client, make_role("Revisores"))
    invited = ApiUser.objects.get(email="nueva@example.com")

    response = set_status(client, invited, "suspended")

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content


def test_an_account_in_a_closing_state_is_not_changed_from_here(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
) -> None:
    closing = make_user(email="baja@example.com", status="closing")

    response = set_status(client, closing, "active")

    assert response.status_code == HTTPStatus.CONFLICT, response.content


def test_an_unknown_person_is_not_found(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    response = client.post(
        "/auth/user-status/",
        {"status": "suspended", "user_id": str(uuid4())},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_a_superuser_account_is_only_managed_by_a_superuser(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
) -> None:
    root = make_user(email="root@example.com", is_superuser=True)

    response = set_status(client, root, "suspended")

    assert response.status_code == HTTPStatus.FORBIDDEN, response.content
    assert ApiUser.objects.get(pk=root.pk).status == ApiUserStatus.ACTIVE


def test_the_last_active_super_admin_cannot_be_suspended(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
) -> None:
    execute()
    admins = Group.objects.get(name="Administrador")
    root = make_user(email="root@example.com")
    link(root, admins)

    blocked = set_status(client, root, "suspended")

    assert blocked.status_code == HTTPStatus.CONFLICT, blocked.content
    assert body(blocked)["detail"] == LAST_ADMIN_DETAIL

    # con otra persona activa en el rol, ya se puede
    second = make_user(email="segunda@example.com")
    link(second, admins)

    assert set_status(client, root, "suspended").status_code == HTTPStatus.OK


########################################################################################
# Rol de una persona


def set_role(client: DMRClient, user: ApiUser, role: Group) -> HttpResponse:
    return client.post(
        "/auth/user-role/",
        {"role_id": role.pk, "user_id": str(user.pk)},
    )


def test_changing_the_role_leaves_a_single_team_role(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_member: Callable[..., ApiUser],
    make_role: Callable[..., Group],
) -> None:
    member = make_member("miembro@example.com", "guides.view")
    newer = make_role("Nuevo rol", "guides.decide")

    response = set_role(client, member, newer)

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["role"] == {"id": newer.pk, "name": "Nuevo rol"}
    assert list(
        ApiUserGroups.objects.filter(api_user=member).values_list("group_id", flat=True)
    ) == [newer.pk]


def test_changing_the_role_leaves_groups_of_other_kinds_alone(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_member: Callable[..., ApiUser],
    make_role: Callable[..., Group],
) -> None:
    member = make_member("miembro@example.com", "guides.view")
    public = make_role("Pública", kind=GroupKinds.PUBLIC, role=AccountRoles.TURISTA)
    link(member, public)

    set_role(client, member, make_role("Nuevo rol"))

    assert ApiUserGroups.objects.filter(api_user=member, group=public).exists()
    assert ApiUserGroups.objects.filter(api_user=member).count() == 2


def test_nobody_changes_their_own_role(
    client: DMRClient,
    manager: ApiUser,
    make_role: Callable[..., Group],
) -> None:
    response = set_role(client, manager, make_role("Otro"))

    assert response.status_code == HTTPStatus.FORBIDDEN, response.content


def test_a_person_outside_the_team_has_no_team_role_to_change(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> None:
    outsider = make_user(email="afuera@example.com")

    response = set_role(client, outsider, make_role("Otro"))

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
    assert not ApiUserGroups.objects.filter(api_user=outsider).exists()


def test_the_new_role_must_be_a_team_role(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_member: Callable[..., ApiUser],
    make_role: Callable[..., Group],
) -> None:
    member = make_member("miembro@example.com", "guides.view")
    public = make_role("Pública", kind=GroupKinds.PUBLIC, role=AccountRoles.TURISTA)

    response = set_role(client, member, public)

    assert response.status_code == HTTPStatus.NOT_FOUND, response.content


def test_the_last_super_admin_cannot_be_moved_to_another_role(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> None:
    execute()
    admins = Group.objects.get(name="Administrador")
    root = make_user(email="root@example.com")
    link(root, admins)
    other = make_role("Otro")

    blocked = set_role(client, root, other)

    assert blocked.status_code == HTTPStatus.CONFLICT, blocked.content
    assert body(blocked)["detail"] == LAST_ADMIN_DETAIL

    # con otra persona activa en el rol, ya se puede
    link(make_user(email="segunda@example.com"), admins)

    assert set_role(client, root, other).status_code == HTTPStatus.OK


def test_anyone_can_be_promoted_to_super_admin_only_by_who_manages_the_team(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_member: Callable[..., ApiUser],
) -> None:
    execute()
    member = make_member("miembro@example.com", "guides.view")

    response = set_role(client, member, Group.objects.get(name="Administrador"))

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["role"]["name"] == "Administrador"


########################################################################################
# Contraseña de otra persona


def test_a_manager_can_send_a_password_reset_code_to_someone(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
) -> None:
    target = make_user(email="objetivo@example.com")

    response = client.post("/auth/user-password-reset/", {"user_id": str(target.pk)})

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["objetivo@example.com"]

    # el código sirve en el flujo normal de recuperación, y quien lo manda no
    # llega a ver ni la contraseña nueva ni el código
    reset = DMRClient().post(
        "/auth/password-reset/",
        {
            "code": extract_code(mail.outbox[0]),
            "email": "objetivo@example.com",
            "password": NEW_PASSWORD,
        },
    )
    assert reset.status_code == HTTPStatus.NO_CONTENT, reset.content
    assert ApiUser.objects.get(pk=target.pk).check_password(NEW_PASSWORD)
    assert not ApiUser.objects.get(pk=target.pk).check_password(PASSWORD)


@pytest.mark.parametrize("status", ["pending", "suspended"])
def test_no_reset_code_goes_to_an_account_that_cannot_operate(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
    status: str,
) -> None:
    target = make_user(email="objetivo@example.com", status=status)

    response = client.post("/auth/user-password-reset/", {"user_id": str(target.pk)})

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert mail.outbox == []


def test_a_reset_code_for_an_unknown_person_is_not_found(
    client: DMRClient,
    manager: ApiUser,  # ruff: ignore[unused-function-argument]
) -> None:
    response = client.post("/auth/user-password-reset/", {"user_id": str(uuid4())})

    assert response.status_code == HTTPStatus.NOT_FOUND
