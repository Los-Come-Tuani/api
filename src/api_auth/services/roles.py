from typing import TYPE_CHECKING, Final

from asgiref.sync import sync_to_async
from django.contrib.auth.models import Permission

from api_auth.catalog import ALL_IDS, expand_implied
from api_auth.enums import AccountRoles, GroupKinds, Surfaces
from api_auth.models import ApiGroupProfile
from api_exceptions.errors import ForbiddenError

from .two_factor import has_two_factor

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from api_auth.models import ApiUser
    from api_utils.types import UsableHttpRequest

########################################################################################

# - de más a menos poderoso: si una cuenta tiene varios papeles, se muestra el primero
ROLE_PRIORITY: Final[Sequence[str]] = (
    AccountRoles.ADMIN.value,
    AccountRoles.ALCALDIA.value,
    AccountRoles.INSTITUCION.value,
    AccountRoles.NEGOCIO.value,
    AccountRoles.GUIA.value,
    AccountRoles.TRADUCTOR.value,
    AccountRoles.TURISTA.value,
)

# - los papeles de la calle (app móvil); el resto administra desde el portal
PUBLIC_ROLES: Final[frozenset[str]] = frozenset({
    AccountRoles.GUIA.value,
    AccountRoles.TRADUCTOR.value,
    AccountRoles.TURISTA.value,
})

# - por dónde entra cada clase de grupo (RF-S-08)
SURFACES_BY_KIND: Final[Mapping[str, frozenset[str]]] = {
    GroupKinds.OPERATOR.value: frozenset({Surfaces.WEB.value}),
    GroupKinds.PUBLIC.value: frozenset({Surfaces.MOBILE.value}),
    GroupKinds.STAFF.value: frozenset({Surfaces.WEB.value}),
}

TWO_FACTOR_REQUIRED_DETAIL: Final[str] = (
    "Tu rol exige la verificación en dos pasos. Actívala para seguir."
)

########################################################################################
# Grupos y papeles


def profiles_of_sync(user: ApiUser) -> list[ApiGroupProfile]:
    return list(
        ApiGroupProfile.objects.filter(group__users=user).select_related("group"),
    )


# - el papel que ven los clientes: el de mayor rango entre los grupos de la cuenta
def role_of(user: ApiUser, profiles: Sequence[ApiGroupProfile]) -> str | None:
    if user.is_superuser:
        return AccountRoles.ADMIN.value

    held: set[str] = {str(profile.role) for profile in profiles}

    for role in ROLE_PRIORITY:
        if role in held:
            return role

    return None


def role_of_sync(user: ApiUser) -> str | None:
    return role_of(user, profiles_of_sync(user))


########################################################################################
# Permisos funcionales


def functional_permissions_sync(user: ApiUser) -> frozenset[str]:
    # un permiso solo llega por un rol: los que alguien tenga sueltos no cuentan, ni
    # los de una cuenta que no puede operar
    if not user.is_active:
        return frozenset()

    if user.is_superuser:
        return expand_implied(ALL_IDS)

    granted = Permission.objects.filter(
        codename__in=ALL_IDS,
        content_type__app_label="apiauth",
        content_type__model="apigroupprofile",
        group__users=user,
    ).values_list("codename", flat=True)

    return expand_implied(set(granted))


async def functional_permissions(user: ApiUser) -> frozenset[str]:
    return await sync_to_async(functional_permissions_sync)(user)


async def has_any_permission(user: ApiUser, *any_of: str) -> bool:
    return not (await functional_permissions(user)).isdisjoint(any_of)


# - deja pasar si la cuenta tiene al menos uno de los permisos; si no, `403`
async def ensure_permission(user: ApiUser, *any_of: str) -> None:
    if not await has_any_permission(user, *any_of):
        raise ForbiddenError


########################################################################################
# Superficies (RF-S-08)


def surface_allows_sync(user: ApiUser, surface: str) -> bool:
    # una cuenta sin grupos no tiene un papel que la limite: tampoco tiene permisos
    if user.is_superuser:
        return True

    profiles: list[ApiGroupProfile] = profiles_of_sync(user)

    if not profiles:
        return True

    kinds: set[str] = {str(profile.kind) for profile in profiles}

    return any(surface in SURFACES_BY_KIND[kind] for kind in kinds)


async def surface_allows(user: ApiUser, surface: str) -> bool:
    return await sync_to_async(surface_allows_sync)(user, surface)


########################################################################################
# Segundo factor obligatorio


async def requires_two_factor(user: ApiUser) -> bool:
    return await ApiGroupProfile.objects.filter(
        group__users=user,
        requires_two_factor=True,
    ).aexists()


async def ensure_two_factor_enrolled(
    controller: object,
    request: UsableHttpRequest,
) -> None:
    # quien tiene un rol que exige el segundo factor entra, pero solo puede activarlo
    # (y lo mínimo de la cuenta) hasta que lo haga
    if getattr(controller, "allows_pending_two_factor", False):
        return

    user: ApiUser = request.user

    if not await requires_two_factor(user) or await has_two_factor(user):
        return

    raise ForbiddenError(detail=TWO_FACTOR_REQUIRED_DETAIL)
