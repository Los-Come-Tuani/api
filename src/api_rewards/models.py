from typing import TYPE_CHECKING

from django.db.models import (
    BooleanField,
    CharField,
    CheckConstraint,
    DateTimeField,
    DecimalField,
    F,
    Index,
    IntegerField,
    OneToOneField,
    Q,
    SmallIntegerField,
    TextField,
    UniqueConstraint,
)
from django.db.models.deletion import CASCADE, RESTRICT, SET_NULL
from django.db.models.fields.related import ForeignKey
from django.db.models.functions import Now
from django.utils.timezone import now
from pgtrigger import (
    Before,
    F as PgF,
    Insert,
    Q as PgQ,
    ReadOnly,
    Trigger,
    UpdateOf,
)

from api_auth.models import ApiUser
from api_catalogs.models import BenefitType, Currency
from api_core.models.base import ApiModel
from api_organizations.models import Business
from api_territory.models import PointOfInterest
from api_utils.db import track_table

if TYPE_CHECKING:
    from collections.abc import Sequence

# Los disparadores que nombran columnas llevan el nombre real de la columna, en español.
########################################################################################
# Las tablas y columnas están en español (modelo de dominio, `Convenciones`); el código
# Python sigue en inglés. Cada campo declara su `db_column`.
#
# El modelo cuelga visitas, movimientos y cupones de `perfil_turista`; mientras ese
# perfil no existe, cuelgan de la cuenta.
########################################################################################

# - el alfabeto de los códigos de cupón: sin I, O, 0 ni 1, que se confunden al dictarlos
COUPON_ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# Lo que otorga un lugar al ser visitado (M12). Una por lugar; el comercio la tiene por
# su lugar. `qr_token` es lo que va impreso en el QR del local: sin él no se acredita.
@track_table(meta={"db_table": "insignia_cambio"}, exclude=["qr_token"])
class Badge(ApiModel):
    point = OneToOneField(
        db_column="punto_interes_id",
        on_delete=RESTRICT,
        related_name="badge",
        to=PointOfInterest,
    )

    name = CharField(db_column="nombre", max_length=120)
    # cuántas insignias da la visita
    value = SmallIntegerField(db_column="valor", db_default=1, default=1)
    # dejar de darla no toca las ya acreditadas
    active = BooleanField(db_column="activa", db_default=True, default=True)
    qr_token = CharField(db_column="codigo_qr", max_length=64)
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "insignia"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(value__gt=0) & Q(value__lte=10),
                name="chk_insignia_valor_positivo",
            ),
            UniqueConstraint(fields=["qr_token"], name="unq_insignia_codigoqr"),
        )


# El hecho de que un turista escaneó el QR de un lugar estando a menos de cincuenta
# metros. No se corrige ni se borra; una por lugar y turista cada 24 horas (RF-S-15).
@track_table(meta={"db_table": "visita_acreditada_cambio"})
class Visit(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="visits",
        to=ApiUser,
    )
    badge = ForeignKey(
        db_column="insignia_id",
        on_delete=RESTRICT,
        related_name="visits",
        to=Badge,
    )

    # dónde estaba el teléfono y a qué distancia: la evidencia si alguien la disputa
    latitude = DecimalField(db_column="latitud", decimal_places=6, max_digits=9)
    longitude = DecimalField(db_column="longitud", decimal_places=6, max_digits=9)
    distance_meters = SmallIntegerField(db_column="distancia_metros")
    accredited_at = DateTimeField(
        db_column="acreditada_en", db_default=Now(), default=now
    )

    class Meta(ApiModel.Meta):
        db_table: str = "visita_acreditada"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(distance_meters__gte=0) & Q(distance_meters__lte=50),
                name="chk_visitaacreditada_distancia",
            ),
            CheckConstraint(
                condition=Q(latitude__gte=10.7) & Q(latitude__lte=15.1),
                name="chk_visitaacreditada_latitud_rango",
            ),
            CheckConstraint(
                condition=Q(longitude__gte=-87.7) & Q(longitude__lte=-82.6),
                name="chk_visitaacreditada_longitud_rango",
            ),
        )

        indexes: Sequence[Index] = (
            Index(
                fields=["user", "badge", "-accredited_at"],
                name="idx_visitaacreditada_ventana",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=[
                    "accredited_at",
                    "badge",
                    "distance_meters",
                    "latitude",
                    "longitude",
                    "user",
                ],
                name="trg_visitaacreditada_inmutable",
            ),
            Trigger(
                func=(
                    "IF EXISTS (SELECT 1 FROM visita_acreditada"
                    " WHERE usuario_id = NEW.usuario_id"
                    " AND insignia_id = NEW.insignia_id"
                    " AND acreditada_en > NEW.acreditada_en - interval '24 hours')"
                    " THEN RAISE EXCEPTION"
                    " 'Ese lugar ya acreditó una visita en las últimas 24 horas.';"
                    " END IF; RETURN NEW;"
                ),
                name="trg_visitaacreditada_ventana",
                operation=Insert,
                when=Before,
            ),
        )


########################################################################################


# Activa, agotada, retirada y expirada: solo la activa admite canje.
@track_table(meta={"db_table": "estado_campania_cambio"})
class CampaignStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    allows_redemption = BooleanField(db_column="admite_canje")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_campania"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadocampania_codigo"),
        )


# La promoción que publica un comercio: qué beneficio, cuántos cupones y a qué costo en
# insignias. Sale al crearse; el equipo con `content.moderate` puede retirarla.
@track_table(meta={"db_table": "campania_cupon_cambio"})
class CouponCampaign(ApiModel):
    business = ForeignKey(
        db_column="comercio_id",
        on_delete=RESTRICT,
        related_name="coupon_campaigns",
        to=Business,
    )
    benefit_type = ForeignKey(
        db_column="tipo_beneficio_id",
        on_delete=RESTRICT,
        related_name="campaigns",
        to=BenefitType,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="campaigns",
        to=CampaignStatus,
    )

    title = CharField(db_column="titulo", max_length=80)
    description = TextField(
        blank=True, db_column="descripcion", db_default="", default=""
    )
    terms = TextField(blank=True, db_column="condiciones", db_default="", default="")
    # el porcentaje o los córdobas; nulo si el tipo no exige monto
    benefit_amount = DecimalField(
        db_column="monto_beneficio",
        db_default=None,
        decimal_places=2,
        default=None,
        max_digits=12,
        null=True,
    )
    # nula si el beneficio es porcentual o no lleva monto
    currency = ForeignKey(
        db_column="moneda_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="+",
        to=Currency,
    )
    cost_badges = SmallIntegerField(db_column="costo_insignias")
    stock_total = IntegerField(db_column="stock_total")
    stock_delivered = IntegerField(db_column="stock_entregado", db_default=0, default=0)
    image_key = CharField(
        blank=True, db_column="imagen_id", db_default="", default="", max_length=500
    )

    expires_at = DateTimeField(db_column="expira_en")
    withdrawn_at = DateTimeField(
        db_column="retirada_en", db_default=None, default=None, null=True
    )
    # quién la retiró y por qué: el comercio o el equipo al moderar
    withdrawn_reason = CharField(
        blank=True,
        db_column="motivo_retiro",
        db_default="",
        default="",
        max_length=500,
    )
    created_at = DateTimeField(db_column="creado_en", db_default=Now(), default=now)

    class Meta(ApiModel.Meta):
        db_table: str = "campania_cupon"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=Q(cost_badges__gt=0),
                name="chk_campaniacupon_costo_positivo",
            ),
            CheckConstraint(
                condition=Q(stock_total__gt=0),
                name="chk_campaniacupon_stock_positivo",
            ),
            CheckConstraint(
                condition=Q(stock_delivered__gte=0)
                & Q(stock_delivered__lte=F("stock_total")),
                name="chk_campaniacupon_stock_coherente",
            ),
            CheckConstraint(
                condition=Q(benefit_amount__isnull=True) | Q(benefit_amount__gt=0),
                name="chk_campaniacupon_monto_positivo",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["status", "expires_at"], name="idx_campaniacupon_tienda"),
            Index(
                fields=["business", "-expires_at"],
                name="idx_campaniacupon_comercio",
            ),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(fields=["created_at"], name="trg_campaniacupon_readonly_creadoen"),
        )


# Vigente, consumido y expirado. Retirar la campaña no toca los cupones entregados.
@track_table(meta={"db_table": "estado_cupon_cambio"})
class CouponStatus(ApiModel):
    code = CharField(db_column="codigo", max_length=24)
    label = CharField(db_column="etiqueta", max_length=60)
    allows_validation = BooleanField(db_column="admite_validacion")
    is_terminal = BooleanField(db_column="es_terminal")

    class Meta(ApiModel.Meta):
        db_table: str = "estado_cupon"

        constraints: Sequence[UniqueConstraint] = (
            UniqueConstraint(fields=["code"], name="unq_estadocupon_codigo"),
        )


# El código concreto que obtuvo un turista. Copia su beneficio de la campaña (D-25): si
# el comercio la retira, lo ya entregado vale lo mismo hasta su fecha límite.
@track_table(meta={"db_table": "cupon_cambio"})
class Coupon(ApiModel):
    campaign = ForeignKey(
        db_column="campania_id",
        on_delete=RESTRICT,
        related_name="coupons",
        to=CouponCampaign,
    )
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="coupons",
        to=ApiUser,
    )
    business = ForeignKey(
        db_column="comercio_id",
        on_delete=RESTRICT,
        related_name="coupons",
        to=Business,
    )
    status = ForeignKey(
        db_column="estado_id",
        on_delete=RESTRICT,
        related_name="coupons",
        to=CouponStatus,
    )

    # se dicta en el mostrador: ocho caracteres legibles
    code = CharField(db_column="codigo", max_length=8)
    title = CharField(db_column="titulo", max_length=80)
    benefit_type = ForeignKey(
        db_column="tipo_beneficio_id",
        on_delete=RESTRICT,
        related_name="+",
        to=BenefitType,
    )
    benefit_amount = DecimalField(
        db_column="monto_beneficio",
        db_default=None,
        decimal_places=2,
        default=None,
        max_digits=12,
        null=True,
    )
    currency = ForeignKey(
        db_column="moneda_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=RESTRICT,
        related_name="+",
        to=Currency,
    )
    cost_badges = SmallIntegerField(db_column="costo_insignias")
    expires_at = DateTimeField(db_column="expira_en")

    redeemed_at = DateTimeField(db_column="canjeado_en", db_default=Now(), default=now)
    consumed_at = DateTimeField(
        db_column="consumido_en", db_default=None, default=None, null=True
    )
    # quién del comercio lo validó
    consumed_by = ForeignKey(
        db_column="consumido_por",
        db_default=None,
        default=None,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
        to=ApiUser,
    )

    class Meta(ApiModel.Meta):
        db_table: str = "cupon"

        constraints: Sequence[CheckConstraint | UniqueConstraint] = (
            CheckConstraint(
                condition=Q(code__regex=rf"^[{COUPON_ALPHABET}]{{8}}$"),
                name="chk_cupon_codigo_formato",
            ),
            CheckConstraint(
                condition=Q(consumed_at__isnull=True)
                | Q(consumed_at__gte=F("redeemed_at")),
                name="chk_cupon_consumo_coherente",
            ),
            UniqueConstraint(fields=["code"], name="unq_cupon_codigo"),
        )

        indexes: Sequence[Index] = (
            Index(fields=["user", "-expires_at"], name="idx_cupon_billetera"),
            Index(fields=["business", "code"], name="idx_cupon_validacion"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=[
                    "benefit_amount",
                    "benefit_type",
                    "business",
                    "campaign",
                    "code",
                    "cost_badges",
                    "currency",
                    "expires_at",
                    "redeemed_at",
                    "user",
                ],
                name="trg_cupon_readonly_beneficio",
            ),
            Trigger(
                condition=PgQ(old__consumed_at__isnull=False)
                & PgQ(old__consumed_at__df=PgF("new__consumed_at")),
                func="RAISE EXCEPTION 'Un cupón consumido no se vuelve a usar.';",
                name="trg_cupon_norevive",
                operation=UpdateOf("consumido_en"),
                when=Before,
            ),
        )


########################################################################################


# El libro del saldo (D-24): cada fila abona por una visita o carga por un cupón. El
# saldo es la suma, y un disparador impide que quede negativo.
@track_table(meta={"db_table": "movimiento_insignia_cambio"})
class BadgeMovement(ApiModel):
    user = ForeignKey(
        db_column="usuario_id",
        on_delete=RESTRICT,
        related_name="badge_movements",
        to=ApiUser,
    )
    amount = SmallIntegerField(db_column="cantidad")
    visit = OneToOneField(
        db_column="visita_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="movement",
        to=Visit,
    )
    coupon = OneToOneField(
        db_column="cupon_id",
        db_default=None,
        default=None,
        null=True,
        on_delete=CASCADE,
        related_name="movement",
        to=Coupon,
    )
    recorded_at = DateTimeField(
        db_column="registrado_en", db_default=Now(), default=now
    )

    class Meta(ApiModel.Meta):
        db_table: str = "movimiento_insignia"

        constraints: Sequence[CheckConstraint] = (
            CheckConstraint(
                condition=(
                    Q(visit__isnull=False, coupon__isnull=True, amount__gt=0)
                    | Q(visit__isnull=True, coupon__isnull=False, amount__lt=0)
                ),
                name="chk_movimientoinsignia_origen_coherente",
            ),
        )

        indexes: Sequence[Index] = (
            Index(fields=["user", "-recorded_at"], name="idx_movimientoinsignia_saldo"),
        )

        triggers: Sequence[Trigger] = (
            *ApiModel.Meta.triggers,
            ReadOnly(
                fields=["amount", "coupon", "recorded_at", "user", "visit"],
                name="trg_movimientoinsignia_inmutable",
            ),
            Trigger(
                func=(
                    "IF NEW.cantidad < 0 AND (SELECT COALESCE(SUM(cantidad), 0)"
                    " FROM movimiento_insignia WHERE usuario_id = NEW.usuario_id)"
                    " + NEW.cantidad < 0 THEN RAISE EXCEPTION"
                    " 'No alcanzan las insignias para ese canje.';"
                    " END IF; RETURN NEW;"
                ),
                name="trg_movimientoinsignia_saldo_suficiente",
                operation=Insert,
                when=Before,
            ),
        )
