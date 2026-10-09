from typing import TYPE_CHECKING

from django.db.models import (
    CheckConstraint,
    DateTimeField,
    Index,
    OneToOneField,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Length, Now
from django.db.models.lookups import GreaterThan
from django.utils.timezone import now
from pgtrigger import ReadOnly, Trigger

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_services.models import Booking
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# La sala de una reserva (M10): el turista y el guía hablan ahí antes y durante el
# servicio. Nace con la reserva.
@track_table(meta={"db_table": "conversacion_cambio"})
class Conversation(ApiModel):
    booking = OneToOneField(
        db_column="reserva_id",
        on_delete=CASCADE,
        related_name="conversation",
        to=Booking,
    )
    created_at = DateTimeField(db_column="creada_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "conversacion"


# Quién está en la sala y hasta dónde leyó.
@track_table(meta={"db_table": "conversacion_participante_cambio"})
class Participant(ApiModel):
    conversation = ForeignKey(
        db_column="conversacion_id",
        on_delete=CASCADE,
        related_name="participants",
        to=Conversation,
    )
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="conversations",
        to=ApiUser,
    )
    last_read_at = DateTimeField(
        db_column="leido_hasta", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "conversacion_participante"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["conversation", "user"],
                name="unq_conversacionparticipante_par",
            ),
        )


# Un mensaje. No se edita: lo dicho queda dicho.
@track_table(meta={"db_table": "mensaje_cambio"})
class Message(ApiModel):
    conversation = ForeignKey(
        db_column="conversacion_id",
        on_delete=CASCADE,
        related_name="messages",
        to=Conversation,
    )
    sender = ForeignKey(
        db_column="remitente_id",
        on_delete=RESTRICT,
        related_name="messages",
        to=ApiUser,
    )
    body = TextField(db_column="cuerpo")
    sent_at = DateTimeField(db_column="enviado_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "mensaje"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=GreaterThan(Length("body"), 0),
                name="chk_mensaje_cuerpo_presente",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["conversation", "sent_at"], name="idx_mensaje_sala"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["body", "conversation", "sender", "sent_at"],
                name="trg_mensaje_inmutable",
            ),
        )
