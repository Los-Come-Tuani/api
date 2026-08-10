from typing import TYPE_CHECKING, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import Group, Permission, PermissionsMixin
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import (
    BooleanField,
    CharField,
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
    email = EmailField(db_default="", default="")
    username = CharField(max_length=100, unique=True)
    password = CharField(max_length=128)

    created_at = DateTimeField(db_default=Now(), default=now)

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
    USERNAME_FIELD: Final[str] = "username"

    class Meta(ApiModel.Meta):
        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                Lower("email"),
                condition=Q(email__len__gt=0),
                name="unq_apiuser_email",
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
                condition=Q(email__len__gt=0),
                name="gin_apiuser_email",
            ),
            Index(fields=["created_at"], name="idx_apiuser_createdat"),
            Index(fields=["is_active"], name="idx_apiuser_isactive"),
        )

        ordering: Sequence[str] = ("username",)
        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_apiuser_readonly_createdat"),
            Protect(name="trg_apiuser_protect_insert", operation=Insert),
        )
