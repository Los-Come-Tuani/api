from typing import TYPE_CHECKING

from django.contrib.auth.models import Group, Permission
from django.db.models import UniqueConstraint
from django.db.models.deletion import CASCADE, DB_CASCADE
from django.db.models.fields.related import ForeignKey

from api_core.models.base import ApiModel
from api_utils.db import track_table

from .user import ApiUser

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################


@track_table()
class ApiUserGroups(ApiModel):
    api_user = ForeignKey(
        on_delete=DB_CASCADE,
        related_name="+",
        to=ApiUser,
    )

    group = ForeignKey(
        on_delete=DB_CASCADE,
        related_name="+",
        to=Group,
    )

    class Meta(ApiModel.Meta):
        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["api_user", "group"],
                name="unq_apiusergroups_apiuser_group",
            ),
        )


########################################################################################


@track_table()
class ApiUserPermissions(ApiModel):
    # all models in a relation chain must use either
    # ALL python callbacks or ALL database callbacks for `on_delete`
    api_user = ForeignKey(
        on_delete=CASCADE,
        related_name="+",
        to=ApiUser,
    )

    # Permission.content_type uses python `CASCADE`
    # so it must be mirrored here
    permission = ForeignKey(
        on_delete=CASCADE,
        related_name="+",
        to=Permission,
    )

    class Meta(ApiModel.Meta):
        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["api_user", "permission"],
                name="unq_apiuserpermissions_apiuser_permission",
            ),
        )
