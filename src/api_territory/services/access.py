from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import Q

from api_auth.services.roles import functional_permissions_sync
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError
from api_roles.services import OrganizationRef, organization_of_sync

if TYPE_CHECKING:
    from api_auth.models import ApiUser

########################################################################################


# Quién actúa: sus permisos del equipo y, si opera una organización ya verificada, cuál.
# Una organización todavía en revisión no administra nada.
@dataclass(frozen=True, slots=True)
class Actor:
    user: ApiUser
    permissions: frozenset[str]
    organization: OrganizationRef | None

    def can(self, *any_of: str) -> bool:
        return not self.permissions.isdisjoint(any_of)

    def operates(self, kind: str) -> bool:
        return self.organization is not None and self.organization.kind == kind


def actor_sync(user: ApiUser) -> Actor:
    organization: OrganizationRef | None = organization_of_sync(user)

    if organization is not None and organization.verified_at is None:
        organization = None

    return Actor(
        organization=organization,
        permissions=functional_permissions_sync(user),
        user=user,
    )


# Lo que es de la organización de quien actúa: el campo de dueño de su clase.
def owned_by(organization: OrganizationRef, prefix: str = "") -> Q:
    return Q(**{f"{prefix}{organization.kind}_id": organization.id})


def invalid(field: str, message: str) -> BadRequestError:
    return BadRequestError(
        field_errors={field: message},
        type=BadRequestErrorTypes.FAILED_VALIDATION,
    ).scoped(RequestScopes.BODY)
