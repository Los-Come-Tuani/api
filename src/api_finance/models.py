from typing import TYPE_CHECKING

from django.db.models import (
    CharField,
    CheckConstraint,
    DateField,
    DateTimeField,
    DecimalField,
    Index,
    IntegerField,
    OneToOneField,
    Q,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import Before, Insert, ReadOnly, Trigger

from api_auth.models import ApiUser
from api_core.models.base import ApiModel
from api_organizations.models import Business
from api_profiles.models import ProviderProfile
from api_services.models import Booking
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`. Todo en córdobas, sin
# centavos (solo córdobas: lo decidió el equipo).
########################################################################################


# Lo que cobra K'Plan: la comisión por reserva (porcentaje), la insignia mensual de un
# lugar y la tarifa por cupón validado. Las cambia el equipo con `billing.manage`.
@track_table(meta={"db_table": "tarifa_cambio"})
class Tariff(ApiModel):
    code = CharField(db_column="codigo", max_length=40)
    label = CharField(db_column="etiqueta", max_length=120)
    value = DecimalField(db_column="valor", decimal_places=2, max_digits=12)
    # `percent` o `nio`
    unit = CharField(db_column="unidad", max_length=16)
    updated_at = DateTimeField(
        db_column="actualizada_en", db_default=Now(), default=now
    )
    updated_by = ForeignKey(
        db_column="actualizada_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "tarifa"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_tarifa_codigo"),
            CheckConstraint(
                condition=Q(value__gte=0), name="chk_tarifa_valor_positivo"
            ),
            CheckConstraint(
                condition=Q(unit__in=["percent", "nio"]),
                name="chk_tarifa_unidad",
            ),
        )


########################################################################################


# El cobro de una reserva. Lo procesa una pasarela intercambiable: hoy la "manual" (el
# turista recibe instrucciones y el equipo confirma); la real se conecta sin cambiar
# esto. Cancelar algo ya cobrado lo deja por reembolsar.
@track_table(meta={"db_table": "pago_cambio"})
class Payment(ApiModel):
    booking = OneToOneField(
        db_column="reserva_id",
        on_delete=RESTRICT,
        related_name="payment",
        to=Booking,
    )
    amount = IntegerField(db_column="monto")
    gateway = CharField(db_column="pasarela", max_length=24)
    status = CharField(
        db_column="estado", db_default="pendiente", default="pendiente", max_length=16
    )
    # lo que la pasarela devuelve (o el número de la transferencia que anota el equipo)
    reference = CharField(
        blank=True, db_column="referencia", db_default="", default="", max_length=120
    )
    instructions = TextField(
        blank=True, db_column="instrucciones", db_default="", default=""
    )

    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)
    confirmed_at = DateTimeField(
        db_column="confirmado_en", db_default=None, default=None, null=True
    )
    confirmed_by = ForeignKey(
        db_column="confirmado_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    refunded_at = DateTimeField(
        db_column="reembolsado_en", db_default=None, default=None, null=True
    )

    class Meta(ApiModel.Meta):
        db_table: str = "pago"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(
                    status__in=[
                        "pendiente",
                        "confirmado",
                        "por_reembolsar",
                        "reembolsado",
                        "anulado",
                    ]
                ),
                name="chk_pago_estado",
            ),
            CheckConstraint(condition=Q(amount__gt=0), name="chk_pago_monto_positivo"),
        )

        indexes: Sequence[Index] = (
            Index(fields=["status", "created_at"], name="idx_pago_bandeja"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["amount", "booking", "created_at"], name="trg_pago_readonly"
            ),
        )


# Lo que se queda K'Plan de una reserva cerrada. La tasa se copia: cambiar la tarifa no
# cambia lo ya cobrado.
@track_table(meta={"db_table": "comision_cambio"})
class Commission(ApiModel):
    booking = OneToOneField(
        db_column="reserva_id",
        on_delete=RESTRICT,
        related_name="commission",
        to=Booking,
    )
    rate = DecimalField(db_column="tasa", decimal_places=2, max_digits=5)
    amount = IntegerField(db_column="monto")
    created_at = DateTimeField(db_column="creada_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "comision"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(rate__gte=0) & Q(rate__lte=100),
                name="chk_comision_tasa_rango",
            ),
            CheckConstraint(
                condition=Q(amount__gte=0), name="chk_comision_monto_positivo"
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["amount", "booking", "rate"], name="trg_comision_inmutable"
            ),
        )


########################################################################################


# La cuenta donde el guía recibe sus retiros. El número va cifrado (D-09) y cambiarla es
# otra fila que surte efecto 24 horas después (D-10): mientras tanto vale la anterior.
@track_table(meta={"db_table": "cuenta_bancaria_cambio"}, exclude=["number_encrypted"])
class BankAccount(ApiModel):
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=CASCADE,
        related_name="bank_accounts",
        to=ProviderProfile,
    )
    bank = CharField(db_column="banco", max_length=80)
    holder = CharField(db_column="titular", max_length=150)
    account_type = CharField(db_column="tipo_cuenta", max_length=16)
    number_encrypted = TextField(db_column="numero_cifrado")
    # para mostrarla sin descifrar
    last4 = CharField(db_column="ultimos_cuatro", max_length=4)
    requested_at = DateTimeField(
        db_column="solicitada_en", db_default=Now(), default=now
    )
    effective_at = DateTimeField(db_column="vigente_desde")

    class Meta(ApiModel.Meta):
        db_table: str = "cuenta_bancaria"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(account_type__in=["ahorro", "corriente"]),
                name="chk_cuentabancaria_tipo",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                fields=["provider", "-effective_at"], name="idx_cuentabancaria_vigente"
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            # el número cifrado sí se reescribe: rotar las llaves lo vuelve a cifrar
            ReadOnly(
                fields=[
                    "account_type",
                    "bank",
                    "effective_at",
                    "holder",
                    "last4",
                    "provider",
                    "requested_at",
                ],
                name="trg_cuentabancaria_inmutable",
            ),
        )


# El guía pide cobrar su saldo. Se descuenta al pedirlo; si el equipo lo rechaza,
# vuelve.
@track_table(meta={"db_table": "solicitud_retiro_cambio"})
class Withdrawal(ApiModel):
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=RESTRICT,
        related_name="withdrawals",
        to=ProviderProfile,
    )
    bank_account = ForeignKey(
        db_column="cuenta_bancaria_id",
        on_delete=RESTRICT,
        related_name="withdrawals",
        to=BankAccount,
    )
    amount = IntegerField(db_column="monto")
    status = CharField(
        db_column="estado", db_default="pendiente", default="pendiente", max_length=16
    )
    requested_at = DateTimeField(
        db_column="solicitada_en", db_default=Now(), default=now
    )
    resolved_at = DateTimeField(
        db_column="resuelta_en", db_default=None, default=None, null=True
    )
    resolved_by = ForeignKey(
        db_column="resuelta_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    reference = CharField(
        blank=True, db_column="referencia", db_default="", default="", max_length=120
    )
    note = TextField(blank=True, db_column="nota", db_default="", default="")

    class Meta(ApiModel.Meta):
        db_table: str = "solicitud_retiro"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(status__in=["pendiente", "pagada", "rechazada"]),
                name="chk_solicitudretiro_estado",
            ),
            CheckConstraint(
                condition=Q(amount__gt=0),
                name="chk_solicitudretiro_monto_positivo",
            ),
        )


# El libro del saldo del guía: abona lo que gana en cada reserva cerrada (menos la
# comisión) y carga lo que retira. La base no deja que quede negativo.
@track_table(meta={"db_table": "movimiento_saldo_cambio"})
class BalanceMovement(ApiModel):
    provider = ForeignKey(
        db_column="perfil_prestador_id",
        on_delete=RESTRICT,
        related_name="balance_movements",
        to=ProviderProfile,
    )
    amount = IntegerField(db_column="monto")
    # `servicio`, `retiro` o `devolucion_retiro`
    kind = CharField(db_column="tipo", max_length=24)
    booking = OneToOneField(
        db_column="reserva_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="balance_movement",
        to=Booking,
    )
    withdrawal = ForeignKey(
        db_column="solicitud_retiro_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="movements",
        to=Withdrawal,
    )
    recorded_at = DateTimeField(
        db_column="registrado_en", db_default=Now(), default=now
    )

    class Meta(ApiModel.Meta):
        db_table: str = "movimiento_saldo"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=(
                    Q(kind="servicio", booking__isnull=False, amount__gt=0)
                    | Q(kind="retiro", withdrawal__isnull=False, amount__lt=0)
                    | Q(
                        kind="devolucion_retiro", withdrawal__isnull=False, amount__gt=0
                    )
                ),
                name="chk_movimientosaldo_origen_coherente",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                fields=["provider", "-recorded_at"], name="idx_movimientosaldo_saldo"
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=[
                    "amount",
                    "booking",
                    "kind",
                    "provider",
                    "recorded_at",
                    "withdrawal",
                ],
                name="trg_movimientosaldo_inmutable",
            ),
            Trigger(
                func=(
                    "IF NEW.monto < 0 AND (SELECT COALESCE(SUM(monto), 0)"
                    " FROM movimiento_saldo"
                    " WHERE perfil_prestador_id = NEW.perfil_prestador_id)"
                    " + NEW.monto < 0 THEN RAISE EXCEPTION"
                    " 'El saldo no alcanza para ese retiro.';"
                    " END IF; RETURN NEW;"
                ),
                name="trg_movimientosaldo_saldo_suficiente",
                operation=Insert,
                when=Before,
            ),
        )


########################################################################################


# El estado de cuenta mensual de un comercio: la insignia de su lugar y los cupones que
# validó. Lo emite `issuestatements`; el equipo lo cobra fuera de línea y lo marca
# pagado.
@track_table(meta={"db_table": "estado_cuenta_cambio"})
class Statement(ApiModel):
    business = ForeignKey(
        db_column="comercio_id",
        on_delete=RESTRICT,
        related_name="statements",
        to=Business,
    )
    # el primer día del mes que cobra
    period = DateField(db_column="periodo")
    total = IntegerField(db_column="total")
    status = CharField(
        db_column="estado", db_default="pendiente", default="pendiente", max_length=16
    )
    issued_at = DateTimeField(db_column="emitido_en", db_default=Now(), default=now)
    paid_at = DateTimeField(
        db_column="pagado_en", db_default=None, default=None, null=True
    )
    paid_by = ForeignKey(
        db_column="pagado_registrado_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )
    reference = CharField(
        blank=True, db_column="referencia", db_default="", default="", max_length=120
    )

    class Meta(ApiModel.Meta):
        db_table: str = "estado_cuenta"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            UniqueConstraint(
                fields=["business", "period"], name="unq_estadocuenta_periodo"
            ),
            CheckConstraint(
                condition=Q(status__in=["pendiente", "pagado", "anulado"]),
                name="chk_estadocuenta_estado",
            ),
            CheckConstraint(
                condition=Q(total__gte=0), name="chk_estadocuenta_total_positivo"
            ),
        )


@track_table(meta={"db_table": "linea_estado_cuenta_cambio"})
class StatementLine(ApiModel):
    statement = ForeignKey(
        db_column="estado_cuenta_id",
        on_delete=CASCADE,
        related_name="lines",
        to=Statement,
    )
    concept = CharField(db_column="concepto", max_length=40)
    description = CharField(db_column="descripcion", max_length=200)
    quantity = IntegerField(db_column="cantidad")
    unit_price = IntegerField(db_column="precio_unitario")
    amount = IntegerField(db_column="monto")

    class Meta(ApiModel.Meta):
        db_table: str = "linea_estado_cuenta"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(quantity__gt=0) & Q(unit_price__gte=0) & Q(amount__gte=0),
                name="chk_lineaestadocuenta_montos",
            ),
        )
