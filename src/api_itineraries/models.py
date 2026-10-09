from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    DecimalField,
    Index,
    JSONField,
    Q,
    SmallIntegerField,
    TimeField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Length, Now
from django.db.models.lookups import GreaterThanOrEqual
from django.utils.timezone import now
from pgtrigger import (
    Before,
    Insert,
    Q as PgQ,
    ReadOnly,
    Trigger,
    UpdateOf,
)

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_territory.models import Circuit, PointOfInterest
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

# Los disparadores que nombran columnas (UpdateOf) llevan el nombre real de la columna,
# en español: pgtrigger no resuelve db_column. Las condiciones (Q) sí usan campos.
########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
########################################################################################


# Planificado, en curso, completado y eliminado (M6).
@track_table(meta={"db_table": "estado_itinerario_cambio"})
class ItineraryStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    allows_editing = BooleanField(db_column="admite_edicion")
    allows_booking = BooleanField(db_column="admite_reserva")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_itinerario"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoitinerario_codigo"),
        )


# Lo que un turista se propone recorrer (D-33). Mientras sigue un circuito tal cual no
# copia nada: las paradas se leen del circuito vivo. La primera edición (agregar, quitar
# o reordenar) lo vuelve `adjusted`, copia las paradas y suelta la referencia viva; eso
# no se revierte.
#
# El modelo lo cuelga de `perfil_turista`; mientras ese perfil no existe (llega con las
# insignias), cuelga de la cuenta.
@track_table(meta={"db_table": "itinerario_cambio"})
class Itinerary(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=CASCADE,
        related_name="itineraries",
        to=ApiUser,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="itineraries",
        to=ItineraryStatus,
    )

    title = CharField(db_column="titulo", max_length=80)
    # el circuito vivo que se lee mientras no se ajusta
    followed_circuit = ForeignKey(
        db_column="circuito_seguido_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="followers",
        to=Circuit,
    )
    adjusted = BooleanField(db_column="ajustado", db_default=False, default=False)

    # el plan del día que arma la app: hora de salida, cómo se mueve, a qué ritmo y las
    # llegadas fijadas a mano (posición de la parada -> minutos desde medianoche)
    start_time = TimeField(
        db_column="hora_salida",
        db_default="09:00",
        default="09:00",
    )
    travel_mode = CharField(
        db_column="modo_traslado",
        db_default="walking",
        default="walking",
        max_length=16,
    )
    pace = CharField(
        db_column="ritmo", db_default="balanced", default="balanced", max_length=16
    )
    fixed_arrivals = JSONField(db_column="llegadas_fijas", db_default={}, default=dict)

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    started_at = DateTimeField(
        db_column="iniciado_en", db_default=None, default=None, null=True
    )
    completed_at = DateTimeField(
        db_column="completado_en", db_default=None, default=None, null=True
    )
    # baja lógica del turista
    deleted_at = DateTimeField(
        db_column="eliminado_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "itinerario"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(adjusted=True) | Q(followed_circuit__isnull=False),
                name="chk_itinerario_seguido_coherente",
            ),
            CheckConstraint(
                condition=GreaterThanOrEqual(Length("title"), 3),
                name="chk_itinerario_titulo_longitud",
            ),
            CheckConstraint(
                condition=Q(travel_mode__in=["walking", "vehicle"]),
                name="chk_itinerario_modo",
            ),
            CheckConstraint(
                condition=Q(pace__in=["relaxed", "balanced", "intense"]),
                name="chk_itinerario_ritmo",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(deleted_at__isnull=True),
                fields=["user", "-created_at"],
                name="idx_itinerario_turista",
            ),
            Index(
                fields=["followed_circuit", "adjusted"],
                name="idx_itinerario_metricas",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_itinerario_readonly_creadoen"),
            Trigger(
                condition=PgQ(old__adjusted=True, new__adjusted=False),
                func=(
                    "RAISE EXCEPTION "
                    "'Un itinerario ajustado no vuelve a seguir el circuito.';"
                ),
                name="trg_itinerario_ajustado_irreversible",
                operation=UpdateOf("ajustado"),
                when=Before,
            ),
        )


# Las paradas propias: solo existen cuando el itinerario se apartó del circuito. Guardan
# su nombre y sus coordenadas (D-16); el lugar del que salieron es solo un rastro.
@track_table(meta={"db_table": "itinerario_parada_cambio"})
class ItineraryStop(ApiModel):
    itinerary = ForeignKey(
        db_column="itinerario_id",
        on_delete=CASCADE,
        related_name="stops",
        to=Itinerary,
    )
    point = ForeignKey(
        db_column="punto_interes_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="itinerary_stops",
        to=PointOfInterest,
    )

    name = CharField(db_column="nombre", max_length=80)
    latitude = DecimalField(db_column="latitud", decimal_places=6, max_digits=9)
    longitude = DecimalField(db_column="longitud", decimal_places=6, max_digits=9)
    order = SmallIntegerField(db_column="orden")
    visited_at = DateTimeField(
        db_column="visitada_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "itinerario_parada"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(
                fields=["itinerary", "order"],
                name="unq_itinerarioparada_orden",
            ),
            CheckConstraint(
                condition=Q(order__gte=0),
                name="chk_itinerarioparada_orden_positivo",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            Trigger(
                func=(
                    "IF NOT EXISTS (SELECT 1 FROM itinerario"
                    " WHERE id = NEW.itinerario_id AND ajustado) THEN"
                    " RAISE EXCEPTION"
                    " 'Un itinerario que sigue un circuito no tiene paradas propias.';"
                    " END IF; RETURN NEW;"
                ),
                name="trg_itinerario_sin_paradas_propias",
                operation=Insert,
                when=Before,
            ),
        )


# De qué circuitos se derivó el itinerario (D-17): puede combinar varios.
@track_table(meta={"db_table": "itinerario_circuito_cambio"})
class ItineraryCircuit(ApiModel):
    itinerary = ForeignKey(
        db_column="itinerario_id",
        on_delete=CASCADE,
        related_name="origins",
        to=Itinerary,
    )
    circuit = ForeignKey(
        db_column="circuito_id",
        on_delete=RESTRICT,
        related_name="derived_itineraries",
        to=Circuit,
    )
    order = SmallIntegerField(db_column="orden", db_default=0, default=0)

    class Meta(ApiModel.Meta):
        db_table: str = "itinerario_circuito"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(
                fields=["itinerary", "circuit"],
                name="unq_itinerariocircuito_par",
            ),
        )
