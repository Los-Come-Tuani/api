from typing import TYPE_CHECKING

from django.contrib.auth.models import Group
from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    OneToOneField,
    Q,
)
from django.db.models.deletion import DB_CASCADE
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import ReadOnly

from api_auth.enums import AccountRoles, GroupKinds
from api_core.models.base import ApiModel
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pgtrigger import Trigger

########################################################################################


# Lo que K'Plan sabe de un grupo además de sus permisos: de dónde es, qué papel da y si
# es de sistema. Un rol del equipo es un grupo `staff` con permisos funcionales.
#
# Es también la casa de los permisos funcionales (`api_auth.catalog`): su tipo de
# contenido es el de esos `Permission`, que se piden como `apiauth.guides.review`.
@track_table()
class ApiGroupProfile(ApiModel):
    group = OneToOneField(
        on_delete=DB_CASCADE,
        related_name="profile",
        to=Group,
    )

    # por cuál superficie entra quien tiene este grupo (portal o app)
    kind = CharField(choices=GroupKinds, max_length=16)
    # el papel que los clientes ven en la sesión; el equipo es siempre `admin`
    role = CharField(choices=AccountRoles, max_length=16)

    description = CharField(blank=True, db_default="", default="", max_length=300)

    # quien tiene este rol no opera sin segundo factor (se obliga a activarlo al entrar)
    requires_two_factor = BooleanField(db_default=False, default=False)

    # los roles de sistema no se editan ni se borran desde el portal
    is_system = BooleanField(db_default=False, default=False)

    created_at = DateTimeField(db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(kind__in=GroupKinds.values),
                name="chk_apigroupprofile_kind",
            ),
            CheckConstraint(
                condition=Q(role__in=AccountRoles.values),
                name="chk_apigroupprofile_role",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["created_at", "group", "kind"],
                name="trg_apigroupprofile_readonly",
            ),
        )
