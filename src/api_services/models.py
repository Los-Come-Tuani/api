from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
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
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import ReadOnly, Trigger

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_itineraries.models import Itinerary
from api_profiles.models import ProviderProfile
from api_territory.models import Circuit, City
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
#
# Dos caminos llevan a una reserva (M9): en un circuito oficial, el guía publica sus
# salidas y el turista reserva una; en un itinerario propio del turista, el turista
# publica una convocatoria, los guías se postulan y él elige.
########################################################################################


# El guía guiará un circuito oficial en esta fecha y hora. En los de grupo (creativos y
# especiales en grupo) varias reservas comparten la salida hasta llenar los cupos; en
# los privados (`exclusive`) la primera reserva se la queda.
@track_table(meta={"db_table": "salida_guiada_cambio"})
class GuidedDeparture(ApiModel):
    circuit = ForeignKey(
        db_column="circuito_id",
        on_delete=RESTRICT,
        related_name="departures",
        to=Circuit,
    )
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=RESTRICT,
        related_name="departures",
        to=ProviderProfile,
    )

    date = DateField(db_column="fecha")
    start_time = TimeField(db_column="hora_salida")
    capacity = SmallIntegerField(db_column="cupos")
    exclusive = BooleanField(db_column="exclusiva", db_default=False, default=False)
    transport_included = BooleanField(
        db_column="incluye_transporte", db_default=False, default=False
    )
    note = CharField(
        blank=True, db_column="nota", db_default="", default="", max_length=500
    )

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    cancelled_at = DateTimeField(
        db_column="cancelada_en", db_default=None, default=None, null=True
    )
    cancel_reason = CharField(
        blank=True,
        db_column="motivo_cancelacion",
        db_default="",
        default="",
        max_length=500,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "salida_guiada"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(capacity__gte=1) & Q(capacity__lte=50),
                name="chk_salidaguiada_cupos_rango",
            ),
            # un guía no sale dos veces a la misma hora
            UniqueConstraint(
                condition=Q(cancelled_at__isnull=True),
                fields=["provider", "date", "start_time"],
                name="unq_salidaguiada_guia_hora",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                condition=Q(cancelled_at__isnull=True),
                fields=["circuit", "date"],
                name="idx_salidaguiada_circuito",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_salidaguiada_readonly_creadoen"),
        )


########################################################################################


# Abierta, adjudicada, cancelada y expirada: solo la abierta recibe postulaciones.
@track_table(meta={"db_table": "estado_convocatoria_cambio"})
class RequestStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    accepts_applications = BooleanField(db_column="admite_postulaciones")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_convocatoria"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoconvocatoria_codigo"),
        )


# El turista busca guía para su itinerario propio: fecha, hora, cuántos van y, si
# quiere, hasta cuánto paga. Los guías de esa ciudad (o de todo el país) se postulan.
@track_table(meta={"db_table": "convocatoria_cambio"})
class ServiceRequest(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="service_requests",
        to=ApiUser,
    )
    itinerary = ForeignKey(
        db_column="itinerario_id",
        on_delete=RESTRICT,
        related_name="service_requests",
        to=Itinerary,
    )
    # dónde ocurre: decide qué guías la ven
    city = ForeignKey(
        db_column="ciudad_id",
        on_delete=RESTRICT,
        related_name="service_requests",
        to=City,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="requests",
        to=RequestStatus,
    )

    date = DateField(db_column="fecha")
    start_time = TimeField(db_column="hora_inicio")
    adults = SmallIntegerField(db_column="adultos", db_default=1, default=1)
    children = SmallIntegerField(db_column="ninos", db_default=0, default=0)
    # en córdobas; nulo es "que el guía proponga"
    max_fee = IntegerField(
        db_column="tarifa_maxima", db_default=None, default=None, null=True
    )
    note = TextField(blank=True, db_column="nota", db_default="", default="")

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    closed_at = DateTimeField(
        db_column="cerrada_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "convocatoria"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(adults__gte=1) & Q(children__gte=0),
                name="chk_convocatoria_grupo_valido",
            ),
            CheckConstraint(
                condition=Q(adults__lte=50) & Q(children__lte=50),
                name="chk_convocatoria_grupo_tope",
            ),
            CheckConstraint(
                condition=Q(max_fee__isnull=True) | Q(max_fee__gt=0),
                name="chk_convocatoria_tarifa_positiva",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["city", "status", "date"], name="idx_convocatoria_ciudad"),
        )


# Un guía se ofrece para una convocatoria, con su precio.
@track_table(meta={"db_table": "postulacion_cambio"})
class Application(ApiModel):
    request = ForeignKey(
        db_column="convocatoria_id",
        on_delete=CASCADE,
        related_name="applications",
        to=ServiceRequest,
    )
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=RESTRICT,
        related_name="applications",
        to=ProviderProfile,
    )

    # en córdobas, por el servicio completo
    fee = IntegerField(db_column="tarifa")
    message = TextField(blank=True, db_column="mensaje", db_default="", default="")
    status = CharField(
        db_column="estado", db_default="enviada", default="enviada", max_length=16
    )
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "postulacion"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(
                    status__in=["enviada", "aceptada", "rechazada", "retirada"]
                ),
                name="chk_postulacion_estado",
            ),
            CheckConstraint(
                condition=Q(fee__gt=0), name="chk_postulacion_tarifa_positiva"
            ),
            # un guía se postula una vez a cada convocatoria
            UniqueConstraint(
                fields=["request", "provider"],
                name="unq_postulacion_guia",
            ),
        )


########################################################################################


# Confirmada, en curso, prestada, cerrada y cancelada. Sin cobro en línea hasta F8.
@track_table(meta={"db_table": "estado_reserva_cambio"})
class BookingStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    allows_cancellation = BooleanField(db_column="admite_cancelacion")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_reserva"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadoreserva_codigo"),
        )


# El servicio acordado entre un turista y un guía. Nace de una salida o de una
# postulación aceptada; desde ahí todo es igual: chat, cierre y reseñas. La tarifa se
# congela al reservar (D-20): cambiar el precio del circuito no la mueve.
@track_table(meta={"db_table": "reserva_cambio"})
class Booking(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="bookings",
        to=ApiUser,
    )
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=RESTRICT,
        related_name="bookings",
        to=ProviderProfile,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="bookings",
        to=BookingStatus,
    )

    # de dónde nació: una salida del guía o una postulación aceptada
    departure = ForeignKey(
        db_column="salida_guiada_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="bookings",
        to=GuidedDeparture,
    )
    application = OneToOneField(
        db_column="postulacion_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="booking",
        to=Application,
    )
    # qué se recorre: el circuito oficial o el itinerario propio
    circuit = ForeignKey(
        db_column="circuito_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="bookings",
        to=Circuit,
    )
    itinerary = ForeignKey(
        db_column="itinerario_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="bookings",
        to=Itinerary,
    )

    date = DateField(db_column="fecha")
    start_time = TimeField(db_column="hora_inicio")
    adults = SmallIntegerField(db_column="adultos", db_default=1, default=1)
    children = SmallIntegerField(db_column="ninos", db_default=0, default=0)
    # congelada al reservar, en córdobas
    amount = IntegerField(db_column="monto")
    # sin pasarela todavía: el cobro se conecta en F8
    payment_status = CharField(
        db_column="estado_pago",
        db_default="sin_cobro",
        default="sin_cobro",
        max_length=16,
    )

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    started_at = DateTimeField(
        db_column="iniciada_en", db_default=None, default=None, null=True
    )
    finished_at = DateTimeField(
        db_column="prestada_en", db_default=None, default=None, null=True
    )
    cancelled_at = DateTimeField(
        db_column="cancelada_en", db_default=None, default=None, null=True
    )
    cancelled_by = ForeignKey(
        db_column="cancelada_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    cancel_reason = CharField(
        blank=True,
        db_column="motivo_cancelacion",
        db_default="",
        default="",
        max_length=500,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "reserva"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=(
                    Q(departure__isnull=False, application__isnull=True)
                    | Q(departure__isnull=True, application__isnull=False)
                ),
                name="chk_reserva_origen_excluyente",
            ),
            CheckConstraint(
                condition=Q(circuit__isnull=False) | Q(itinerary__isnull=False),
                name="chk_reserva_recorrido_presente",
            ),
            CheckConstraint(
                condition=Q(adults__gte=1) & Q(children__gte=0),
                name="chk_reserva_grupo_valido",
            ),
            CheckConstraint(
                condition=Q(amount__gte=0), name="chk_reserva_monto_positivo"
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["user", "-date"], name="idx_reserva_turista"),
            Index(fields=["provider", "date"], name="idx_reserva_prestador"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["amount", "created_at", "departure", "application", "user"],
                name="trg_reserva_readonly_acuerdo",
            ),
        )
