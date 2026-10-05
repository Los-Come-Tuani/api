from typing import TYPE_CHECKING, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import Group, Permission, PermissionsMixin
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
    EmailField,
    Index,
    Q,
    UniqueConstraint,
)
from django.db.models.fields.related import ManyToManyField
from django.db.models.functions import Lower, Now, Upper
from django.utils.timezone import now
from pgtrigger import Insert, Protect, ReadOnly

from api_auth.enums import ApiUserStatus
from api_core.models.base import ApiModel
from api_utils.db import ImmutableUnaccent, track_table

from .manager import ApiUserManager

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

    from django.db.models.query import QuerySet
    from pgtrigger import Trigger
    from ty_extensions import Intersection

########################################################################################


@track_table()
class ApiUser(ApiModel, AbstractBaseUser, PermissionsMixin):
    first_name = CharField(db_default="", default="", max_length=100)
    last_name = CharField(db_default="", default="", max_length=100)

    # identificador de acceso (RF-S-05); siempre en minúsculas (ver `Meta`)
    email = EmailField(max_length=254)
    # alias público opcional; no sirve para iniciar sesión
    username = CharField(
        blank=True,
        db_default=None,
        default=None,
        max_length=100,
        null=True,
        unique=True,
    )
    password = CharField(max_length=128)

    # solo para comprobar la mayoría de edad (RF-S-05)
    birth_date = DateField(db_default=None, default=None, null=True)
    # código ISO 3166-1 alfa-2; vacío mientras la persona no lo declare
    nationality = CharField(db_default="", default="", max_length=2)

    status = CharField(
        choices=ApiUserStatus,
        db_default=ApiUserStatus.ACTIVE,
        default=ApiUserStatus.ACTIVE,
        max_length=16,
    )

    # nulo mientras el correo no se confirma; las cuentas federadas nacen verificadas
    verified_at = DateTimeField(db_default=None, default=None, null=True)

    # toda credencial emitida en este instante o antes deja de servir (RF-S-07)
    sessions_revoked_at = DateTimeField(db_default=None, default=None, null=True)

    # cuando la baja se hace efectiva (RF-S-11); nulo si no hay baja pendiente
    closing_effective_at = DateTimeField(db_default=None, default=None, null=True)

    created_at = DateTimeField(db_default=Now(), default=now)

    # `is_active` refleja `status == active` y la base lo exige; para cambiar el estado
    # se usa `api_auth.services.account.change_status`, nunca esta columna sola
    is_active = BooleanField(db_default=False, default=False)
    is_staff = BooleanField(db_default=False, default=False)
    is_superuser = BooleanField(db_default=False, default=False)

    groups = ManyToManyField(
        related_name="users",
        through="ApiUserGroups",
        to=Group,
    )

    permissions = ManyToManyField(
        related_name="users",
        through="ApiUserPermissions",
        to=Permission,
    )

    objects: ClassVar[Intersection[ApiUserManager, QuerySet]] = ApiUserManager()

    last_login = None
    user_permissions = None

    EMAIL_FIELD: Final[str] = "email"
    # el correo (USERNAME_FIELD) y la contraseña ya se piden siempre
    REQUIRED_FIELDS: list[str] = []  # ruff: ignore[mutable-class-default]
    USERNAME_FIELD: Final[str] = "email"

    class Meta(ApiModel.Meta):
        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(fields=["email"], name="unq_apiuser_email"),
            CheckConstraint(
                condition=Q(email=Lower("email")),
                name="chk_apiuser_email_lower",
            ),
            CheckConstraint(
                condition=(Q(username__isnull=True) | ~Q(username="")),
                name="chk_apiuser_username_notblank",
            ),
            CheckConstraint(
                condition=Q(status__in=ApiUserStatus.values),
                name="chk_apiuser_status",
            ),
            CheckConstraint(
                condition=(
                    Q(is_active=True, status=ApiUserStatus.ACTIVE)
                    | (Q(is_active=False) & ~Q(status=ApiUserStatus.ACTIVE))
                ),
                name="chk_apiuser_active_matches_status",
            ),
        )

        indexes: Sequence[Index] = (
            GinIndex(
                OpClass(
                    expression=Upper(ImmutableUnaccent("username")),
                    name="gin_trgm_ops",
                ),
                name="gin_apiuser_username",
            ),
            GinIndex(
                OpClass(
                    expression=Upper(ImmutableUnaccent("email")),
                    name="gin_trgm_ops",
                ),
                name="gin_apiuser_email",
            ),
            Index(fields=["created_at"], name="idx_apiuser_createdat"),
            Index(fields=["is_active"], name="idx_apiuser_isactive"),
            Index(fields=["status"], name="idx_apiuser_status"),
        )

        ordering: Sequence[str] = ("email",)

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_apiuser_readonly_createdat"),
            Protect(name="trg_apiuser_protect_insert", operation=Insert),
        )

    @property
    def display_name(self) -> str:
        name: str = f"{self.first_name} {self.last_name}".strip()

        return name or str(self.email).partition("@")[0]
