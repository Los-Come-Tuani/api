from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    SmallIntegerField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE
from django.db.models.fields.related import ForeignKey
from django.db.models.query_utils import Q

from api_core.models.base import ApiModel
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Giro del comercio: restaurante, cafetería, panadería, artesanía u otro.
@track_table(meta={"db_table": "tipo_negocio_cambio"})
class BusinessType(ApiModel):
    code = CharField(db_column="codigo", max_length=40)
    label = CharField(db_column="etiqueta", max_length=100)
    active = BooleanField(db_column="activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "tipo_negocio"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_tiponegocio_codigo"),
        )


########################################################################################


# Las cuatro figuras que admite el alta de una institución cultural (RF-I-07).
@track_table(meta={"db_table": "tipo_institucion_cambio"})
class InstitutionType(ApiModel):
    code = CharField(db_column="codigo", max_length=40)
    label = CharField(db_column="etiqueta", max_length=100)
    active = BooleanField(db_column="activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "tipo_institucion"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_tipoinstitucion_codigo"),
        )


########################################################################################


# La lista compartida de causas: rechazos, reportes, sanciones, cancelaciones.
@track_table(meta={"db_table": "motivo_cambio"})
class Reason(ApiModel):
    code = CharField(db_column="codigo", max_length=60)
    label = CharField(db_column="etiqueta", max_length=150)
    # obliga a acompañar el motivo con una nota («otro» la exige)
    requires_text = BooleanField(
        db_column="exige_texto", db_default=False, default=False
    )
    active = BooleanField(db_column="activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "motivo"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_motivo_codigo"),
        )


# En qué lista se ofrece cada causa: una misma causa sirve en varios sitios.
@track_table(meta={"db_table": "motivo_contexto_cambio"})
class ReasonContext(ApiModel):
    reason = ForeignKey(
        db_column="motivo_id",
        on_delete=CASCADE,
        related_name="contexts",
        to=Reason,
    )
    context = CharField(db_column="contexto", max_length=60)
    order = SmallIntegerField(db_column="orden", db_default=0, default=0)

    class Meta(ApiModel.Meta):
        db_table: str = "motivo_contexto"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["reason", "context"],
                name="unq_motivocontexto_par",
            ),
        )


########################################################################################


@track_table(meta={"db_table": "moneda_cambio"})
class Currency(ApiModel):
    # ISO 4217
    code = CharField(db_column="codigo", max_length=3)
    name = CharField(db_column="nombre", max_length=100)
    decimals = SmallIntegerField(db_column="decimales", db_default=2, default=2)

    class Meta(ApiModel.Meta):
        db_table: str = "moneda"

        constraints: Sequence[UniqueConstraint | CheckConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_moneda_codigo"),
            CheckConstraint(
                condition=Q(decimals__gte=0) & Q(decimals__lte=6),
                name="chk_moneda_decimales_rango",
            ),
        )
