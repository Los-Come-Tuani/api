from typing import TYPE_CHECKING

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
    DecimalField,
    F,
    Index,
    IntegerField,
    Q,
    TextField,
    TimeField,
    UniqueConstraint,
)
from django.db.models.deletion import RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now, Upper
from django.utils.timezone import now
from pgtrigger import ReadOnly, Trigger

from api_catalogs.models import EventCategory
from api_core.models.base import ApiModel
from api_organizations.models import CulturalInstitution
from api_territory.models import City, Municipality, PointOfInterest
from api_utils.db import ImmutableUnaccent, track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Programado, en curso, finalizado y cancelado (M8). La vigencia la gobierna el
# calendario (RF-I-02): nadie publica ni despublica a mano. `programado` se ve como
# próximo en la agenda; `cancelado` se sigue viendo, señalado, y ya no genera avisos.
@track_table(meta={"db_table": "estado_evento_cambio"})
class EventStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    is_visible = BooleanField(db_column="es_visible")
    allows_editing = BooleanField(db_column="admite_edicion")
    generates_alerts = BooleanField(db_column="genera_avisos")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_evento"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoevento_codigo"),
        )


# Una función, feria, taller o festival, con su recinto, su rango de fechas y un
# horario diario. Lo programa una institución cultural o una alcaldía; sin ninguna de
# las dos es un evento especial de K'Plan. La ciudad es la de donde ocurre, no la de
# quien lo programa.
@track_table(meta={"db_table": "evento_cambio"})
class Event(ApiModel):
    institution = ForeignKey(
        db_column="institucion_cultural_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="events",
        to=CulturalInstitution,
    )
    municipality = ForeignKey(
        db_column="alcaldia_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="events",
        to=Municipality,
    )
    city = ForeignKey(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="events",
        to=City,
    )
    # el lugar del mapa donde ocurre, si es uno
    point = ForeignKey(
        db_column="punto_interes_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="events",
        to=PointOfInterest,
    )
    category = ForeignKey(
        db_column="categoria_evento_id",
        on_delete=RESTRICT,
        related_name="events",
        to=EventCategory,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="events",
        to=EventStatus,
    )
    # rastro del evento del que se copió (RF-I-06)
    cloned_from = ForeignKey(
        db_column="clonado_de_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="clones",
        to="self",
    )

    name = CharField(db_column="nombre", max_length=120)
    description = TextField(
        blank=True, db_column="descripcion", db_default="", default=""
    )
    venue = CharField(db_column="recinto", max_length=150)
    address = CharField(
        blank=True, db_column="direccion", db_default="", default="", max_length=200
    )
    latitude = DecimalField(db_column="latitud", decimal_places=6, max_digits=9)
    longitude = DecimalField(db_column="longitud", decimal_places=6, max_digits=9)

    start_date = DateField(db_column="fecha_inicio")
    end_date = DateField(db_column="fecha_fin")
    # el horario de cada día; un cierre antes de la apertura termina de madrugada
    start_time = TimeField(db_column="hora_inicio")
    end_time = TimeField(db_column="hora_fin")

    # en córdobas, sin centavos; cero es entrada libre
    entry_price = IntegerField(db_column="precio_entrada", db_default=0, default=0)

    # destacado en el inicio de la app: lo decide el equipo
    featured = BooleanField(db_column="destacado", db_default=False, default=False)
    cancellation_reason = CharField(
        blank=True,
        db_column="motivo_cancelacion",
        db_default="",
        default="",
        max_length=500,
    )

    # moderación posterior: el equipo con `content.moderate` lo oculta de la app
    hidden_at = DateTimeField(
        db_column="oculto_en", db_default=None, default=None, null=True
    )
    hidden_reason = CharField(
        blank=True, db_column="motivo_oculto", db_default="", default="", max_length=500
    )

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "evento"

        constraints: Sequence[CheckConstraint] = (
            # a lo sumo quien lo programa: ninguno es un evento de K'Plan
            CheckConstraint(
                condition=Q(institution__isnull=True) | Q(municipality__isnull=True),
                name="chk_evento_organizador_unico",
            ),
            CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="chk_evento_fechas_orden",
            ),
            CheckConstraint(
                condition=~Q(end_time=F("start_time")),
                name="chk_evento_horas_distintas",
            ),
            CheckConstraint(
                condition=Q(entry_price__gte=0),
                name="chk_evento_precio_no_negativo",
            ),
            CheckConstraint(
                condition=Q(latitude__gte=10.7) & Q(latitude__lte=15.1),
                name="chk_evento_latitud_rango",
            ),
            CheckConstraint(
                condition=Q(longitude__gte=-87.7) & Q(longitude__lte=-82.6),
                name="chk_evento_longitud_rango",
            ),
            CheckConstraint(
                condition=~Q(cloned_from=F("id")),
                name="chk_evento_no_autoclon",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["city", "start_date"], name="idx_evento_agenda"),
            Index(fields=["start_date", "end_date"], name="idx_evento_vigencia"),
            Index(
                condition=Q(cloned_from__isnull=False),
                fields=["cloned_from"],
                name="idx_evento_clonado",
            ),
            GinIndex(
                OpClass(
                    expression=Upper(ImmutableUnaccent("name")),
                    name="gin_trgm_ops",
                ),
                name="gin_evento_nombre",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_evento_readonly_creadoen"),
        )
