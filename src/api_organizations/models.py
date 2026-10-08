from typing import TYPE_CHECKING

from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    DecimalField,
    EmailField,
    F,
    Index,
    Q,
    SmallIntegerField,
    TextField,
    TimeField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Lower, Now, Upper
from django.utils.timezone import now
from pgtrigger import (
    Before,
    F as PgF,
    Q as PgQ,
    ReadOnly,
    Trigger,
    UpdateOf,
)

from api_catalogs.models import BusinessType, Currency, InstitutionType
from api_core.models.base import ApiModel
from api_territory.models import City
from api_utils.db import ImmutableUnaccent, track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

# Los disparadores que nombran columnas (UpdateOf) llevan el nombre real de la columna,
# en español: pgtrigger no resuelve db_column. Las condiciones (Q) sí usan campos.
########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Ficha de la MIPYME que aparece en el mapa. No tiene estado propio: `verified_at` nulo
# es la ficha que todavía no aparece, y lo escribe la resolución de la verificación.
@track_table(meta={"db_table": "comercio_cambio"})
class Business(ApiModel):
    city = ForeignKey(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="businesses",
        to=City,
    )
    business_type = ForeignKey(
        db_column="tipo_negocio_id",
        on_delete=RESTRICT,
        related_name="businesses",
        to=BusinessType,
    )

    # registro único del contribuyente; identifica, pero no es la llave primaria
    ruc = CharField(db_column="ruc", max_length=16)
    # el nombre comercial, no la razón social
    name = CharField(db_column="nombre", max_length=150)
    address = CharField(db_column="direccion", max_length=255)
    phone = CharField(db_column="telefono", max_length=30)
    alternate_phone = CharField(
        blank=True,
        db_column="telefono_alterno",
        db_default="",
        default="",
        max_length=30,
    )

    latitude = DecimalField(db_column="latitud", decimal_places=6, max_digits=9)
    longitude = DecimalField(db_column="longitud", decimal_places=6, max_digits=9)

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    verified_at = DateTimeField(
        db_column="verificado_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "comercio"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(fields=["ruc"], name="unq_comercio_ruc"),
            # provisional: el formato oficial del RUC no está definido en ninguna fuente
            CheckConstraint(
                condition=Q(ruc__regex=r"^[A-Z0-9-]{13,16}$"),
                name="chk_comercio_ruc_formato",
            ),
            # el territorio nicaragüense
            CheckConstraint(
                condition=Q(latitude__gte=10.7) & Q(latitude__lte=15.1),
                name="chk_comercio_latitud_rango",
            ),
            CheckConstraint(
                condition=Q(longitude__gte=-87.7) & Q(longitude__lte=-82.6),
                name="chk_comercio_longitud_rango",
            ),
            CheckConstraint(
                condition=Q(verified_at__isnull=True)
                | Q(verified_at__gte=F("created_at")),
                name="chk_comercio_verificado_coherente",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(verified_at__isnull=False),
                fields=["city"],
                name="idx_comercio_ciudad",
            ),
            Index(
                condition=Q(verified_at__isnull=True),
                fields=["created_at"],
                name="idx_comercio_cola",
            ),
            Index(fields=["latitude", "longitude"], name="idx_comercio_punto"),
            GinIndex(
                OpClass(
                    expression=Upper(ImmutableUnaccent("name")),
                    name="gin_trgm_ops",
                ),
                name="gin_comercio_nombre",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_comercio_readonly_creadoen"),
            # el RUC se corrige mientras la ficha está pendiente; verificada, ya no
            Trigger(
                condition=PgQ(old__verified_at__isnull=False)
                & PgQ(old__ruc__df=PgF("new__ruc")),
                func=(
                    "RAISE EXCEPTION "
                    "'El RUC no se reescribe una vez verificada la ficha.';"
                ),
                name="trg_comercio_readonly_ruc",
                operation=UpdateOf("ruc"),
                when=Before,
            ),
            Trigger(
                condition=PgQ(
                    old__verified_at__isnull=False, new__verified_at__isnull=True
                ),
                func=(
                    "RAISE EXCEPTION 'La verificación de un comercio no se revierte.';"
                ),
                name="trg_comercio_noreverifica",
                operation=UpdateOf("verificado_en"),
                when=Before,
            ),
        )


########################################################################################


# Una fila por día de la semana: permite saber si el local está abierto ahora sin
# interpretar texto. Un cierre anterior a la apertura significa madrugada.
@track_table(meta={"db_table": "comercio_horario_cambio"})
class BusinessHours(ApiModel):
    business = ForeignKey(
        db_column="comercio_id",
        on_delete=CASCADE,
        related_name="hours",
        to=Business,
    )

    # 0 es domingo, 6 es sábado
    weekday = SmallIntegerField(db_column="dia_semana")
    closed = BooleanField(db_column="cerrado", db_default=False, default=False)
    opens = TimeField(db_column="abre", db_default=None, default=None, null=True)
    closes = TimeField(db_column="cierra", db_default=None, default=None, null=True)

    class Meta(ApiModel.Meta):
        db_table: str = "comercio_horario"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(
                fields=["business", "weekday"],
                name="unq_comerciohorario_dia",
            ),
            CheckConstraint(
                condition=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="chk_comerciohorario_dia_rango",
            ),
            # un día cerrado no tiene horas, y uno abierto tiene las dos
            CheckConstraint(
                condition=(
                    Q(closed=True, opens__isnull=True, closes__isnull=True)
                    | Q(closed=False, opens__isnull=False, closes__isnull=False)
                ),
                name="chk_comerciohorario_coherente",
            ),
            CheckConstraint(
                condition=Q(closed=True) | ~Q(opens=F("closes")),
                name="chk_comerciohorario_horas_distintas",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(closed=False),
                fields=["business", "weekday"],
                name="idx_comerciohorario_abierto",
            ),
        )


########################################################################################


# La imagen de un dueño: un comercio, un lugar o un circuito (después, un evento). Una
# sola tabla con referencias excluyentes y una verificación que exige exactamente una
# presente. La primera por `order` es la portada.
@track_table(meta={"db_table": "foto_cambio"})
class Photo(ApiModel):
    business = ForeignKey(
        db_column="comercio_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="photos",
        to=Business,
    )
    point = ForeignKey(
        db_column="punto_interes_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="photos",
        to="apiterritory.PointOfInterest",
    )
    circuit = ForeignKey(
        db_column="circuito_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="photos",
        to="apiterritory.Circuit",
    )
    event = ForeignKey(
        db_column="evento_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="photos",
        to="apiagenda.Event",
    )

    # la referencia en el almacenamiento de archivos
    file_key = CharField(db_column="archivo_id", max_length=255)
    alt_text = CharField(
        blank=True,
        db_column="texto_alternativo",
        db_default="",
        default="",
        max_length=255,
    )
    order = SmallIntegerField(db_column="orden", db_default=0, default=0)

    class Meta(ApiModel.Meta):
        db_table: str = "foto"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=(
                    Q(
                        business__isnull=False,
                        circuit__isnull=True,
                        event__isnull=True,
                        point__isnull=True,
                    )
                    | Q(
                        business__isnull=True,
                        circuit__isnull=True,
                        event__isnull=True,
                        point__isnull=False,
                    )
                    | Q(
                        business__isnull=True,
                        circuit__isnull=False,
                        event__isnull=True,
                        point__isnull=True,
                    )
                    | Q(
                        business__isnull=True,
                        circuit__isnull=True,
                        event__isnull=False,
                        point__isnull=True,
                    )
                ),
                name="chk_foto_dueno_excluyente",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(point__isnull=False),
                fields=["point", "order"],
                name="idx_foto_lugar",
            ),
            Index(
                condition=Q(circuit__isnull=False),
                fields=["circuit", "order"],
                name="idx_foto_circuito",
            ),
            Index(
                condition=Q(event__isnull=False),
                fields=["event", "order"],
                name="idx_foto_evento",
            ),
        )


########################################################################################


# El platillo emblemático, gancho del segmento gastronómico. Varias filas por comercio,
# una sola vigente: reemplazar es insertar y retirar, no actualizar.
@track_table(meta={"db_table": "platillo_estrella_cambio"})
class SignatureDish(ApiModel):
    business = ForeignKey(
        db_column="comercio_id",
        on_delete=CASCADE,
        related_name="signature_dishes",
        to=Business,
    )

    name = CharField(db_column="nombre", max_length=150)
    description = TextField(
        blank=True, db_column="descripcion", db_default="", default=""
    )

    # orientativo: no es una tarifa cobrable
    reference_price = DecimalField(
        db_column="precio_referencia",
        decimal_places=2,
        max_digits=12,
    )
    currency = ForeignKey(
        db_column="moneda_id",
        on_delete=RESTRICT,
        related_name="+",
        to=Currency,
    )

    photo = ForeignKey(
        db_column="foto_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=Photo,
    )

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    withdrawn_at = DateTimeField(
        db_column="retirado_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "platillo_estrella"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(reference_price__gt=0),
                name="chk_platilloestrella_precio_positivo",
            ),
            CheckConstraint(
                condition=Q(withdrawn_at__isnull=True)
                | Q(withdrawn_at__gte=F("created_at")),
                name="chk_platilloestrella_retirado_coherente",
            ),
            # el índice único parcial hace cumplir «uno vigente», sin ventana de carrera
            UniqueConstraint(
                condition=Q(withdrawn_at__isnull=True),
                fields=["business"],
                name="unq_platilloestrella_vigente",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            Trigger(
                condition=PgQ(
                    old__withdrawn_at__isnull=False, new__withdrawn_at__isnull=True
                ),
                func=(
                    "RAISE EXCEPTION "
                    "'Un platillo retirado no vuelve a ser el vigente.';"
                ),
                name="trg_platilloestrella_norevive",
                operation=UpdateOf("retirado_en"),
                when=Before,
            ),
        )


########################################################################################


# Casa de cultura, fundación, ticketera o teatro que programa la agenda (RF-I-07). No
# puede programar eventos hasta que se verifica (el veto llega con la agenda, F6).
@track_table(meta={"db_table": "institucion_cultural_cambio"})
class CulturalInstitution(ApiModel):
    # dónde está la institución, no dónde ocurre lo que programa
    city = ForeignKey(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="cultural_institutions",
        to=City,
    )
    institution_type = ForeignKey(
        db_column="tipo_institucion_id",
        on_delete=RESTRICT,
        related_name="cultural_institutions",
        to=InstitutionType,
    )

    name = CharField(db_column="nombre", max_length=150)
    contact_email = EmailField(db_column="correo_contacto", max_length=254)
    phone = CharField(db_column="telefono", max_length=30)

    # el documento que acredita su existencia legal (la referencia en el almacenamiento)
    document_key = CharField(db_column="documento_id", max_length=255)

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    verified_at = DateTimeField(
        db_column="verificado_en",
        db_default=None,
        default=None,
        null=True,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "institucion_cultural"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            # un teatro no se registra dos veces en la misma ciudad
            UniqueConstraint(
                Lower("name"),
                "city",
                name="unq_institucioncultural_nombre",
            ),
            CheckConstraint(
                condition=Q(verified_at__isnull=True)
                | Q(verified_at__gte=F("created_at")),
                name="chk_institucioncultural_verificado_coherente",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["city"], name="idx_institucioncultural_ciudad"),
            Index(
                condition=Q(verified_at__isnull=True),
                fields=["created_at"],
                name="idx_institucioncultural_cola",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["created_at"],
                name="trg_institucioncultural_readonly_creadoen",
            ),
            Trigger(
                condition=PgQ(
                    old__verified_at__isnull=False, new__verified_at__isnull=True
                ),
                func=(
                    "RAISE EXCEPTION "
                    "'La verificación de una institución no se revierte.';"
                ),
                name="trg_institucioncultural_noreverifica",
                operation=UpdateOf("verificado_en"),
                when=Before,
            ),
        )
