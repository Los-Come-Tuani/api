from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    EmailField,
    OneToOneField,
    UniqueConstraint,
)
from django.db.models.deletion import RESTRICT
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import Before, Q, Trigger, UpdateOf

from api_core.models.base import ApiModel
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

# Los disparadores que nombran columnas (UpdateOf) llevan el nombre real de la columna,
# en español: pgtrigger no resuelve db_column. Las condiciones (Q) sí usan campos.
########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Una de las diez Ciudades Creativas de la Red Nacional. El catálogo está completo desde
# el primer día; `active` dice si ya se incorporó a la plataforma.
@track_table(meta={"db_table": "ciudad_cambio"})
class City(ApiModel):
    code = CharField(db_column="codigo", max_length=40)
    name = CharField(db_column="nombre", max_length=100)

    # el centro de la ciudad, para encuadrar el mapa
    latitude = DecimalField(db_column="latitud", decimal_places=6, max_digits=9)
    longitude = DecimalField(db_column="longitud", decimal_places=6, max_digits=9)

    active = BooleanField(db_column="activa", db_default=False, default=False)

    class Meta(ApiModel.Meta):
        db_table: str = "ciudad"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_ciudad_codigo"),
        )


########################################################################################


# El gobierno local dado de alta en la plataforma: la única autoridad que publica
# contenido oficial. No es una organización más: vive aquí porque manda sobre un
# territorio. Una sola por ciudad (la incorporación es progresiva).
#
# No tiene estado propio: `verified_at` nulo es el registro que todavía no opera, y lo
# escribe la resolución de la verificación (ver `api_moderation`).
@track_table(meta={"db_table": "alcaldia_cambio"})
class Municipality(ApiModel):
    city = OneToOneField(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="municipality",
        to=City,
    )

    name = CharField(db_column="nombre", max_length=150)
    contact_email = EmailField(db_column="correo_contacto", max_length=254)
    phone = CharField(db_column="telefono", max_length=30)

    # el documento que acredita la representación de quien solicita (la referencia en el
    # almacenamiento de archivos)
    document_key = CharField(db_column="documento_id", max_length=255)

    registered_at = DateTimeField(
        db_column="dada_de_alta_en",
        db_default=Now(),
        default=now,
    )
    verified_at = DateTimeField(
        db_column="verificado_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "alcaldia"

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            Trigger(
                condition=Q(
                    old__verified_at__isnull=False, new__verified_at__isnull=True
                ),
                func=(
                    "RAISE EXCEPTION 'La verificación de una alcaldía no se revierte.';"
                ),
                name="trg_alcaldia_noreverifica",
                operation=UpdateOf("verificado_en"),
                when=Before,
            ),
        )
