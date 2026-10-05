from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    GenericIPAddressField,
    Index,
    PositiveSmallIntegerField,
    Q,
    UniqueConstraint,
)
from django.db.models.deletion import DB_CASCADE
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import Protect, ReadOnly, Update

from api_auth.enums import IdentityProviders, VerificationPurposes
from api_core.models.base import ApiModel
from api_utils.db import track_table

from .user import ApiUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pgtrigger import Trigger

########################################################################################


class ApiLoginAttempt(ApiModel):
    """
    Cada intento de iniciar sesión, exitoso o no (RF-S-06). Solo se inserta.

    No referencia a `ApiUser`: si lo hiciera, un correo que no existe no tendría dónde
    registrarse y el bloqueo solo funcionaría con cuentas reales, lo que revelaría
    cuáles existen (D-08).
    """

    # tal como lo tecleó la persona
    identifier = CharField(max_length=254)
    # el mismo identificador normalizado; con él se cuentan los intentos
    key = CharField(max_length=254)

    ip_address = GenericIPAddressField(db_default=None, default=None, null=True)
    succeeded = BooleanField()

    created_at = DateTimeField(db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        indexes: Sequence[Index] = (
            Index(
                condition=Q(succeeded=False),
                fields=["key", "-created_at"],
                name="idx_apiloginattempt_failed",
            ),
            Index(fields=["created_at"], name="idx_apiloginattempt_createdat"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            # un intento no se corrige: borrarlos por antigüedad sí se permite (purga)
            Protect(name="trg_apiloginattempt_noupdate", operation=Update),
        )


########################################################################################


class ApiLoginLock(ApiModel):
    """El bloqueo vigente de un identificador: uno solo por llave."""

    key = CharField(max_length=254)
    locked_until = DateTimeField()

    class Meta(ApiModel.Meta):
        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["key"], name="unq_apiloginlock_key"),
        )

        indexes: Sequence[Index] = (
            Index(fields=["locked_until"], name="idx_apiloginlock_lockeduntil"),
        )


########################################################################################


@track_table()
class ApiExternalIdentity(ApiModel):
    """
    Cuenta de un proveedor federado (Google) vinculada a un usuario.

    Una cuenta externa no se vincula a dos usuarios, y un usuario tiene a lo sumo una
    identidad por proveedor.
    """

    user = ForeignKey(
        on_delete=DB_CASCADE,
        related_name="external_identities",
        to=ApiUser,
    )

    provider = CharField(choices=IdentityProviders, max_length=24)
    # el identificador estable de la persona en el proveedor (`sub` en Google)
    subject = CharField(max_length=255)
    # el correo que el proveedor reportó al vincular; informativo
    email = EmailField(max_length=254)

    created_at = DateTimeField(db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["provider", "subject"],
                name="unq_apiexternalidentity_subject",
            ),
            UniqueConstraint(
                fields=["user", "provider"],
                name="unq_apiexternalidentity_user",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["created_at", "provider", "subject", "user"],
                name="trg_apiexternalidentity_readonly",
            ),
        )


########################################################################################


class ApiVerificationCode(ApiModel):
    """
    Código de un solo uso enviado por correo (alta, invitación, recuperación).

    Guarda el hash y no el código. El destino queda congelado: un código emitido para
    un correo no sirve para otro.
    """

    purpose = CharField(choices=VerificationPurposes, max_length=24)
    destination = EmailField(max_length=254)
    code_hash = CharField(max_length=64)

    user = ForeignKey(
        default=None,
        null=True,
        on_delete=DB_CASCADE,
        related_name="+",
        to=ApiUser,
    )

    attempts = PositiveSmallIntegerField(db_default=0, default=0)
    expires_at = DateTimeField()
    consumed_at = DateTimeField(db_default=None, default=None, null=True)
    created_at = DateTimeField(db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        indexes: Sequence[Index] = (
            Index(
                fields=["destination", "purpose", "-created_at"],
                name="idx_apiverificationcode_lookup",
            ),
            Index(fields=["expires_at"], name="idx_apiverificationcode_expiresat"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["code_hash", "created_at", "destination", "purpose", "user"],
                name="trg_apiverificationcode_readonly",
            ),
        )
