from datetime import date
from typing import TYPE_CHECKING, Any, Final

from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_core.services.pages import paginate
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_finance.models import Statement, StatementLine
from api_finance.schemas import StatementGet, StatementLineGet
from api_finance.seeder import BADGE_MONTHLY, COUPON_FEE
from api_finance.services.payments import tariff
from api_organizations.models import Business
from api_rewards.models import Badge, Coupon

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_finance.schemas import StatementQuery
    from api_territory.services.access import Actor

########################################################################################

STATEMENT_API: Final[dict[str, str]] = {
    "anulado": "void",
    "pagado": "paid",
    "pendiente": "pending",
}
STATEMENT_BY_API: Final[dict[str, str]] = {
    name: code for code, name in STATEMENT_API.items()
}

########################################################################################
# Emitir


def next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)  # ruff: ignore[magic-value-comparison]


def previous_month(day: date) -> date:
    first = date(day.year, day.month, 1)

    return date(first.year - (first.month == 1), (first.month - 2) % 12 + 1, 1)


# Lo que se cobra a un comercio por un mes: la insignia de su lugar (si la tuvo) y los
# cupones que validó en el mostrador.
def lines_for(business: Business, period: date) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    badge_price = int(tariff(BADGE_MONTHLY))
    coupon_price = int(tariff(COUPON_FEE))

    badge: Any = Badge.objects.filter(active=True, point__business=business).first()

    if badge is not None and badge_price > 0:
        lines.append({
            "amount": badge_price,
            "concept": "insignia_mensual",
            "description": f"Insignia de {badge.point.name}",
            "quantity": 1,
            "unit_price": badge_price,
        })

    validated: int = Coupon.objects.filter(
        business=business,
        consumed_at__date__gte=period,
        consumed_at__date__lt=next_month(period),
    ).count()

    if validated and coupon_price > 0:
        lines.append({
            "amount": validated * coupon_price,
            "concept": "cupon_validado",
            "description": "Cupones validados",
            "quantity": validated,
            "unit_price": coupon_price,
        })

    return lines


# Emite el estado de cuenta del mes de cada comercio verificado que tenga algo que
# cobrar. Volver a correrlo no duplica nada.
def issue_statements(period: date) -> int:
    issued: int = 0

    for business in Business.objects.filter(verified_at__isnull=False):
        if Statement.objects.filter(business=business, period=period).exists():
            continue

        lines = lines_for(business, period)

        if not lines:
            continue

        with atomic():
            statement: Statement = Statement.objects.create(
                business=business,
                period=period,
                total=sum(int(line["amount"]) for line in lines),
            )

            StatementLine.objects.bulk_create(
                StatementLine(statement=statement, **line) for line in lines
            )

        issued += 1

    return issued


########################################################################################
# Lectura y cobro


def statements() -> QuerySet:
    return Statement.objects.select_related("business").prefetch_related("lines")


def statement_payload(statement: Statement) -> StatementGet:
    found: Any = statement

    return StatementGet(
        business_id=found.business_id,
        business_name=str(found.business.name),
        id=found.pk,
        issued_at=found.issued_at,
        lines=[
            StatementLineGet(
                amount=int(line.amount),
                concept=str(line.concept),
                description=str(line.description),
                quantity=int(line.quantity),
                unit_price=int(line.unit_price),
            )
            for line in found.lines.all()
        ],
        paid_at=found.paid_at,
        period=found.period,
        reference=str(found.reference),
        status=STATEMENT_API[str(found.status)],  # ty: ignore[invalid-argument-type]
        total=int(found.total),
    )


# El comercio ve los suyos; el equipo con `billing.view`, todos.
def visible_statements(actor: Actor) -> QuerySet:
    found = statements()

    if actor.can(P.BILLING_VIEW):
        return found

    if actor.organization is not None and actor.operates("business"):
        return found.filter(business_id=actor.organization.id)

    raise ForbiddenError


def statements_sync(actor: Actor, query: StatementQuery) -> Paginated[StatementGet]:
    found = visible_statements(actor)

    if query.status is not None:
        found = found.filter(status=STATEMENT_BY_API[query.status])

    if query.business_id is not None:
        found = found.filter(business_id=query.business_id)

    return paginate(
        found.order_by("-period", "business__name", "id"),
        query,
        statement_payload,
        StatementGet,
    )


def pay_statement_sync(
    actor: Actor, statement_id: UUID, reference: str
) -> StatementGet:
    if not actor.can(P.BILLING_MANAGE):
        raise ForbiddenError

    with atomic():
        statement: Any = (
            Statement.objects.select_for_update().filter(pk=statement_id).first()
        )

        if statement is None:
            raise NotFoundError(detail="No encontramos ese estado de cuenta.")

        if statement.status != "pendiente":
            raise ConflictError(detail="Ese estado de cuenta ya no está pendiente.")

        Statement.objects.filter(pk=statement.pk).update(
            paid_at=now(),
            paid_by=actor.user,
            reference=reference.strip(),
            status="pagado",
        )

    return statement_payload(statements().get(pk=statement_id))
