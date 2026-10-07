from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    SmallIntegerField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT
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


@track_table(meta={"db_table": "idioma_cambio"})
class Language(ApiModel):
    # ISO 639-1
    code = CharField(db_column="codigo", max_length=8)
    name = CharField(db_column="nombre", max_length=100)
    active = BooleanField(db_column="activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "idioma"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_idioma_codigo"),
        )


########################################################################################


# Lo que ofrece un prestador: guiar recorridos o traducir. Una misma persona puede
# ofrecer los dos (D-12), y por eso no es un campo del perfil.
@track_table(meta={"db_table": "tipo_servicio_cambio"})
class ServiceType(ApiModel):
    code = CharField(db_column="codigo", max_length=40)
    label = CharField(db_column="etiqueta", max_length=100)
    active = BooleanField(db_column="activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "tipo_servicio"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_tiposervicio_codigo"),
        )


# Los documentos que se le piden a un prestador. El modelo solo prevé el que acredita un
# servicio (la licencia del INTUR, el certificado de idiomas); el equipo pide además la
# cédula y el récord de policía a todos (`service` nulo), y la licencia de conducir y el
# seguro a quien lleva turistas en su vehículo (`requires_vehicle`).
@track_table(meta={"db_table": "tipo_acreditacion_cambio"})
class CredentialType(ApiModel):
    code = CharField(db_column="codigo", max_length=40)
    label = CharField(db_column="etiqueta", max_length=100)
    service = ForeignKey(
        db_column="tipo_servicio_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="credential_types",
        to=ServiceType,
    )
    # falso en los que no caducan: un certificado de idiomas no vence, una licencia sí
    requires_expiry = BooleanField(
        db_column="exige_vencimiento", db_default=True, default=True
    )
    requires_vehicle = BooleanField(
        db_column="exige_vehiculo", db_default=False, default=False
    )
    order = SmallIntegerField(db_column="orden", db_default=0, default=0)
    active = BooleanField(db_column="activo", db_default=True, default=True)

    class Meta(ApiModel.Meta):
        db_table: str = "tipo_acreditacion"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_tipoacreditacion_codigo"),
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
