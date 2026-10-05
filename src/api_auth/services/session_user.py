from typing import TYPE_CHECKING, Any

from api_auth.enums import ApiUserTypes
from api_auth.schemas.group import GroupInlineGet
from api_auth.schemas.session import SessionUserGet, TwoFactorState

from .two_factor import has_two_factor

if TYPE_CHECKING:
    from typing import Final

    from django.contrib.auth.models import Group

    from api_auth.models import ApiUser
    from api_auth.schemas.session import Role

########################################################################################

# - mientras los roles no sean datos (F2), el papel sale del nombre del grupo
ROLE_BY_GROUP: Final[dict[str, Role]] = {
    ApiUserTypes.ADMIN: "admin",
    ApiUserTypes.CLIENT: "turista",
    ApiUserTypes.STAFF: "admin",
}

# - los papeles de la calle (app móvil); el resto administra desde el portal
PUBLIC_ROLES: Final[frozenset[Role]] = frozenset({"guia", "traductor", "turista"})

########################################################################################


def resolve_role(user: ApiUser, groups: list[Group]) -> Role | None:
    if user.is_superuser:
        return "admin"

    for group in groups:
        role: Role | None = ROLE_BY_GROUP.get(group.name)

        if role is not None:
            return role

    return None


async def build_session_user(user: ApiUser) -> SessionUserGet:
    groups: list[Group] = [g async for g in user.groups.order_by("name")]  # ty: ignore[unresolved-attribute]

    # los atributos de los modelos de Django no tienen tipos para ty: aquí se leen sin
    # ellos, y los valores validan contra `SessionUserGet` al construirlo
    account: Any = user

    return SessionUserGet(
        birth_date=account.birth_date,
        created_at=account.created_at,
        email=account.email,
        first_name=account.first_name,
        groups=tuple(GroupInlineGet(id=g.pk, name=str(g.name)) for g in groups),
        id=account.pk,
        last_name=account.last_name,
        name=account.display_name,
        nationality=account.nationality,
        organization_id=None,
        permissions=tuple(sorted(await user.aget_all_permissions())),
        role=resolve_role(user, groups),
        status=account.status,
        two_factor=TwoFactorState(
            enabled=await has_two_factor(user),
            required=False,
        ),
        username=account.username,
        verified=account.verified_at is not None,
    )
