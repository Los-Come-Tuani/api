from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.models import ApiUserGroups
from api_organizations.models import Business, CulturalInstitution
from api_roles.models import RoleAssignment
from api_territory.models import Municipality

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from django.contrib.auth.models import Group

    from api_auth.models import ApiUser

########################################################################################

type ScopeObject = Business | CulturalInstitution | Municipality


# La organización sobre la que actúa una persona: lo que la sesión muestra.
@dataclass(frozen=True, slots=True)
class OrganizationRef:
    id: UUID
    kind: str
    name: str
    verified_at: datetime | None


def scope_field(scope_object: ScopeObject | None) -> dict[str, ScopeObject]:
    # el campo de `asignacion_rol` que corresponde a cada clase de objeto
    match scope_object:
        case None:
            return {}
        case Business():
            return {"business": scope_object}
        case CulturalInstitution():
            return {"institution": scope_object}
        case Municipality():
            return {"municipality": scope_object}


# Da un rol sobre un objeto; la base comprueba que el ámbito sea el que el rol exige. La
# persona entra también al grupo del rol: de ahí salen su papel y la superficie por la
# que entra (`api_auth.services.roles`).
def grant_role_sync(
    *,
    granted_by: ApiUser,
    role: Group,
    scope_object: ScopeObject | None,
    user: ApiUser,
) -> RoleAssignment:
    with atomic():
        assignment: RoleAssignment = RoleAssignment.objects.create(
            granted_by=granted_by,
            role=role,
            user=user,
            **scope_field(scope_object),
        )

        ApiUserGroups.objects.get_or_create(api_user=user, group=role)

    return assignment


# Escribe la fecha de revocación; solo sale del grupo quien ya no conserva el rol.
def revoke_role_sync(assignment: RoleAssignment) -> None:
    with atomic():
        RoleAssignment.objects.filter(
            pk=assignment.pk,
            revoked_at__isnull=True,
        ).update(revoked_at=now())

        still_holds: bool = RoleAssignment.objects.filter(
            revoked_at__isnull=True,
            role=assignment.role,
            user=assignment.user,
        ).exists()

        if not still_holds:
            ApiUserGroups.objects.filter(
                api_user=assignment.user,
                group=assignment.role,
            ).delete()


# La organización de la asignación vigente más antigua de la persona, si tiene alguna.
def organization_of_sync(user: ApiUser) -> OrganizationRef | None:
    found: Any = (
        RoleAssignment.objects
        .select_related("business", "institution", "municipality")
        .filter(revoked_at__isnull=True, user=user)
        .exclude(
            business__isnull=True,
            institution__isnull=True,
            municipality__isnull=True,
        )
        .order_by("granted_at")
        .first()
    )

    if found is None:
        return None

    for kind, record in (
        ("business", found.business),
        ("institution", found.institution),
        ("municipality", found.municipality),
    ):
        if record is not None:
            return OrganizationRef(
                id=record.pk,
                kind=kind,
                name=str(record.name),
                verified_at=record.verified_at,
            )

    return None
