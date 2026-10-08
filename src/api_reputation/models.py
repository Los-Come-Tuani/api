from typing import TYPE_CHECKING

from django.db.models import (
    CharField,
    CheckConstraint,
    DateTimeField,
    F,
    Index,
    Q,
    SmallIntegerField,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
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


# La evaluación mutua al terminar un servicio (M11): el turista califica al guía y el
# guía al turista, una vez cada uno. Se publica al instante; si el reseñado la impugna y
# el equipo le da la razón, se oculta.
@track_table(meta={"db_table": "resena_cambio"})
class Review(ApiModel):
    booking = ForeignKey(
        db_column="reserva_id",
        on_delete=RESTRICT,
        related_name="reviews",
        to=Booking,
    )
    author = ForeignKey(
        db_column="autor_id",
        on_delete=RESTRICT,
        related_name="reviews_written",
        to=ApiUser,
    )
    subject = ForeignKey(
        db_column="resenado_id",
        on_delete=RESTRICT,
        related_name="reviews_received",
        to=ApiUser,
    )
    # quién califica a quién
    direction = CharField(db_column="sentido", max_length=24)
    rating = SmallIntegerField(db_column="calificacion")
    comment = TextField(blank=True, db_column="comentario", db_default="", default="")
    created_at = DateTimeField(db_column="creada_en", db_default=Now(), default=now)
    hidden_at = DateTimeField(
        db_column="oculta_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "resena"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="chk_resena_calificacion_rango",
            ),
            CheckConstraint(
                condition=Q(direction__in=["tourist_to_guide", "guide_to_tourist"]),
                name="chk_resena_sentido",
            ),
            CheckConstraint(
                condition=~Q(author=F("subject")),
                name="chk_resena_no_autoresena",
            ),
            UniqueConstraint(fields=["booking", "author"], name="unq_resena_autor"),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(hidden_at__isnull=True),
                fields=["subject", "-created_at"],
                name="idx_resena_resenado",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=[
                    "author",
                    "booking",
                    "comment",
                    "created_at",
                    "rating",
                    "subject",
                ],
                name="trg_resena_inmutable",
            ),
        )


# El reseñado pide que el equipo revise una reseña. Una abierta a la vez.
@track_table(meta={"db_table": "resena_impugnacion_cambio"})
class ReviewDispute(ApiModel):
    review = ForeignKey(
        db_column="resena_id",
        on_delete=CASCADE,
        related_name="disputes",
        to=Review,
    )
    raised_by = ForeignKey(
        db_column="presentada_por",
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )
    reason = TextField(db_column="motivo")
    status = CharField(
        db_column="estado", db_default="pendiente", default="pendiente", max_length=16
    )
    created_at = DateTimeField(db_column="creada_en", db_default=Now(), default=now)
    resolved_by = ForeignKey(
        db_column="resuelta_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    resolved_at = DateTimeField(
        db_column="resuelta_en", db_default=None, default=None, null=True
    )
    note = TextField(blank=True, db_column="nota", db_default="", default="")

    class Meta(ApiModel.Meta):
        db_table: str = "resena_impugnacion"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(status__in=["pendiente", "aceptada", "rechazada"]),
                name="chk_resenaimpugnacion_estado",
            ),
            UniqueConstraint(
                condition=Q(status="pendiente"),
                fields=["review"],
                name="unq_resenaimpugnacion_abierta",
            ),
        )
