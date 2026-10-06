from collections import defaultdict
from typing import TYPE_CHECKING, Final

from asgiref.sync import sync_to_async
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError
from django.db.models import Count, Q
from django.db.transaction import atomic
from django.utils.timezone import now
from django.views.decorators.debug import sensitive_variables

from api_auth.catalog import (
    ALL_IDS,
    FunctionalPermissions as P,
)
from api_auth.enums import (
    AccountRoles,
    ApiUserStatus,
    ApiUserTypes,
    GroupKinds,
    VerificationPurposes,
)
from api_auth.models import ApiGroupProfile, ApiUser, ApiUserGroups
from api_auth.schemas.team import (
    StaffInviteGet,
    StaffMemberGet,
    StaffRoleGet,
    StaffRoleInlineGet,
)
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)

from .account import change_status_sync, ensure_strong_password, invalid_code_error
from .mail import send_invitation_code, send_password_reset_code
from .verification import check_code_sync, issue_code, issue_code_sync

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from django.db.models import Manager

    from api_auth.schemas.team import (
        StaffAcceptPost,
        StaffInvitePost,
        StaffRolePost,
    )

########################################################################################

# - quien cuenta como parte del equipo en un rol: los activos y los invitados
MEMBER_STATUSES: Final[Sequence[str]] = (
    ApiUserStatus.ACTIVE.value,
    ApiUserStatus.PENDING.value,
)

SYSTEM_ROLE_DETAIL: Final[str] = "Los roles de sistema no se pueden editar ni borrar."

LAST_ADMIN_DETAIL: Final[str] = (
    "Tiene que quedar al menos una persona activa con el rol Super admin."
)

########################################################################################
# Roles del equipo (grupos `staff`)


def staff_profile_or_404(role_id: int) -> ApiGroupProfile:
    profile: ApiGroupProfile | None = (
        ApiGroupProfile.objects
        .select_related("group")
        .filter(group_id=role_id, kind=GroupKinds.STAFF)
        .first()
    )

    if profile is None:
        raise NotFoundError(detail="No encontramos ese rol.")

    return profile


def group_of(profile: ApiGroupProfile) -> Group:
    return profile.group  # ty: ignore[invalid-return-type]


def permissions_of(group: Group) -> Manager:
    return group.permissions  # ty: ignore[invalid-return-type]


def roles_payload(profiles: Sequence[ApiGroupProfile]) -> list[StaffRoleGet]:
    ids: list[int] = [group_of(profile).pk for profile in profiles]

    granted: dict[int, list[str]] = defaultdict(list)

    for group_id, codename in Permission.objects.filter(
        codename__in=ALL_IDS,
        content_type__app_label="apiauth",
        content_type__model="apigroupprofile",
        group__id__in=ids,
    ).values_list("group__id", "codename"):
        granted[group_id].append(codename)

    members: dict[int, int] = dict(
        ApiUserGroups.objects
        .filter(api_user__status__in=MEMBER_STATUSES, group_id__in=ids)
        .values_list("group_id")
        .annotate(total=Count("id"))
    )

    return [
        StaffRoleGet(
            created_at=profile.created_at,  # ty: ignore[invalid-argument-type]
            description=str(profile.description),
            id=group_of(profile).pk,
            members=members.get(group_of(profile).pk, 0),
            name=str(group_of(profile).name),
            permissions=tuple(sorted(granted[group_of(profile).pk])),
            requires_two_factor=bool(profile.requires_two_factor),
            system=bool(profile.is_system),
        )
        for profile in profiles
    ]


def list_roles_sync() -> list[StaffRoleGet]:
    return roles_payload(
        list(
            ApiGroupProfile.objects
            .filter(kind=GroupKinds.STAFF)
            .select_related("group")
            .order_by("-is_system", "group__name")
        )
    )


def get_role_sync(role_id: int) -> StaffRoleGet:
    return roles_payload([staff_profile_or_404(role_id)])[0]


def validate_permissions(requested: Sequence[str]) -> list[str]:
    unknown: list[str] = sorted(set(requested) - ALL_IDS)

    if unknown:
        raise BadRequestError(
            field_errors={
                "permissions": f"Permisos desconocidos: {', '.join(unknown)}."
            },
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    return sorted(set(requested))


def permission_rows(codenames: Sequence[str]) -> list[Permission]:
    return list(
        Permission.objects.filter(
            codename__in=codenames,
            content_type__app_label="apiauth",
            content_type__model="apigroupprofile",
        )
    )


def create_role_sync(data: StaffRolePost) -> StaffRoleGet:
    codenames: list[str] = validate_permissions(data.permissions)

    try:
        with atomic():
            group: Group = Group.objects.create(name=data.name)

            ApiGroupProfile.objects.create(
                description=data.description,
                group=group,
                kind=GroupKinds.STAFF,
                requires_two_factor=data.requires_two_factor,
                role=AccountRoles.ADMIN,
            )

            permissions_of(group).set(permission_rows(codenames))
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i

    return get_role_sync(group.pk)


def would_lock_out(actor: ApiUser, role: ApiGroupProfile, codenames: set[str]) -> bool:
    # quien edita su propio rol no puede quitarse el permiso de administrar el equipo:
    # se quedaría sin poder deshacerlo
    if actor.is_superuser:
        return False

    own: Group = group_of(role)

    if not ApiUserGroups.objects.filter(api_user=actor, group=own).exists():
        return False

    # lo que le dan los otros roles que la persona tiene
    others: set[str] = set(
        Permission.objects.filter(
            codename__in=ALL_IDS,
            content_type__app_label="apiauth",
            content_type__model="apigroupprofile",
            group__in=Group.objects.filter(users=actor).exclude(pk=own.pk),
        ).values_list("codename", flat=True)
    )

    return P.STAFF_MANAGE.value not in (codenames | others)


def apply_role_changes(
    profile: ApiGroupProfile,
    data: StaffRolePost,
    codenames: Sequence[str],
) -> None:
    with atomic():
        group: Group = group_of(profile)
        group.name = data.name  # ty: ignore[invalid-assignment]
        group.save(update_fields=["name"])

        profile.description = data.description  # ty: ignore[invalid-assignment]
        profile.requires_two_factor = data.requires_two_factor  # ty: ignore[invalid-assignment]
        profile.save(update_fields=["description", "requires_two_factor"])

        # los permisos del modelo que el grupo ya tuviera se conservan
        kept: list[Permission] = list(
            permissions_of(group).exclude(codename__in=ALL_IDS)
        )
        permissions_of(group).set([*kept, *permission_rows(codenames)])


def update_role_sync(
    role_id: int,
    data: StaffRolePost,
    actor: ApiUser,
) -> StaffRoleGet:
    profile: ApiGroupProfile = staff_profile_or_404(role_id)

    if profile.is_system:
        raise ForbiddenError(detail=SYSTEM_ROLE_DETAIL)

    codenames: list[str] = validate_permissions(data.permissions)

    if would_lock_out(actor, profile, set(codenames)):
        raise ForbiddenError(
            detail=(
                "No puedes quitarle a tu propio rol el permiso de administrar el "
                "equipo: te quedarías sin poder deshacerlo."
            ),
        )

    try:
        apply_role_changes(profile, data, codenames)
    except IntegrityError as i:
        raise ConflictError.from_integrity_error(i).scoped(RequestScopes.BODY) from i

    return get_role_sync(role_id)


def delete_role_sync(role_id: int) -> None:
    profile: ApiGroupProfile = staff_profile_or_404(role_id)

    if profile.is_system:
        raise ForbiddenError(detail=SYSTEM_ROLE_DETAIL)

    members: int = ApiUserGroups.objects.filter(group_id=role_id).count()

    if members:
        raise ConflictError(
            detail=(
                f"Este rol lo tienen {members} persona(s) del equipo. Cámbiales el "
                "rol antes de borrarlo."
            ),
        )

    group_of(profile).delete()


########################################################################################
# Personas del equipo


def user_or_404(user_id: UUID) -> ApiUser:
    user: ApiUser | None = ApiUser.objects.filter(pk=user_id).first()

    if user is None:
        raise NotFoundError(detail="No encontramos a esa persona.")

    return user


def member_payload(user: ApiUser) -> StaffMemberGet:
    profile: ApiGroupProfile | None = (
        ApiGroupProfile.objects
        .select_related("group")
        .filter(group__users=user, kind=GroupKinds.STAFF)
        .first()
    )

    return StaffMemberGet(
        created_at=user.created_at,  # ty: ignore[invalid-argument-type]
        email=str(user.email),
        id=user.pk,
        name=user.display_name,
        role=(
            None
            if profile is None
            else StaffRoleInlineGet(
                id=group_of(profile).pk,
                name=str(group_of(profile).name),
            )
        ),
        status=user.status,  # ty: ignore[invalid-argument-type]
    )


# El equipo de K'Plan: quien tiene un rol del equipo y los superusuarios (tienen todo
# aunque no estén en un grupo). Es pequeño: se devuelve completo, por nombre.
def staff_members_sync() -> list[StaffMemberGet]:
    members = (
        ApiUser.objects
        .filter(Q(groups__profile__kind=GroupKinds.STAFF) | Q(is_superuser=True))
        .distinct()
        .order_by("first_name", "last_name", "email")
    )

    return [member_payload(user) for user in members]


def ensure_not_last_admin(target: ApiUser) -> None:
    # la última persona activa con el rol Super admin (o con todo, por ser superusuario)
    # no se suspende ni se cambia de rol: nadie podría volver a administrar el equipo
    if target.status != ApiUserStatus.ACTIVE:
        return

    admins = ApiUser.objects.filter(status=ApiUserStatus.ACTIVE).filter(
        Q(is_superuser=True) | Q(groups__name=ApiUserTypes.ADMIN)
    )

    is_admin: bool = admins.filter(pk=target.pk).exists()

    if is_admin and not admins.exclude(pk=target.pk).exists():
        raise ConflictError(detail=LAST_ADMIN_DETAIL)


def assign_staff_role(user: ApiUser, profile: ApiGroupProfile) -> None:
    # una persona del equipo tiene un solo rol del equipo; los grupos de otro tipo
    # (los públicos, por ejemplo) no se tocan
    with atomic():
        ApiUserGroups.objects.filter(
            api_user=user,
            group__profile__kind=GroupKinds.STAFF,
        ).delete()

        ApiUserGroups.objects.create(api_user=user, group=group_of(profile))


def invite_staff_sync(data: StaffInvitePost) -> tuple[ApiUser, str | None]:
    profile: ApiGroupProfile | None = (
        ApiGroupProfile.objects
        .select_related("group")
        .filter(group_id=data.role_id, kind=GroupKinds.STAFF)
        .first()
    )

    if profile is None:
        raise BadRequestError(
            field_errors={"role_id": "Ese rol no existe."},
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        ).scoped(RequestScopes.BODY)

    with atomic():
        user: ApiUser | None = ApiUser.objects.filter(email=data.email).first()

        if user is None:
            try:
                user = ApiUser.objects.create_user(
                    email=data.email,
                    first_name=data.first_name,
                    last_name=data.last_name,
                    password=None,
                    status=ApiUserStatus.PENDING,
                )
            except IntegrityError as i:
                raise ConflictError.from_integrity_error(i).scoped(
                    RequestScopes.BODY
                ) from i
        elif user.status != ApiUserStatus.PENDING:
            # quien invita es del equipo, no un desconocido: aquí sí se dice
            raise ConflictError(
                detail="Ya existe una cuenta con ese correo.",
                field_errors={"email": "Ya existe una cuenta con ese correo."},
            ).scoped(RequestScopes.BODY)

        # una invitación sin aceptar se puede reenviar con otro rol
        assign_staff_role(user, profile)

    code: str | None = issue_code_sync(
        destination=str(user.email),
        purpose=VerificationPurposes.INVITATION,
        user=user,
    )

    return user, code


async def invite_staff(data: StaffInvitePost) -> StaffInviteGet:
    user, code = await sync_to_async(invite_staff_sync)(data)

    if code is not None:
        await send_invitation_code(
            code=code,
            name=user.display_name,
            to=str(user.email),
        )

    member: StaffMemberGet = await sync_to_async(member_payload)(user)

    return StaffInviteGet(**dict(member), sent=code is not None)


@sensitive_variables()
def accept_invitation_sync(*, code: str, email: str, password: str) -> None:
    user: ApiUser | None = ApiUser.objects.filter(
        email=email,
        status=ApiUserStatus.PENDING,
    ).first()

    # un correo sin invitación y un código malo dan el mismo error; la comprobación va
    # aparte para que el intento fallido quede guardado
    if user is None or not check_code_sync(
        code=code,
        consume=False,
        destination=email,
        purpose=VerificationPurposes.INVITATION,
    ):
        raise invalid_code_error()

    ensure_strong_password(password, user=user)

    with atomic():
        if not check_code_sync(
            code=code,
            consume=True,
            destination=email,
            purpose=VerificationPurposes.INVITATION,
        ):
            raise invalid_code_error()

        user.set_password(password)
        user.save(update_fields=["password"])

        change_status_sync(user, ApiUserStatus.ACTIVE)

        # quien acepta la invitación demostró que el correo es suyo
        ApiUser.objects.filter(pk=user.pk).update(verified_at=now())


@sensitive_variables()
async def accept_invitation(data: StaffAcceptPost) -> None:
    await sync_to_async(accept_invitation_sync)(
        code=data.code,
        email=data.email,
        password=data.password,
    )


def set_status_sync(*, actor: ApiUser, status: str, user_id: UUID) -> StaffMemberGet:
    target: ApiUser = user_or_404(user_id)

    if target.pk == actor.pk:
        raise ForbiddenError(detail="No puedes cambiar el estado de tu propia cuenta.")

    if target.is_superuser and not actor.is_superuser:
        raise ForbiddenError(detail="Esa cuenta solo la administra un superusuario.")

    if target.status == ApiUserStatus.PENDING:
        raise BadRequestError(
            detail="Esa persona todavía no acepta su invitación.",
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        )

    if target.status not in {ApiUserStatus.ACTIVE, ApiUserStatus.SUSPENDED}:
        raise ConflictError(
            detail="La cuenta está en un estado que no se cambia desde aquí.",
        )

    if status == ApiUserStatus.SUSPENDED:
        ensure_not_last_admin(target)

    # suspender corta de inmediato las sesiones abiertas
    change_status_sync(target, ApiUserStatus(status))

    return member_payload(target)


def set_role_sync(*, actor: ApiUser, role_id: int, user_id: UUID) -> StaffMemberGet:
    target: ApiUser = user_or_404(user_id)
    profile: ApiGroupProfile = staff_profile_or_404(role_id)

    if target.pk == actor.pk:
        raise ForbiddenError(detail="No puedes cambiar tu propio rol.")

    if target.is_superuser and not actor.is_superuser:
        raise ForbiddenError(detail="Esa cuenta solo la administra un superusuario.")

    in_team: bool = ApiUserGroups.objects.filter(
        api_user=target,
        group__profile__kind=GroupKinds.STAFF,
    ).exists()

    if not in_team:
        raise BadRequestError(
            detail="Esa persona no es del equipo de K'Plan.",
            type=BadRequestErrorTypes.FAILED_VALIDATION,
        )

    if group_of(profile).name != ApiUserTypes.ADMIN:
        ensure_not_last_admin(target)

    assign_staff_role(target, profile)

    return member_payload(target)


async def send_password_reset_to(user_id: UUID) -> None:
    target: ApiUser = await sync_to_async(user_or_404)(user_id)

    if target.status != ApiUserStatus.ACTIVE:
        raise ConflictError(
            detail="Solo se puede recuperar la contraseña de una cuenta activa.",
        )

    code: str | None = await issue_code(
        destination=str(target.email),
        purpose=VerificationPurposes.PASSWORD_RESET,
        user=target,
    )

    if code is not None:
        await send_password_reset_code(code=code, to=str(target.email))
