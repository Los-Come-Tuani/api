from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_finance.controllers import (
    GuideWithdrawalController,
    GuideWithdrawalPayController,
    GuideWithdrawalRejectController,
    MineBalanceController,
    MineBankAccountController,
    MineWithdrawalController,
    PaymentConfirmController,
    PaymentController,
    PaymentRefundController,
    PricingController,
    StatementController,
    StatementPayController,
    WithdrawalController,
)

if TYPE_CHECKING:
    from typing import Final

    from api_core.controllers.base import BaseController
    from api_core.controllers.routers import URL

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")


def action(ctrl: type[BaseController], endpoint: str, tail: str) -> URL:
    return route_controller(
        ctrl=ctrl,
        endpoint=endpoint,
        instance_param=INSTANCE,
        suffix=tail,
        tail=tail,
    )


router: Final[Router] = Router(
    prefix="",
    tags=["finance"],
    urls=(
        route_controller(ctrl=PricingController, endpoint="pricing"),
        route_controller(ctrl=PaymentController, endpoint="payment"),
        action(PaymentConfirmController, "payment", "confirm"),
        action(PaymentRefundController, "payment", "refund"),
        route_controller(ctrl=MineBalanceController, endpoint="balance/mine"),
        route_controller(ctrl=MineBankAccountController, endpoint="bank-account/mine"),
        route_controller(ctrl=MineWithdrawalController, endpoint="withdrawal/mine"),
        route_controller(ctrl=WithdrawalController, endpoint="withdrawal"),
        route_controller(ctrl=GuideWithdrawalController, endpoint="guide-withdrawal"),
        action(GuideWithdrawalPayController, "guide-withdrawal", "pay"),
        action(GuideWithdrawalRejectController, "guide-withdrawal", "reject"),
        route_controller(ctrl=StatementController, endpoint="billing/statement"),
        action(StatementPayController, "billing/statement", "pay"),
    ),
)
