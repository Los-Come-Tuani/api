from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    Index,
    JSONField,
    Q,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# El teléfono al que se le mandan los avisos push (Firebase Cloud Messaging).
@track_table(meta={"db_table": "token_notificacion_cambio"}, exclude=["token"])
class DeviceToken(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=CASCADE,
        related_name="device_tokens",
        to=ApiUser,
    )
    token = CharField(db_column="token", max_length=500)
    platform = CharField(db_column="plataforma", max_length=16)
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    last_seen_at = DateTimeField(db_column="visto_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "token_notificacion"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(fields=["token"], name="unq_tokennotificacion_token"),
            CheckConstraint(
                condition=Q(platform__in=["android", "ios", "web"]),
                name="chk_tokennotificacion_plataforma",
            ),
        )


# Un aviso a una persona (M15): queda en su bandeja y, si lo quiere y hay Firebase, le
# llega al teléfono.
@track_table(meta={"db_table": "aviso_emitido_cambio"})
class Notification(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=CASCADE,
        related_name="notifications",
        to=ApiUser,
    )
    kind = CharField(db_column="tipo", max_length=40)
    title = CharField(db_column="titulo", max_length=120)
    body = TextField(db_column="cuerpo")
    # a qué apunta (la reserva, la convocatoria...): la app abre esa pantalla
    data = JSONField(db_column="datos", db_default={}, default=dict)
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    read_at = DateTimeField(
        db_column="leido_en", db_default=None, default=None, null=True
    )
    # `omitido` (sin Firebase o sin teléfono), `enviado` o `fallido`
    push_status = CharField(
        db_column="estado_push", db_default="omitido", default="omitido", max_length=16
    )

    class Meta(ApiModel.Meta):
        db_table: str = "aviso_emitido"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(push_status__in=["omitido", "enviado", "fallido"]),
                name="chk_avisoemitido_estadopush",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["user", "-created_at"], name="idx_avisoemitido_bandeja"),
        )


# Qué avisos quiere recibir en el teléfono. Sin fila, los quiere todos; la bandeja los
# guarda igual.
@track_table(meta={"db_table": "preferencia_aviso_cambio"})
class NotificationPreference(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=CASCADE,
        related_name="notification_preferences",
        to=ApiUser,
    )
    kind = CharField(db_column="tipo", max_length=40)
    push_enabled = BooleanField(db_column="push_activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "preferencia_aviso"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["user", "kind"], name="unq_preferenciaaviso_tipo"),
        )
