from typing import TYPE_CHECKING

from django.db.models import (
    CharField,
    CheckConstraint,
    DateTimeField,
    Index,
    Q,
    TextField,
)
from django.db.models.deletion import RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now

from api_agenda.models import Event
from api_auth.models import ApiUser
from api_catalogs.models import Reason
from api_core.models.base import ApiModel
from api_reputation.models import Review
from api_territory.models import PointOfInterest
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Alguien avisa al equipo de una persona o de un contenido (M14): exactamente uno.
@track_table(meta={"db_table": "reporte_cambio"})
class Report(ApiModel):
    reporter = ForeignKey(
        db_column="reportado_por",
        on_delete=RESTRICT,
        related_name="reports_made",
        to=ApiUser,
    )
    target_user = ForeignKey(
        db_column="usuario_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="reports_received",
        to=ApiUser,
    )
    target_review = ForeignKey(
        db_column="resena_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="reports",
        to=Review,
    )
    target_point = ForeignKey(
        db_column="punto_interes_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="reports",
        to=PointOfInterest,
    )
    target_event = ForeignKey(
        db_column="evento_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="reports",
        to=Event,
    )
    reason = ForeignKey(
        db_column="motivo_id",
        on_delete=RESTRICT,
        related_name="+",
        to=Reason,
    )
    note = TextField(blank=True, db_column="nota", db_default="", default="")
    status = CharField(
        db_column="estado", db_default="pendiente", default="pendiente", max_length=16
    )
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    resolved_at = DateTimeField(
        db_column="resuelto_en", db_default=None, default=None, null=True
    )
    resolved_by = ForeignKey(
        db_column="resuelto_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    resolution_note = TextField(
        blank=True, db_column="nota_resolucion", db_default="", default=""
    )

    class Meta(ApiModel.Meta):
        db_table: str = "reporte"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(status__in=["pendiente", "atendido", "descartado"]),
                name="chk_reporte_estado",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["status", "created_at"], name="idx_reporte_bandeja"),
        )


# Lo que el equipo decide sobre una persona: advertencia, suspensión (con o sin fin) o
# expulsión. Levantarla escribe la fecha; no se borra (RF-B-10).
@track_table(meta={"db_table": "sancion_cambio"})
class Sanction(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="sanctions",
        to=ApiUser,
    )
    kind = CharField(db_column="tipo", max_length=16)
    reason = TextField(db_column="motivo")
    starts_at = DateTimeField(db_column="inicia_en", db_default=Now(), default=now)
    # nulo es indefinida (o una advertencia, que no dura)
    ends_at = DateTimeField(
        db_column="termina_en", db_default=None, default=None, null=True
    )
    created_by = ForeignKey(
        db_column="impuesta_por",
        on_delete=RESTRICT,
        related_name="+",
        to=ApiUser,
    )
    report = ForeignKey(
        db_column="reporte_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="sanctions",
        to=Report,
    )
    lifted_at = DateTimeField(
        db_column="levantada_en", db_default=None, default=None, null=True
    )
    lifted_by = ForeignKey(
        db_column="levantada_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "sancion"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(kind__in=["advertencia", "suspension", "expulsion"]),
                name="chk_sancion_tipo",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["user", "-starts_at"], name="idx_sancion_usuario"),
        )
