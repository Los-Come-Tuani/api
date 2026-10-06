from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.transaction import atomic

from api_auth.catalog import (
    CATALOG,
    FunctionalPermissions as P,
)
from api_auth.enums import AccountRoles, ApiUserTypes, GroupKinds
from api_auth.models import ApiGroupProfile

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

########################################################################################


@dataclass(frozen=True, slots=True)
class RoleSpec:
    name: str
    kind: str
    role: str
    description: str = ""
    permissions: Sequence[str] = field(default_factory=tuple)
    requires_two_factor: bool = False
    is_system: bool = False


# - los grupos que el sistema necesita: no se editan ni se borran desde el portal
SYSTEM_ROLES: Final[Sequence[RoleSpec]] = (
    RoleSpec(
        description="Super admin: tiene todo y no se edita ni se borra.",
        is_system=True,
        kind=GroupKinds.STAFF,
        name=ApiUserTypes.ADMIN.value,
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Turistas de la app.",
        is_system=True,
        kind=GroupKinds.PUBLIC,
        name=ApiUserTypes.CLIENT.value,
        role=AccountRoles.TURISTA,
    ),
    RoleSpec(
        description="Guías de la app.",
        is_system=True,
        kind=GroupKinds.PUBLIC,
        name="Guía",
        role=AccountRoles.GUIA,
    ),
    RoleSpec(
        description="Traductores de la app.",
        is_system=True,
        kind=GroupKinds.PUBLIC,
        name="Traductor",
        role=AccountRoles.TRADUCTOR,
    ),
    RoleSpec(
        description="Negocios que administran su lugar desde el portal.",
        is_system=True,
        kind=GroupKinds.OPERATOR,
        name="Negocio",
        role=AccountRoles.NEGOCIO,
    ),
    RoleSpec(
        description="Alcaldías que administran sus lugares desde el portal.",
        is_system=True,
        kind=GroupKinds.OPERATOR,
        name="Alcaldía",
        role=AccountRoles.ALCALDIA,
    ),
    RoleSpec(
        description="Instituciones que administran sus lugares desde el portal.",
        is_system=True,
        kind=GroupKinds.OPERATOR,
        name="Institución",
        role=AccountRoles.INSTITUCION,
    ),
)

# - roles del equipo de ejemplo: se crean una vez y después se editan o se borran con
#   libertad (volver a migrar no los restaura)
EXAMPLE_ROLES: Final[Sequence[RoleSpec]] = (
    RoleSpec(
        description="Equipo sin permisos asignados todavía.",
        kind=GroupKinds.STAFF,
        name=ApiUserTypes.STAFF.value,
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Ve las solicitudes de guías y traductores, sin poder revisarlas.",
        kind=GroupKinds.STAFF,
        name="Observador de guías y traductores",
        permissions=(P.GUIDES_VIEW,),
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Revisa documentos y antecedentes de guías y traductores.",
        kind=GroupKinds.STAFF,
        name="Verificador",
        permissions=(P.GUIDES_REVIEW,),
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Revisa y da la decisión final sobre guías y traductores.",
        kind=GroupKinds.STAFF,
        name="Aprobador",
        permissions=(P.GUIDES_REVIEW, P.GUIDES_DECIDE),
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Ve las organizaciones y sus solicitudes, sin poder cambiarlas.",
        kind=GroupKinds.STAFF,
        name="Observador de negocios",
        permissions=(P.ORGANIZATIONS_VIEW,),
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Admite y administra negocios y alcaldías.",
        kind=GroupKinds.STAFF,
        name="Gestor de organizaciones",
        permissions=(P.ORGANIZATIONS_REVIEW, P.ORGANIZATIONS_MANAGE),
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
    RoleSpec(
        description="Modera cupones, eventos y campañas de insignias.",
        kind=GroupKinds.STAFF,
        name="Moderador de contenido",
        permissions=(P.CONTENT_MODERATE,),
        requires_two_factor=True,
        role=AccountRoles.ADMIN,
    ),
)

########################################################################################


def seed_permissions() -> dict[str, Permission]:
    # los permisos funcionales viven con el tipo de contenido de `ApiGroupProfile`: así
    # se piden como `apiauth.guides.review` y no chocan con los de los modelos
    content_type: ContentType = ContentType.objects.get_for_model(ApiGroupProfile)

    seeded: dict[str, Permission] = {}

    for info in CATALOG:
        permission, created = Permission.objects.get_or_create(
            codename=info.id,
            content_type=content_type,
            defaults={"name": info.label[:255]},
        )

        if not created and permission.name != info.label[:255]:
            permission.name = info.label[:255]
            permission.save(update_fields=["name"])

        seeded[info.id] = permission

    return seeded


def seed_role(spec: RoleSpec, permissions: dict[str, Permission]) -> None:
    group, _ = Group.objects.get_or_create(name=spec.name)

    if spec.is_system:
        # lo que el sistema garantiza de un grupo de sistema se vuelve a fijar cada vez
        ApiGroupProfile.objects.update_or_create(
            group=group,
            defaults={
                "description": spec.description,
                "is_system": True,
                "kind": spec.kind,
                "requires_two_factor": spec.requires_two_factor,
                "role": spec.role,
            },
        )

        return

    _, created = ApiGroupProfile.objects.get_or_create(
        group=group,
        defaults={
            "description": spec.description,
            "kind": spec.kind,
            "requires_two_factor": spec.requires_two_factor,
            "role": spec.role,
        },
    )

    if created and spec.permissions:
        group.permissions.add(*(permissions[p] for p in spec.permissions))


@atomic
def execute() -> None:
    permissions: dict[str, Permission] = seed_permissions()

    for spec in SYSTEM_ROLES:
        seed_role(spec, permissions)

    for spec in EXAMPLE_ROLES:
        seed_role(spec, permissions)

    # el super admin tiene todo, también lo funcional
    Group.objects.get(
        name=ApiUserTypes.ADMIN.value,
    ).permissions.add(*Permission.objects.all())
