from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group
from django.db import DatabaseError
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.enums import GroupKinds, GroupScopes
from api_auth.models import ApiGroupProfile, ApiUserGroups
from api_auth.seeder import SYSTEM_ROLES
from api_catalogs.models import BusinessType
from api_organizations.models import Business
from api_roles.models import RoleAssignment
from api_roles.services import grant_role_sync, organization_of_sync, revoke_role_sync
from api_territory.models import City, Municipality

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db


def rejected(call: Callable[[], Any]) -> None:
    # un savepoint propio: la base aborta la transacción entera al rechazar una fila
    with pytest.raises(DatabaseError), atomic():
        call()


def role(name: str) -> Group:
    return Group.objects.get(name=name)


@pytest.fixture
def city() -> City:
    return City.objects.get(code="leon")


def make_business(city: City, ruc: str = "J0310000000001") -> Business:
    return Business.objects.create(
        address="Frente a la catedral",
        business_type=BusinessType.objects.get(code="restaurante"),
        city=city,
        latitude=Decimal("12.437900"),
        longitude=Decimal("-86.878000"),
        name="El Sacuanjoche",
        phone="2311-0000",
        ruc=ruc,
    )


@pytest.fixture
def business(city: City) -> Business:
    return make_business(city)


@pytest.fixture
def municipality(city: City) -> Municipality:
    return Municipality.objects.create(
        city=city,
        contact_email="alcaldia@example.com",
        document_key="documentos/acta.pdf",
        name="Alcaldía de León",
        phone="2311-2222",
    )


########################################################################################
# Ámbito de cada rol


def test_each_operator_role_demands_its_own_scope_and_the_rest_are_global() -> None:
    scopes = {
        spec.name: ApiGroupProfile.objects.get(group__name=spec.name).scope
        for spec in SYSTEM_ROLES
    }

    assert scopes["Negocio"] == GroupScopes.BUSINESS
    assert scopes["Alcaldía"] == GroupScopes.MUNICIPALITY
    assert scopes["Institución"] == GroupScopes.INSTITUTION
    assert {
        scope
        for name, scope in scopes.items()
        if name not in {"Negocio", "Alcaldía", "Institución"}
    } == {GroupScopes.GLOBAL}


def test_only_an_operator_role_can_have_a_scope() -> None:
    staff = Group.objects.create(name="Equipo con ámbito")

    rejected(
        lambda: ApiGroupProfile.objects.create(
            group=staff,
            kind=GroupKinds.STAFF,
            role="admin",
            scope=GroupScopes.BUSINESS,
        )
    )


########################################################################################
# Asignación


def test_a_role_is_assigned_over_the_object_it_demands(
    business: Business,
    municipality: Municipality,
    user: ApiUser,
) -> None:
    RoleAssignment.objects.create(
        business=business,
        granted_by=user,
        role=role("Negocio"),
        user=user,
    )
    RoleAssignment.objects.create(
        granted_by=user,
        municipality=municipality,
        role=role("Alcaldía"),
        user=user,
    )

    assert RoleAssignment.objects.filter(user=user).count() == 2


@pytest.mark.parametrize(
    ("role_name", "owner"),
    [
        # un operador de comercio no se asigna a una alcaldía
        ("Negocio", "municipality"),
        # un operador de alcaldía no se asigna a un comercio
        ("Alcaldía", "business"),
        # un operador sin ámbito
        ("Negocio", None),
        # un rol del equipo con ámbito
        ("Administrador", "business"),
    ],
)
def test_the_scope_must_be_the_one_the_role_demands(
    business: Business,
    municipality: Municipality,
    user: ApiUser,
    owner: str | None,
    role_name: str,
) -> None:
    scope = {"business": business, "municipality": municipality}.get(owner or "")
    fields = {owner: scope} if owner else {}

    rejected(
        lambda: RoleAssignment.objects.create(
            granted_by=user,
            role=role(role_name),
            user=user,
            **fields,
        )
    )


def test_a_global_role_has_no_scope(
    user: ApiUser, make_user: Callable[..., ApiUser]
) -> None:
    admin = make_user(email="admin@example.com")

    RoleAssignment.objects.create(
        granted_by=user, role=role("Administrador"), user=admin
    )

    assert RoleAssignment.objects.filter(user=admin, business__isnull=True).count() == 1


def test_two_scopes_at_once_are_impossible(
    business: Business,
    municipality: Municipality,
    user: ApiUser,
) -> None:
    rejected(
        lambda: RoleAssignment.objects.create(
            business=business,
            granted_by=user,
            municipality=municipality,
            role=role("Negocio"),
            user=user,
        )
    )


def test_the_same_role_is_not_held_twice_over_the_same_object(
    business: Business,
    user: ApiUser,
) -> None:
    assignment = RoleAssignment.objects.create(
        business=business,
        granted_by=user,
        role=role("Negocio"),
        user=user,
    )

    rejected(
        lambda: RoleAssignment.objects.create(
            business=business,
            granted_by=user,
            role=role("Negocio"),
            user=user,
        )
    )

    # revocada, se puede volver a dar: es otra fila
    RoleAssignment.objects.filter(pk=assignment.pk).update(revoked_at=now())
    RoleAssignment.objects.create(
        business=business,
        granted_by=user,
        role=role("Negocio"),
        user=user,
    )

    assert RoleAssignment.objects.filter(user=user).count() == 2


def test_a_revocation_is_not_undone_and_an_assignment_is_not_deleted(
    business: Business,
    user: ApiUser,
) -> None:
    assignment = RoleAssignment.objects.create(
        business=business,
        granted_by=user,
        role=role("Negocio"),
        user=user,
    )
    RoleAssignment.objects.filter(pk=assignment.pk).update(revoked_at=now())

    rejected(
        lambda: RoleAssignment.objects.filter(pk=assignment.pk).update(revoked_at=None)
    )
    rejected(lambda: RoleAssignment.objects.filter(pk=assignment.pk).delete())


########################################################################################
# Servicios


def test_granting_a_role_also_puts_the_person_in_its_group(
    business: Business,
    user: ApiUser,
) -> None:
    assignment = grant_role_sync(
        granted_by=user,
        role=role("Negocio"),
        scope_object=business,
        user=user,
    )

    assert assignment.revoked_at is None
    assert ApiUserGroups.objects.filter(api_user=user, group=role("Negocio")).exists()


def test_revoking_leaves_the_group_only_when_no_other_assignment_keeps_it(
    city: City,
    business: Business,
    user: ApiUser,
) -> None:
    other = make_business(city, "J0310000000002")
    first = grant_role_sync(
        granted_by=user, role=role("Negocio"), scope_object=business, user=user
    )
    second = grant_role_sync(
        granted_by=user, role=role("Negocio"), scope_object=other, user=user
    )

    revoke_role_sync(first)
    assert ApiUserGroups.objects.filter(api_user=user, group=role("Negocio")).exists()

    revoke_role_sync(second)
    assert not ApiUserGroups.objects.filter(
        api_user=user, group=role("Negocio")
    ).exists()


def test_the_organization_of_a_person_comes_from_the_live_assignment(
    business: Business,
    user: ApiUser,
) -> None:
    assert organization_of_sync(user) is None

    assignment = grant_role_sync(
        granted_by=user,
        role=role("Negocio"),
        scope_object=business,
        user=user,
    )

    reference = organization_of_sync(user)
    assert reference is not None
    assert (reference.id, reference.kind, reference.name) == (
        business.pk,
        "business",
        "El Sacuanjoche",
    )
    assert reference.verified_at is None

    revoke_role_sync(assignment)
    assert organization_of_sync(user) is None


def test_the_schema_uses_the_spanish_name_of_the_domain_model() -> None:
    assert RoleAssignment._meta.db_table == "asignacion_rol"  # ruff: ignore[private-member-access]
