from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from dmr.test import DMRClient
from pgtransaction.transaction import Atomic

from api_auth.enums import AccountRoles, GroupKinds, GroupScopes
from api_auth.models import ApiGroupProfile, ApiUser, ApiUserGroups
from api_auth.seeder import seed_permissions
from api_auth.services import totp
from api_tests.helpers import PASSWORD

# - el ámbito que exige cada papel de operador
OPERATOR_SCOPES: Final[dict[str, str]] = {
    AccountRoles.ALCALDIA: GroupScopes.MUNICIPALITY,
    AccountRoles.INSTITUCION: GroupScopes.INSTITUTION,
    AccountRoles.NEGOCIO: GroupScopes.BUSINESS,
}

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Final

    from django.conf import LazySettings

########################################################################################


class Clock:
    """Reloj del TOTP controlable: cada paso son `TOTP_PERIOD` segundos."""

    def __init__(self, step: int) -> None:
        self.step: int = step

    def advance(self, steps: int = 1) -> None:
        self.step += steps


########################################################################################


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    # los contadores de throttling viven en la caché y se compartirían entre pruebas
    cache.clear()


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings: LazySettings) -> None:
    # PBKDF2 es lento a propósito (casi un segundo por contraseña en una máquina
    # normal) y cada prueba crea y verifica cuentas; las pruebas no miden el hash
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _no_transaction_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    # pytest-django envuelve cada prueba en una transacción, y `pgtransaction` no
    # permite reintentos dentro de una transacción anidada (lo que usan las
    # operaciones de crear y actualizar). En producción sí reintentan.
    monkeypatch.setattr(Atomic, "retry", property(lambda _: 0))


@pytest.fixture
def client() -> DMRClient:
    return DMRClient()


@pytest.fixture
def csrf_client() -> DMRClient:
    # como un navegador: el flujo web exige la cabecera CSRF
    return DMRClient(enforce_csrf_checks=True)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock(step=60_000)

    monkeypatch.setattr(totp, "current_step", lambda: fake.step)

    return fake


@pytest.fixture
def make_user(db: None) -> Callable[..., ApiUser]:  # ruff: ignore[unused-function-argument]
    def factory(
        email: str = "ana@example.com",
        password: str = PASSWORD,
        **extra: object,
    ) -> ApiUser:
        return ApiUser.objects.create_user(
            email=email,
            password=password,
            **extra,
        )

    return factory


@pytest.fixture
def user(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user()


@pytest.fixture
def make_role(db: None) -> Callable[..., Group]:  # ruff: ignore[unused-function-argument]
    # los permisos funcionales existen una vez sembrado el catálogo
    functional: dict[str, Permission] = seed_permissions()

    def factory(
        name: str,
        *permissions: str,
        kind: str = GroupKinds.STAFF,
        requires_two_factor: bool = False,
        role: str = AccountRoles.ADMIN,
    ) -> Group:
        group = Group.objects.create(name=name)

        ApiGroupProfile.objects.create(
            group=group,
            kind=kind,
            requires_two_factor=requires_two_factor,
            role=role,
            # el operador de una organización exige el ámbito de su organización
            scope=OPERATOR_SCOPES.get(role, GroupScopes.GLOBAL)
            if kind == GroupKinds.OPERATOR
            else GroupScopes.GLOBAL,
        )

        group.permissions.add(*(functional[codename] for codename in permissions))

        return group

    return factory


@pytest.fixture
def make_member(
    make_role: Callable[..., Group],
    make_user: Callable[..., ApiUser],
) -> Callable[..., ApiUser]:
    # una persona del equipo con un rol que da exactamente esos permisos
    def factory(
        email: str = "equipo@example.com",
        *permissions: str,
        requires_two_factor: bool = False,
    ) -> ApiUser:
        member = make_user(email=email)

        ApiUserGroups.objects.create(
            api_user=member,
            group=make_role(
                f"Rol de {email}",
                *permissions,
                requires_two_factor=requires_two_factor,
            ),
        )

        return member

    return factory
