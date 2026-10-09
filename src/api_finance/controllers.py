from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_finance.schemas import (
    BankAccountPost,
    BankAccountsGet,
    GuideBalanceGet,
    PaymentGet,
    PaymentQuery,
    PricingPut,
    ReferencePost,
    ResolveWithdrawalPost,
    StatementGet,
    StatementQuery,
    TariffGet,
    WithdrawalAdminGet,
    WithdrawalGet,
    WithdrawalPost,
    WithdrawalQuery,
)
from api_finance.services import balance, payments, statements
from api_territory.controllers import as_actor

if TYPE_CHECKING:
    from uuid import UUID

    from api_territory.services.access import Actor

########################################################################################
# Tarifas y pagos (el equipo: `billing.view` ve, `billing.manage` cambia)


class PricingController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[TariffGet]:
        return await as_actor(self.request.user, payments.pricing_sync)

    @modify(status_code=HTTPStatus.OK)
    async def put(self, parsed_body: Body[PricingPut]) -> list[TariffGet]:
        return await as_actor(
            self.request.user, payments.update_pricing_sync, parsed_body
        )


class PaymentController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self, parsed_query: StrictQuery[PaymentQuery]
    ) -> Paginated[PaymentGet]:
        return await as_actor(self.request.user, payments.payments_sync, parsed_query)


class PaymentConfirmController(BaseController[CustomPydanticFastSerializer]):
    # el equipo comprobó el pago (pasarela manual)
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ReferencePost],
        parsed_path: Path[UuidInstancePath],
    ) -> PaymentGet:
        return await as_actor(
            self.request.user,
            payments.confirm_payment_sync,
            parsed_path.id,
            parsed_body.reference,
        )


class PaymentRefundController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ReferencePost],
        parsed_path: Path[UuidInstancePath],
    ) -> PaymentGet:
        return await as_actor(
            self.request.user,
            payments.refund_payment_sync,
            parsed_path.id,
            parsed_body.reference,
        )


########################################################################################
# El guía: su saldo, su cuenta y sus retiros


class MineBalanceController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> GuideBalanceGet:
        return await sync_to_async(balance.balance_sync)(self.request.user)


class MineBankAccountController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> BankAccountsGet:
        return await sync_to_async(balance.accounts_sync)(self.request.user)

    # una cuenta nueva surte efecto en 24 horas (la primera, de una vez)
    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[BankAccountPost]) -> BankAccountsGet:
        return await sync_to_async(balance.add_account_sync)(
            self.request.user, parsed_body
        )


class MineWithdrawalController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[WithdrawalGet]:
        return await sync_to_async(balance.withdrawals_sync)(self.request.user)


class WithdrawalController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[WithdrawalPost]) -> WithdrawalGet:
        return await sync_to_async(balance.request_withdrawal_sync)(
            self.request.user, parsed_body.amount
        )


########################################################################################
# Retiros (el equipo)


def pay_withdrawal(
    actor: Actor, withdrawal_id: UUID, data: ResolveWithdrawalPost
) -> WithdrawalAdminGet:
    return balance.resolve_withdrawal_sync(
        actor, withdrawal_id, note=data.note, paid=True, reference=data.reference
    )


def reject_withdrawal(
    actor: Actor,
    withdrawal_id: UUID,
    data: ResolveWithdrawalPost,
) -> WithdrawalAdminGet:
    return balance.resolve_withdrawal_sync(
        actor, withdrawal_id, note=data.note, paid=False, reference=data.reference
    )


class GuideWithdrawalController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[WithdrawalQuery],
    ) -> Paginated[WithdrawalAdminGet]:
        return await as_actor(
            self.request.user, balance.admin_withdrawals_sync, parsed_query
        )


class GuideWithdrawalPayController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ResolveWithdrawalPost],
        parsed_path: Path[UuidInstancePath],
    ) -> WithdrawalAdminGet:
        return await as_actor(
            self.request.user, pay_withdrawal, parsed_path.id, parsed_body
        )


class GuideWithdrawalRejectController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ResolveWithdrawalPost],
        parsed_path: Path[UuidInstancePath],
    ) -> WithdrawalAdminGet:
        return await as_actor(
            self.request.user, reject_withdrawal, parsed_path.id, parsed_body
        )


########################################################################################
# Estados de cuenta de los comercios


class StatementController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[StatementQuery],
    ) -> Paginated[StatementGet]:
        return await as_actor(
            self.request.user, statements.statements_sync, parsed_query
        )


class StatementPayController(BaseController[CustomPydanticFastSerializer]):
    # el equipo cobró fuera de línea y lo marca pagado
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[ReferencePost],
        parsed_path: Path[UuidInstancePath],
    ) -> StatementGet:
        return await as_actor(
            self.request.user,
            statements.pay_statement_sync,
            parsed_path.id,
            parsed_body.reference,
        )
