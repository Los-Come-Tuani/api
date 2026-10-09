from typing import TYPE_CHECKING

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    F,
    Index,
    IntegerField,
    OneToOneField,
    Q,
    SmallIntegerField,
    TextField,
    TimeField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now, Upper
from django.utils.timezone import now
from pgtrigger import (
    Before,
    F as PgF,
    Q as PgQ,
    ReadOnly,
    Trigger,
    UpdateOf,
)

from api_catalogs.models import CulturalPillar
from api_core.models.base import ApiModel
from api_utils.db import ImmutableUnaccent, track_table

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
                condition=PgQ(
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


########################################################################################


# Un lugar concreto del territorio, con su ubicación (D-18): existe aunque ningún
# circuito lo incluya. Suma lo que la app muestra de cada parada (pilar, dirección,
# horario, tiempo de visita, consejo) y, a lo sumo, una organización dueña: el comercio
# cuyo lugar es (se crea al aprobarlo), la institución o la alcaldía que lo administra.
# Sin dueño, lo administra el equipo.
@track_table(meta={"db_table": "punto_interes_cambio"})
class PointOfInterest(ApiModel):
    city = ForeignKey(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="points",
        to=City,
    )
    pillar = ForeignKey(
        db_column="pilar_cultural_id",
        on_delete=RESTRICT,
        related_name="points",
        to=CulturalPillar,
    )

    business = ForeignKey(
        db_column="comercio_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="points",
        to="apiorganizations.Business",
    )
    institution = ForeignKey(
        db_column="institucion_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="points",
        to="apiorganizations.CulturalInstitution",
    )
    municipality = ForeignKey(
        db_column="alcaldia_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="points",
        to=Municipality,
    )

    name = CharField(db_column="nombre", max_length=80)
    description = TextField(
        blank=True, db_column="descripcion", db_default="", default=""
    )
    address = CharField(
        blank=True, db_column="direccion", db_default="", default="", max_length=140
    )
    latitude = DecimalField(db_column="latitud", decimal_places=6, max_digits=9)
    longitude = DecimalField(db_column="longitud", decimal_places=6, max_digits=9)

    # sin horario es un lugar que no cierra (parque, calle, mirador)
    opens_at = TimeField(db_column="abre", db_default=None, default=None, null=True)
    closes_at = TimeField(db_column="cierra", db_default=None, default=None, null=True)
    # el tiempo sugerido de visita
    visit_minutes = SmallIntegerField(
        db_column="minutos_visita", db_default=30, default=30
    )
    tip = CharField(
        blank=True, db_column="consejo", db_default="", default="", max_length=140
    )
    # su QR da una insignia de su pilar (la activación llega con las insignias, F6)
    has_badge = BooleanField(db_column="da_insignia", db_default=False, default=False)

    # lo generan los turistas con sus reseñas (F7): aquí solo se guarda el resumen
    rating = DecimalField(
        db_column="calificacion",
        db_default=0,
        decimal_places=1,
        default=0,
        max_digits=2,
    )
    reviews_count = IntegerField(db_column="resenas", db_default=0, default=0)

    # retirarlo no borra lo que ya otorgó ni las paradas que lo copiaron
    active = BooleanField(db_column="activo", db_default=True, default=True)
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "punto_interes"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(latitude__gte=10.7) & Q(latitude__lte=15.1),
                name="chk_puntointeres_latitud_rango",
            ),
            CheckConstraint(
                condition=Q(longitude__gte=-87.7) & Q(longitude__lte=-82.6),
                name="chk_puntointeres_longitud_rango",
            ),
            # a lo sumo un dueño: ninguno es un lugar del equipo
            CheckConstraint(
                condition=(
                    Q(business__isnull=True, institution__isnull=True)
                    | Q(business__isnull=True, municipality__isnull=True)
                    | Q(institution__isnull=True, municipality__isnull=True)
                ),
                name="chk_puntointeres_dueno_unico",
            ),
            # van las dos horas o ninguna
            CheckConstraint(
                condition=Q(opens_at__isnull=True, closes_at__isnull=True)
                | Q(opens_at__isnull=False, closes_at__isnull=False),
                name="chk_puntointeres_horario_coherente",
            ),
            CheckConstraint(
                condition=Q(visit_minutes__gt=0) & Q(visit_minutes__lte=720),
                name="chk_puntointeres_visita_rango",
            ),
            CheckConstraint(
                condition=Q(rating__gte=0) & Q(rating__lte=5),
                name="chk_puntointeres_calificacion_rango",
            ),
            CheckConstraint(
                condition=Q(reviews_count__gte=0),
                name="chk_puntointeres_resenas_positivas",
            ),
            # el comercio tiene un solo lugar: el suyo
            UniqueConstraint(
                condition=Q(business__isnull=False),
                fields=["business"],
                name="unq_puntointeres_comercio",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(active=True),
                fields=["city"],
                name="idx_puntointeres_ciudad",
            ),
            Index(fields=["latitude", "longitude"], name="idx_puntointeres_punto"),
            GinIndex(
                OpClass(
                    expression=Upper(ImmutableUnaccent("name")),
                    name="gin_trgm_ops",
                ),
                name="gin_puntointeres_nombre",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_puntointeres_readonly_creadoen"),
        )


########################################################################################


# La ficha comercial del lugar: lo que ofrece, sus servicios y cómo contactarlo. La
# edita su dueño y sale de inmediato; el equipo con `places.manage` puede corregirla.
@track_table(meta={"db_table": "ficha_lugar_cambio"})
class PlaceProfile(ApiModel):
    point = OneToOneField(
        db_column="punto_interes_id",
        on_delete=CASCADE,
        related_name="profile",
        to=PointOfInterest,
    )

    amenities = ArrayField(
        CharField(max_length=40),
        db_column="servicios",
        db_default=[],
        default=list,
        size=20,
    )
    languages = ArrayField(
        CharField(max_length=40),
        db_column="idiomas",
        db_default=[],
        default=list,
        size=12,
    )

    phone = CharField(
        blank=True, db_column="telefono", db_default="", default="", max_length=20
    )
    whatsapp = CharField(
        blank=True, db_column="whatsapp", db_default="", default="", max_length=20
    )
    email = CharField(
        blank=True, db_column="correo", db_default="", default="", max_length=254
    )
    website = CharField(
        blank=True, db_column="sitio_web", db_default="", default="", max_length=200
    )
    instagram = CharField(
        blank=True, db_column="instagram", db_default="", default="", max_length=40
    )
    facebook = CharField(
        blank=True, db_column="facebook", db_default="", default="", max_length=80
    )

    updated_at = DateTimeField(
        db_column="actualizado_en", db_default=Now(), default=now
    )

    class Meta(ApiModel.Meta):
        db_table: str = "ficha_lugar"


# Un producto o servicio que ofrece el lugar. El precio es orientativo (córdobas); nulo
# es "a consultar".
@track_table(meta={"db_table": "oferta_lugar_cambio"})
class PlaceOffering(ApiModel):
    point = ForeignKey(
        db_column="punto_interes_id",
        on_delete=CASCADE,
        related_name="offerings",
        to=PointOfInterest,
    )

    name = CharField(db_column="nombre", max_length=80)
    description = CharField(
        blank=True, db_column="descripcion", db_default="", default="", max_length=300
    )
    price = IntegerField(db_column="precio", db_default=None, default=None, null=True)
    order = SmallIntegerField(db_column="orden", db_default=0, default=0)

    class Meta(ApiModel.Meta):
        db_table: str = "oferta_lugar"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(price__isnull=True) | Q(price__gte=0),
                name="chk_ofertalugar_precio_positivo",
            ),
        )


# Una novedad que el dueño publica sobre su lugar. Ocultarla la saca de la app sin
# borrarla.
@track_table(meta={"db_table": "publicacion_cambio"})
class Publication(ApiModel):
    point = ForeignKey(
        db_column="punto_interes_id",
        on_delete=CASCADE,
        related_name="publications",
        to=PointOfInterest,
    )
    author = ForeignKey(
        db_column="autor_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="publications",
        to="apiauth.ApiUser",
    )

    title = CharField(db_column="titulo", max_length=80)
    body = TextField(db_column="cuerpo")
    # la referencia en el almacenamiento; vacía si no lleva imagen
    image_key = CharField(
        blank=True, db_column="imagen_id", db_default="", default="", max_length=255
    )
    visible = BooleanField(db_column="visible", db_default=True, default=True)
    published_at = DateTimeField(
        db_column="publicado_en", db_default=Now(), default=now
    )

    class Meta(ApiModel.Meta):
        db_table: str = "publicacion"

        indexes: Sequence[Index] = (
            Index(
                condition=Q(visible=True),
                fields=["point", "-published_at"],
                name="idx_publicacion_lugar",
            ),
        )


########################################################################################


# Borrador, publicado, despublicado y retirado: solo el publicado se ve en la app, y el
# retirado ya no se edita.
@track_table(meta={"db_table": "estado_circuito_cambio"})
class CircuitStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    is_visible = BooleanField(db_column="es_visible")
    allows_editing = BooleanField(db_column="admite_edicion")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_circuito"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadocircuito_codigo"),
        )


# El recorrido oficial: una secuencia ordenada de lugares de una ciudad. Lo publica la
# alcaldía de esa ciudad (`creative`, RF-A-01) o el equipo de K'Plan (los especiales,
# `kplan`, y los del catálogo, `private`). Suma lo que la app necesita para mostrarlo y
# reservarlo: precios, horarios de salida, punto de encuentro, temporada.
#
# `version` sube solo cuando cambia la geometría (las paradas o su orden): la app la usa
# para saber si tiene que redibujar el recorrido (RF-A-06, D-15).
@track_table(meta={"db_table": "circuito_oficial_cambio"})
class Circuit(ApiModel):
    city = ForeignKey(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="circuits",
        to=City,
    )
    municipality = ForeignKey(
        db_column="alcaldia_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="circuits",
        to=Municipality,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="circuits",
        to=CircuitStatus,
    )

    kind = CharField(db_column="tipo", max_length=16)
    title = CharField(db_column="titulo", max_length=80)
    short_title = CharField(db_column="titulo_corto", max_length=28)
    subtitle = CharField(db_column="subtitulo", max_length=60)
    description = TextField(db_column="descripcion")
    category = CharField(db_column="categoria", max_length=16)
    difficulty = CharField(db_column="dificultad", max_length=16)
    travel_mode = CharField(db_column="modo_traslado", max_length=16)

    # en córdobas, sin centavos
    price_adult = IntegerField(db_column="precio_adulto", db_default=0, default=0)
    price_child = IntegerField(db_column="precio_nino", db_default=0, default=0)

    recommendations = TextField(
        blank=True, db_column="recomendaciones", db_default="", default=""
    )
    includes = TextField(blank=True, db_column="incluye", db_default="", default="")
    notes = TextField(blank=True, db_column="notas", db_default="", default="")
    meeting_point = CharField(db_column="punto_encuentro", max_length=200)
    meeting_latitude = DecimalField(
        db_column="encuentro_latitud", decimal_places=6, max_digits=9
    )
    meeting_longitude = DecimalField(
        db_column="encuentro_longitud", decimal_places=6, max_digits=9
    )
    start_times = ArrayField(
        TimeField(),
        db_column="horarios_salida",
        db_default=[],
        default=list,
        size=6,
    )

    # los especiales de K'Plan dan insignias extra al completarlos; los creativos, tres
    bonus_badges = SmallIntegerField(
        db_column="insignias_extra", db_default=0, default=0
    )
    booking_mode = CharField(db_column="modalidad", max_length=16)
    # de temporada: la app lo muestra solo entre estas fechas
    available_from = DateField(
        db_column="disponible_desde", db_default=None, default=None, null=True
    )
    available_until = DateField(
        db_column="disponible_hasta", db_default=None, default=None, null=True
    )

    version = IntegerField(db_column="version", db_default=1, default=1)

    rating = DecimalField(
        db_column="calificacion",
        db_default=0,
        decimal_places=1,
        default=0,
        max_digits=2,
    )
    reviews_count = IntegerField(db_column="resenas", db_default=0, default=0)

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    published_at = DateTimeField(
        db_column="publicado_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "circuito_oficial"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(kind__in=["kplan", "creative", "private"]),
                name="chk_circuito_tipo",
            ),
            # el creativo es de la alcaldía; los demás no tienen alcaldía
            CheckConstraint(
                condition=Q(kind="creative", municipality__isnull=False)
                | (~Q(kind="creative") & Q(municipality__isnull=True)),
                name="chk_circuito_alcaldia_coherente",
            ),
            CheckConstraint(
                condition=Q(category__in=["city", "nature", "culture"]),
                name="chk_circuito_categoria",
            ),
            CheckConstraint(
                condition=Q(difficulty__in=["easy", "moderate"]),
                name="chk_circuito_dificultad",
            ),
            CheckConstraint(
                condition=Q(travel_mode__in=["walking", "vehicle"]),
                name="chk_circuito_modo",
            ),
            CheckConstraint(
                condition=Q(booking_mode__in=["private", "group"]),
                name="chk_circuito_modalidad",
            ),
            CheckConstraint(
                condition=Q(price_adult__gte=0) & Q(price_child__gte=0),
                name="chk_circuito_precios_positivos",
            ),
            CheckConstraint(
                condition=Q(bonus_badges__gte=0) & Q(bonus_badges__lte=5),
                name="chk_circuito_insignias_rango",
            ),
            CheckConstraint(
                condition=Q(available_from__isnull=True, available_until__isnull=True)
                | Q(
                    available_from__isnull=False,
                    available_until__isnull=False,
                    available_until__gte=F("available_from"),
                ),
                name="chk_circuito_temporada_coherente",
            ),
            CheckConstraint(
                condition=Q(meeting_latitude__gte=10.7)
                & Q(meeting_latitude__lte=15.1)
                & Q(meeting_longitude__gte=-87.7)
                & Q(meeting_longitude__lte=-82.6),
                name="chk_circuito_encuentro_rango",
            ),
            CheckConstraint(
                condition=Q(version__gte=1),
                name="chk_circuito_version_positiva",
            ),
            CheckConstraint(
                condition=Q(rating__gte=0) & Q(rating__lte=5),
                name="chk_circuito_calificacion_rango",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["city", "status"], name="idx_circuito_ciudad"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_circuito_readonly_creadoen"),
            Trigger(
                condition=PgQ(old__version__gt=PgF("new__version")),
                func="RAISE EXCEPTION 'La versión de un circuito no retrocede.';",
                name="trg_circuito_version_creciente",
                operation=UpdateOf("version"),
                when=Before,
            ),
        )


# Una parada del circuito: el lugar y su posición en el recorrido.
@track_table(meta={"db_table": "circuito_parada_cambio"})
class CircuitStop(ApiModel):
    circuit = ForeignKey(
        db_column="circuito_id",
        on_delete=CASCADE,
        related_name="stops",
        to=Circuit,
    )
    point = ForeignKey(
        db_column="punto_interes_id",
        on_delete=RESTRICT,
        related_name="circuit_stops",
        to=PointOfInterest,
    )

    order = SmallIntegerField(db_column="orden")
    # cómo llegar desde la parada anterior
    directions = TextField(
        blank=True, db_column="indicacion", db_default="", default=""
    )
    # minutos de traslado desde la parada anterior; nulo es "lo calcula la app"
    leg_minutes = SmallIntegerField(
        db_column="minutos_tramo", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "circuito_parada"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(
                fields=["circuit", "order"],
                name="unq_circuitoparada_orden",
            ),
            # un lugar no se visita dos veces en el mismo recorrido
            UniqueConstraint(
                fields=["circuit", "point"],
                name="unq_circuitoparada_punto",
            ),
            CheckConstraint(
                condition=Q(order__gte=0),
                name="chk_circuitoparada_orden_positivo",
            ),
            CheckConstraint(
                condition=Q(leg_minutes__isnull=True)
                | (Q(leg_minutes__gte=0) & Q(leg_minutes__lte=600)),
                name="chk_circuitoparada_tramo_rango",
            ),
        )
