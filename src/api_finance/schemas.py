from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_territory.schemas.common import Reference

########################################################################################

type PaymentStatusName = Literal[
    "pending", "confirmed", "refund_due", "refunded", "void"
]
type WithdrawalStatusName = Literal["pending", "paid", "rejected"]
type StatementStatusName = Literal["pending", "paid", "void"]
type ReferenceText = Annotated[str, StringConstraints(max_length=120)]

########################################################################################
# Tarifas


class TariffGet(DTO):
    code: str
    label: str
    value: float
    # `percent` (la comisión) o `nio` (córdobas)
    unit: Literal["percent", "nio"]
    updated_at: datetime


class PricingPut(DTO):
    # solo se cambian las que llegan
    commission_rate: Annotated[float, Field(ge=0, le=100, strict=False)] | None = None
    badge_monthly: Annotated[float, Field(ge=0, le=1_000_000, strict=False)] | None = (
        None
    )
    coupon_fee: Annotated[float, Field(ge=0, le=1_000_000, strict=False)] | None = None


########################################################################################
# Pagos


class PaymentGet(DTO):
    id: UUID
    booking_id: UUID
    amount: int
    gateway: str
    status: PaymentStatusName
    reference: str
    instructions: str
    tourist_name: str
    guide_name: str
    created_at: datetime
    confirmed_at: datetime | None
    refunded_at: datetime | None


class PaymentQuery(PageQuery):
    status: PaymentStatusName | None = None


class ReferencePost(DTO):
    # el número de la transferencia o de la operación
    reference: ReferenceText = ""


########################################################################################
# Saldo, cuenta y retiros del guía


class BalanceMovementGet(DTO):
    amount: int
    kind: Literal["servicio", "retiro", "devolucion_retiro"]
    booking_id: UUID | None
    withdrawal_id: UUID | None
    recorded_at: datetime


class GuideBalanceGet(DTO):
    # lo que puede retirar
    balance: int
    # lo que pidió y todavía no se le pagó (ya descontado del saldo)
    pending_withdrawals: NonNegativeInt
    movements: list[BalanceMovementGet]


class BankAccountGet(DTO):
    id: UUID
    bank: str
    holder: str
    account_type: Literal["ahorro", "corriente"]
    # solo los últimos cuatro dígitos
    last4: str
    effective_at: datetime


class BankAccountsGet(DTO):
    # la que vale hoy
    active: BankAccountGet | None
    # un cambio que todavía espera sus 24 horas
    pending: BankAccountGet | None


class BankAccountPost(DTO):
    bank: Annotated[str, StringConstraints(max_length=80, min_length=2)]
    holder: Annotated[str, StringConstraints(max_length=150, min_length=3)]
    account_type: Literal["ahorro", "corriente"]
    number: Annotated[str, StringConstraints(max_length=40, pattern=r"^[\d\s-]{6,40}$")]


class WithdrawalGet(DTO):
    id: UUID
    amount: int
    status: WithdrawalStatusName
    bank_account: BankAccountGet
    reference: str
    note: str
    requested_at: datetime
    resolved_at: datetime | None


class WithdrawalAdminGet(WithdrawalGet):
    guide_name: str
    # completo solo para quien paga (`billing.manage`)
    account_number: str | None


class WithdrawalPost(DTO):
    amount: Annotated[int, Field(ge=1, le=10_000_000)]


class WithdrawalQuery(PageQuery):
    status: WithdrawalStatusName | None = None


class ResolveWithdrawalPost(DTO):
    reference: ReferenceText = ""
    note: Annotated[str, StringConstraints(max_length=500)] = ""


########################################################################################
# Estados de cuenta de los comercios


class StatementLineGet(DTO):
    concept: str
    description: str
    quantity: int
    unit_price: int
    amount: int


class StatementGet(DTO):
    id: UUID
    business_id: UUID
    business_name: str
    # el primer día del mes que cobra
    period: date
    total: int
    status: StatementStatusName
    lines: list[StatementLineGet]
    issued_at: datetime
    paid_at: datetime | None
    reference: str


class StatementQuery(PageQuery):
    status: StatementStatusName | None = None
    business_id: Reference | None = None
