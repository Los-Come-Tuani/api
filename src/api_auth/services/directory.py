from typing import TYPE_CHECKING, Any, Final

from django.contrib.auth.models import Group
from django.db.models import (
    Case,
    CharField,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    Value,
    When,
)
from django.db.utils import IntegrityError

from api_auth.catalog import FunctionalPermissions as P
from api_auth.enums import AccountRoles, GroupKinds
from api_auth.models import ApiGroupProfile, ApiUser
from api_auth.schemas.directory import AccountGet, AccountPatch, AccountQuery
from api_auth.schemas.session import OrganizationRefGet, ProviderRefGet
from api_auth.schemas.team import StaffRoleInlineGet
from api_auth.services.roles import ROLE_PRIORITY, role_of
from api_auth.services.team import group_of
from api_core.services.pages import paginate
from api_exceptions.enums import RequestScopes
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_moderation.schemas import CityRef
from api_profiles.enums import PROVIDER_API_STATUS
from api_profiles.services.documents import services_of
from api_roles.models import RoleAssignment

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_territory.models import City

########################################################################################

NOT_FOUND_DETAIL: Final[str] = "No encontramos a esa persona."

# - la organización de cada clase de asignación, en el orden en que se prefieren
ORGANIZATION_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("business", "business"),
    ("institution", "institution"),
    ("municipality", "municipality"),
)

########################################################################################
# Lectura


# Quién ve qué: con `users.view`, todas las cuentas; quien solo administra el equipo
# (`staff.manage`), solo al equipo.
def visible_accounts(*, sees_everyone: bool) -> QuerySet:
    whens: list[When] = [When(is_superuser=True, then=Value(AccountRoles.ADMIN.value))]

    # el papel visible es el de más rango: el primer grupo que coincide gana
    whens.extend(
        When(
            Exists(
                ApiGroupProfile.objects.filter(group__users=OuterRef("pk"), role=role)
            ),
            then=Value(role),
        )
        for role in ROLE_PRIORITY
    )

    accounts = (
        ApiUser.objects
        .annotate(derived_role=Case(*whens, default=None, output_field=CharField()))
        .select_related("provider_profile__city", "provider_profile__status")
        .prefetch_related(
            Prefetch("groups", queryset=Group.objects.select_related("profile")),
            Prefetch(
                "role_assignments",
                queryset=RoleAssignment.objects
                .filter(revoked_at__isnull=True)
                .select_related(
                    "business__city", "institution__city", "municipality__city"
                )
                .order_by("granted_at"),
                to_attr="active_assignments",
            ),
        )
    )

    if not sees_everyone:
        accounts = accounts.filter(derived_role=AccountRoles.ADMIN.value)

    return accounts


def account_or_404(account_id: UUID, *, sees_everyone: bool) -> ApiUser:
    found: ApiUser | None = (
        visible_accounts(sees_everyone=sees_everyone).filter(pk=account_id).first()
    )

    if found is None:
        raise NotFoundError(detail=NOT_FOUND_DETAIL)

    return found


def city_ref(city: City | None) -> CityRef | None:
    if city is None:
        return None

    found: Any = city

    return CityRef(code=str(found.code), id=found.pk, name=str(found.name))


def account_payload(user: ApiUser) -> AccountGet:
    account: Any = user

    profiles: list[ApiGroupProfile] = [
        group.profile for group in account.groups.all() if hasattr(group, "profile")
    ]
    staff_group: Group | None = next(
        (group_of(profile) for profile in profiles if profile.kind == GroupKinds.STAFF),
        None,
    )

    organization: OrganizationRefGet | None = None
    city: City | None = None

    for assignment in getattr(account, "active_assignments", ()):
        for kind, field in ORGANIZATION_FIELDS:
            record: Any = getattr(assignment, field)

            if record is not None and organization is None:
                organization = OrganizationRefGet(
                    id=record.pk,
                    kind=kind,  # ty: ignore[invalid-argument-type]
                    name=str(record.name),
                    verified=record.verified_at is not None,
                )
                city = record.city

    provider: Any = getattr(account, "provider_profile", None)

    if provider is not None and organization is None:
        city = provider.city

    return AccountGet(
        city=city_ref(city),
        created_at=account.created_at,
        email=str(account.email),
        first_name=str(account.first_name),
        id=account.pk,
        last_name=str(account.last_name),
        name=user.display_name,
        organization=organization,
        provider=(
            None
            if provider is None
            else ProviderRefGet(
                id=provider.pk,
                services=tuple(services_of(provider)),
                status=PROVIDER_API_STATUS[str(provider.status.code)],  # ty: ignore[invalid-argument-type]
            )
        ),
        role=role_of(user, profiles),  # ty: ignore[invalid-argument-type]
        staff_role=(
            None
            if staff_group is None
            else StaffRoleInlineGet(id=staff_group.pk, name=str(staff_group.name))
        ),
        status=account.status,
        superuser=bool(account.is_superuser),
        verified=account.verified_at is not None,
    )


def accounts_sync(
    query: AccountQuery,
    *,
    sees_everyone: bool,
) -> Paginated[AccountGet]:
    accounts = visible_accounts(sees_everyone=sees_everyone)

    if query.role is not None:
        accounts = accounts.filter(derived_role=query.role)

    if query.status is not None:
        accounts = accounts.filter(status=query.status)

    if query.search:
        term: str = query.search.strip()

        accounts = accounts.filter(
            Q(email__icontains=term)
            | Q(first_name__im_unaccent__icontains=term)
            | Q(last_name__im_unaccent__icontains=term)
            | Q(username__icontains=term)
        )

    ordered = accounts.order_by("first_name", "last_name", "email", "id")

    return paginate(ordered, query, account_payload, AccountGet)


def account_sync(account_id: UUID, *, sees_everyone: bool) -> AccountGet:
    return account_payload(account_or_404(account_id, sees_everyone=sees_everyone))


########################################################################################
# Cambios


def update_account_sync(
    account_id: UUID,
    patch: AccountPatch,
    *,
    actor: ApiUser,
    held: frozenset[str],
) -> AccountGet:
    sees_everyone: bool = P.USERS_VIEW in held
    target: ApiUser = account_or_404(account_id, sees_everyone=sees_everyone)

    if target.pk == actor.pk:
        raise ForbiddenError(detail="Tus propios datos se cambian desde tu perfil.")

    if target.is_superuser and not actor.is_superuser:
        raise ForbiddenError(detail="Esa cuenta solo la administra un superusuario.")

    # al equipo lo administra quien administra el equipo; al resto, quien administra
    # las cuentas
    in_team: bool = getattr(target, "derived_role", None) == AccountRoles.ADMIN.value

    if (P.STAFF_MANAGE if in_team else P.USERS_MANAGE) not in held:
        raise ForbiddenError

    changes: dict[str, object] = patch.model_dump(exclude_unset=True)

    if changes:
        try:
            ApiUser.objects.filter(pk=target.pk).update(**changes)
        except IntegrityError as i:
            raise ConflictError.from_integrity_error(i).scoped(
                RequestScopes.BODY
            ) from i

    return account_sync(account_id, sees_everyone=sees_everyone)
