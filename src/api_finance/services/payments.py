from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Final

from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_core.services.pages import paginate
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_finance.models import BalanceMovement, Commission, Payment, Tariff
from api_finance.schemas import PaymentGet, TariffGet
from api_finance.seeder import BADGE_MONTHLY, COMMISSION_RATE, COUPON_FEE
from api_finance.services.gateway import get_gateway
from api_notifications.services import notify
from api_services.models import Booking, BookingStatus

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_finance.schemas import PaymentQuery, PricingPut
    from api_territory.services.access import Actor

########################################################################################

PAYMENT_API: Final[dict[str, str]] = {
    "anulado": "void",
    "confirmado": "confirmed",
    "pendiente": "pending",
    "por_reembolsar": "refund_due",
    "reembolsado": "refunded",
}
PAYMENT_BY_API: Final[dict[str, str]] = {
    name: code for code, name in PAYMENT_API.items()
}

# - el estado del pago que se copia en la reserva (`estado_pago`)
BOOKING_PAYMENT: Final[dict[str, str]] = {
    "anulado": "anulado",
    "confirmado": "pagado",
    "pendiente": "pendiente",
    "por_reembolsar": "por_reembolsar",
    "reembolsado": "reembolsado",
}

########################################################################################
# Tarifas


def tariff(code: str) -> Decimal:
    return Decimal(Tariff.objects.get(code=code).value)


def tariffs_payload() -> list[TariffGet]:
    return [
        TariffGet(
            code=str(item.code),
            label=str(item.label),
            unit=item.unit,
            updated_at=item.updated_at,
            value=float(item.value),
        )
        for item in Tariff.objects.order_by("code")
    ]


def pricing_sync(actor: Actor) -> list[TariffGet]:
    if not actor.can(P.BILLING_VIEW):
        raise ForbiddenError

    return tariffs_payload()


def update_pricing_sync(actor: Actor, data: PricingPut) -> list[TariffGet]:
    if not actor.can(P.BILLING_MANAGE):
        raise ForbiddenError

    for code, value in (
        (COMMISSION_RATE, data.commission_rate),
        (BADGE_MONTHLY, data.badge_monthly),
        (COUPON_FEE, data.coupon_fee),
    ):
        if value is not None:
            Tariff.objects.filter(code=code).update(
                updated_at=now(),
                updated_by=actor.user,
                value=Decimal(str(value)),
            )

    return tariffs_payload()


########################################################################################
# El cobro de una reserva


def mirror(booking_id: UUID, status: str) -> None:
    Booking.objects.filter(pk=booking_id).update(payment_status=BOOKING_PAYMENT[status])


# Al nacer la reserva se abre su cobro con la pasarela. Una reserva gratis no cobra.
def open_payment(booking: Booking) -> None:
    found: Any = booking

    if int(found.amount) <= 0:
        return

    gateway = get_gateway()
    payment: Payment = Payment.objects.create(
        amount=found.amount,
        booking=booking,
        gateway=gateway.name,
    )
    intent = gateway.create_intent(payment)

    Payment.objects.filter(pk=payment.pk).update(
        instructions=intent.instructions,
        reference=intent.reference,
    )
    mirror(found.pk, "pendiente")


# Cancelar la reserva anula lo que no se cobró y deja por reembolsar lo cobrado.
def cancel_payment(booking: Booking) -> None:
    payment: Any = Payment.objects.filter(booking=booking).first()

    if payment is None:
        return

    status: str | None = {"confirmado": "por_reembolsar", "pendiente": "anulado"}.get(
        str(payment.status)
    )

    if status is not None:
        Payment.objects.filter(pk=payment.pk).update(status=status)
        mirror(payment.booking_id, status)


# Cierra la reserva prestada y cobrada: la comisión de K'Plan (con la tasa de hoy,
# copiada) y lo demás al saldo del guía. Una sola vez.
def settle(booking_id: UUID) -> None:
    booking: Any = (
        Booking.objects
        .select_for_update(of=("self",))
        .select_related("status")
        .filter(pk=booking_id)
        .first()
    )

    if booking is None or booking.status.code != "prestada":
        return

    payment: Any = Payment.objects.filter(booking=booking).first()
    paid: bool = payment is not None and payment.status == "confirmado"
    free: bool = int(booking.amount) == 0

    if not (paid or free) or Commission.objects.filter(booking=booking).exists():
        return

    rate: Decimal = tariff(COMMISSION_RATE)
    commission: int = int(
        (Decimal(int(booking.amount)) * rate / 100).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )

    Commission.objects.create(amount=commission, booking=booking, rate=rate)

    if int(booking.amount) - commission > 0:
        BalanceMovement.objects.create(
            amount=int(booking.amount) - commission,
            booking=booking,
            kind="servicio",
            provider_id=booking.provider_id,
        )

    Booking.objects.filter(pk=booking.pk).update(
        status=BookingStatus.objects.get(code="cerrada")
    )


########################################################################################
# Lo que ve el equipo


def payments() -> QuerySet:
    return Payment.objects.select_related(
        "booking__provider__user",
        "booking__user",
    )


def payment_payload(payment: Payment) -> PaymentGet:
    found: Any = payment

    return PaymentGet(
        amount=int(found.amount),
        booking_id=found.booking_id,
        confirmed_at=found.confirmed_at,
        created_at=found.created_at,
        gateway=str(found.gateway),
        guide_name=found.booking.provider.user.display_name,
        id=found.pk,
        instructions=str(found.instructions),
        reference=str(found.reference),
        refunded_at=found.refunded_at,
        status=PAYMENT_API[str(found.status)],  # ty: ignore[invalid-argument-type]
        tourist_name=found.booking.user.display_name,
    )


def payments_sync(actor: Actor, query: PaymentQuery) -> Paginated[PaymentGet]:
    if not actor.can(P.BILLING_VIEW):
        raise ForbiddenError

    found = payments()

    if query.status is not None:
        found = found.filter(status=PAYMENT_BY_API[query.status])

    return paginate(
        found.order_by("created_at", "id"), query, payment_payload, PaymentGet
    )


def locked_payment(payment_id: UUID) -> Payment:
    payment: Payment | None = (
        Payment.objects.select_for_update(of=("self",)).filter(pk=payment_id).first()
    )

    if payment is None:
        raise NotFoundError(detail="No encontramos ese pago.")

    return payment


def confirm_payment_sync(actor: Actor, payment_id: UUID, reference: str) -> PaymentGet:
    if not actor.can(P.BILLING_MANAGE):
        raise ForbiddenError

    with atomic():
        payment: Any = locked_payment(payment_id)

        if payment.status != "pendiente":
            raise ConflictError(detail="Ese pago no está pendiente.")

        Payment.objects.filter(pk=payment.pk).update(
            confirmed_at=now(),
            confirmed_by=actor.user,
            reference=reference.strip() or payment.reference,
            status="confirmado",
        )
        mirror(payment.booking_id, "confirmado")

        # si el recorrido ya se prestó, se cierra ahora
        settle(payment.booking_id)

        booking: Any = Booking.objects.get(pk=payment.booking_id)
        notify(
            booking.user_id,
            "pago",
            "Pago confirmado",
            "Confirmamos el pago de tu reserva.",
            {"booking_id": str(booking.pk)},
        )

    return payment_payload(payments().get(pk=payment_id))


def refund_payment_sync(actor: Actor, payment_id: UUID, reference: str) -> PaymentGet:
    if not actor.can(P.BILLING_MANAGE):
        raise ForbiddenError

    with atomic():
        payment: Any = locked_payment(payment_id)

        if payment.status != "por_reembolsar":
            raise ConflictError(detail="Ese pago no está por reembolsar.")

        Payment.objects.filter(pk=payment.pk).update(
            reference=reference.strip() or payment.reference,
            refunded_at=now(),
            status="reembolsado",
        )
        mirror(payment.booking_id, "reembolsado")

        booking: Any = Booking.objects.get(pk=payment.booking_id)
        notify(
            booking.user_id,
            "pago",
            "Reembolso hecho",
            "Te devolvimos el pago de la reserva cancelada.",
            {"booking_id": str(booking.pk)},
        )

    return payment_payload(payments().get(pk=payment_id))
