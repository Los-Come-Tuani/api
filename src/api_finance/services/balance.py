from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Sum
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_auth.services.crypto import decrypt_secret, encrypt_secret
from api_core.services.pages import paginate
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_finance.models import BalanceMovement, BankAccount, Withdrawal
from api_finance.schemas import (
    BalanceMovementGet,
    BankAccountGet,
    BankAccountsGet,
    GuideBalanceGet,
    WithdrawalAdminGet,
    WithdrawalGet,
)
from api_notifications.services import notify
from api_profiles.models import ProviderProfile
from api_services.services.guides import active_guide
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_core.schemas.pagination import Paginated
    from api_finance.schemas import BankAccountPost, WithdrawalQuery
    from api_territory.services.access import Actor

########################################################################################

# - una cuenta nueva surte efecto un día después (D-10): mientras tanto vale la anterior
ACCOUNT_DELAY: Final[timedelta] = timedelta(hours=24)
RECENT: Final[int] = 30

WITHDRAWAL_API: Final[dict[str, str]] = {
    "pagada": "paid",
    "pendiente": "pending",
    "rechazada": "rejected",
}
WITHDRAWAL_BY_API: Final[dict[str, str]] = {
    name: code for code, name in WITHDRAWAL_API.items()
}

########################################################################################
# Saldo


def balance_of(provider: ProviderProfile) -> int:
    total: Any = BalanceMovement.objects.filter(provider=provider).aggregate(
        total=Sum("amount")
    )

    return int(total["total"] or 0)


def balance_sync(user: ApiUser) -> GuideBalanceGet:
    provider: ProviderProfile = active_guide(user)
    movements = BalanceMovement.objects.filter(provider=provider).order_by(
        "-recorded_at"
    )[:RECENT]

    return GuideBalanceGet(
        balance=balance_of(provider),
        movements=[
            BalanceMovementGet(
                amount=int(item.amount),
                booking_id=item.booking_id,
                kind=item.kind,
                recorded_at=item.recorded_at,
                withdrawal_id=item.withdrawal_id,
            )
            for item in movements
        ],
        pending_withdrawals=int(
            Withdrawal.objects.filter(provider=provider, status="pendiente").aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        ),
    )


########################################################################################
# Cuenta bancaria


def account_payload(account: BankAccount) -> BankAccountGet:
    found: Any = account

    return BankAccountGet(
        account_type=found.account_type,
        bank=str(found.bank),
        effective_at=found.effective_at,
        holder=str(found.holder),
        id=found.pk,
        last4=str(found.last4),
    )


def active_account(provider: ProviderProfile) -> BankAccount | None:
    return (
        BankAccount.objects
        .filter(effective_at__lte=now(), provider=provider)
        .order_by("-effective_at")
        .first()
    )


def accounts_sync(user: ApiUser) -> BankAccountsGet:
    provider: ProviderProfile = active_guide(user)
    active: BankAccount | None = active_account(provider)
    pending: BankAccount | None = (
        BankAccount.objects
        .filter(effective_at__gt=now(), provider=provider)
        .order_by("-effective_at")
        .first()
    )

    return BankAccountsGet(
        active=None if active is None else account_payload(active),
        pending=None if pending is None else account_payload(pending),
    )


def add_account_sync(user: ApiUser, data: BankAccountPost) -> BankAccountsGet:
    provider: ProviderProfile = active_guide(user)
    digits: str = "".join(char for char in data.number if char.isdigit())

    # la primera surte efecto de una vez; un cambio espera 24 horas
    first: bool = not BankAccount.objects.filter(provider=provider).exists()
    moment = now()

    BankAccount.objects.create(
        account_type=data.account_type,
        bank=data.bank,
        effective_at=moment if first else moment + ACCOUNT_DELAY,
        holder=data.holder,
        last4=digits[-4:],
        number_encrypted=encrypt_secret(digits),
        provider=provider,
        requested_at=moment,
    )

    return accounts_sync(user)


########################################################################################
# Retiros (el guía)


def withdrawal_payload(withdrawal: Withdrawal) -> WithdrawalGet:
    found: Any = withdrawal

    return WithdrawalGet(
        amount=int(found.amount),
        bank_account=account_payload(found.bank_account),
        id=found.pk,
        note=str(found.note),
        reference=str(found.reference),
        requested_at=found.requested_at,
        resolved_at=found.resolved_at,
        status=WITHDRAWAL_API[str(found.status)],  # ty: ignore[invalid-argument-type]
    )


def withdrawals_sync(user: ApiUser) -> list[WithdrawalGet]:
    provider: ProviderProfile = active_guide(user)

    return [
        withdrawal_payload(item)
        for item in Withdrawal.objects
        .select_related("bank_account")
        .filter(provider=provider)
        .order_by("-requested_at")
    ]


# Pedir un retiro lo descuenta del saldo de una vez (queda apartado); si el equipo lo
# rechaza, vuelve.
def request_withdrawal_sync(user: ApiUser, amount: int) -> WithdrawalGet:
    provider: Any = active_guide(user)

    with atomic():
        ProviderProfile.objects.select_for_update().filter(pk=provider.pk).first()

        account: BankAccount | None = active_account(provider)

        if account is None:
            raise invalid("amount", "Primero registra la cuenta donde quieres cobrar.")

        if amount > balance_of(provider):
            raise invalid("amount", "Tu saldo no alcanza para ese retiro.")

        withdrawal: Withdrawal = Withdrawal.objects.create(
            amount=amount,
            bank_account=account,
            provider=provider,
        )
        BalanceMovement.objects.create(
            amount=-amount,
            kind="retiro",
            provider=provider,
            withdrawal=withdrawal,
        )

    return withdrawal_payload(
        Withdrawal.objects.select_related("bank_account").get(pk=withdrawal.pk)
    )


########################################################################################
# Retiros (el equipo)


def admin_payload(withdrawal: Withdrawal, *, reveal: bool) -> WithdrawalAdminGet:
    found: Any = withdrawal

    return WithdrawalAdminGet(
        **dict(withdrawal_payload(withdrawal)),
        # solo quien paga ve el número completo
        account_number=(
            decrypt_secret(str(found.bank_account.number_encrypted)) if reveal else None
        ),
        guide_name=found.provider.user.display_name,
    )


def admin_withdrawals() -> QuerySet:
    return Withdrawal.objects.select_related("bank_account", "provider__user")


def admin_withdrawals_sync(
    actor: Actor,
    query: WithdrawalQuery,
) -> Paginated[WithdrawalAdminGet]:
    if not actor.can(P.BILLING_VIEW):
        raise ForbiddenError

    found = admin_withdrawals()

    if query.status is not None:
        found = found.filter(status=WITHDRAWAL_BY_API[query.status])

    reveal: bool = actor.can(P.BILLING_MANAGE)

    return paginate(
        found.order_by("requested_at", "id"),
        query,
        lambda item: admin_payload(item, reveal=reveal),
        WithdrawalAdminGet,
    )


def resolve_withdrawal_sync(
    actor: Actor,
    withdrawal_id: UUID,
    *,
    paid: bool,
    reference: str,
    note: str,
) -> WithdrawalAdminGet:
    if not actor.can(P.BILLING_MANAGE):
        raise ForbiddenError

    with atomic():
        withdrawal: Any = (
            Withdrawal.objects
            .select_for_update(of=("self",))
            .filter(pk=withdrawal_id)
            .first()
        )

        if withdrawal is None:
            raise NotFoundError(detail="No encontramos ese retiro.")

        if withdrawal.status != "pendiente":
            raise ConflictError(detail="Ese retiro ya se resolvió.")

        if not paid and not note.strip():
            raise invalid("note", "Dile al guía por qué no se pagó.")

        Withdrawal.objects.filter(pk=withdrawal.pk).update(
            note=note.strip(),
            reference=reference.strip(),
            resolved_at=now(),
            resolved_by=actor.user,
            status="pagada" if paid else "rechazada",
        )

        if not paid:
            BalanceMovement.objects.create(
                amount=withdrawal.amount,
                kind="devolucion_retiro",
                provider_id=withdrawal.provider_id,
                withdrawal=withdrawal,
            )

        provider: Any = ProviderProfile.objects.get(pk=withdrawal.provider_id)
        notify(
            provider.user_id,
            "pago",
            "Retiro pagado" if paid else "Retiro rechazado",
            (
                f"Te depositamos C$ {withdrawal.amount}."
                if paid
                else f"No pudimos pagar tu retiro: {note.strip()}"
            ),
            {"withdrawal_id": str(withdrawal.pk)},
        )

    return admin_payload(admin_withdrawals().get(pk=withdrawal_id), reveal=True)
