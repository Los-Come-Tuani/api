from typing import TYPE_CHECKING, Any

from asgiref.sync import sync_to_async

from api_auth.schemas.group import GroupInlineGet
from api_auth.schemas.session import (
    OrganizationRefGet,
    ProviderRefGet,
    SessionUserGet,
    TwoFactorState,
)
from api_profiles.services.payloads import provider_ref_sync
from api_roles.services import organization_of_sync

from .roles import (
    functional_permissions,
    profiles_of_sync,
    requires_two_factor,
    role_of,
)
from .two_factor import has_two_factor

if TYPE_CHECKING:
    from django.contrib.auth.models import Group

    from api_auth.models import ApiUser

########################################################################################


async def build_session_user(user: ApiUser) -> SessionUserGet:
    groups: list[Group] = [g async for g in user.groups.order_by("name")]  # ty: ignore[unresolved-attribute]

    # los atributos de los modelos de Django no tienen tipos para ty: aquí se leen sin
    # ellos, y los valores validan contra `SessionUserGet` al construirlo
    account: Any = user

    # los grupos con su perfil: de ahí salen el papel y los permisos que se ven
    profiles = await sync_to_async(profiles_of_sync)(user)
    permissions = await functional_permissions(user)

    # la organización viene de la asignación de rol con ámbito vigente
    organization = await sync_to_async(organization_of_sync)(user)
    provider = await sync_to_async(provider_ref_sync)(user)

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
        organization=(
            None
            if organization is None
            else OrganizationRefGet(
                id=organization.id,
                kind=organization.kind,  # ty: ignore[invalid-argument-type]
                name=organization.name,
                verified=organization.verified_at is not None,
            )
        ),
        organization_id=None if organization is None else organization.id,
        permissions=tuple(sorted(permissions)),
        provider=(
            None
            if provider is None
            else ProviderRefGet(
                id=provider.id,
                services=provider.services,
                status=provider.status,  # ty: ignore[invalid-argument-type]
            )
        ),
        role=role_of(user, profiles),  # ty: ignore[invalid-argument-type]
        status=account.status,
        two_factor=TwoFactorState(
            enabled=await has_two_factor(user),
            required=await requires_two_factor(user),
        ),
        username=account.username,
        verified=account.verified_at is not None,
    )
