from typing import TYPE_CHECKING

from dmr.routing import Router

from api_core.controllers.routers import route_controller
from api_rewards.controllers import (
    CouponCampaignController,
    CouponCampaignDetailController,
    CouponCampaignWithdrawController,
    CouponController,
    CouponRedemptionController,
    CouponRedemptionValidateController,
    MineBadgeController,
    MineCouponController,
    PlaceQrController,
    RewardController,
    RewardDetailController,
    VisitController,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

INSTANCE: Final[tuple[str, str]] = ("uuid", "id")

router: Final[Router] = Router(
    prefix="",
    tags=["rewards"],
    urls=(
        # la app
        route_controller(ctrl=RewardController, endpoint="reward"),
        route_controller(
            ctrl=RewardDetailController,
            endpoint="reward",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(ctrl=VisitController, endpoint="visit"),
        route_controller(ctrl=MineBadgeController, endpoint="badge/mine"),
        route_controller(ctrl=CouponController, endpoint="coupon"),
        route_controller(ctrl=MineCouponController, endpoint="coupon/mine"),
        # el portal
        route_controller(
            ctrl=PlaceQrController,
            endpoint="place",
            instance_param=INSTANCE,
            suffix="qr",
            tail="qr",
        ),
        route_controller(ctrl=CouponCampaignController, endpoint="coupon-campaign"),
        route_controller(
            ctrl=CouponCampaignDetailController,
            endpoint="coupon-campaign",
            instance_param=INSTANCE,
            suffix="detail",
        ),
        route_controller(
            ctrl=CouponCampaignWithdrawController,
            endpoint="coupon-campaign",
            instance_param=INSTANCE,
            suffix="withdraw",
            tail="withdraw",
        ),
        route_controller(
            ctrl=CouponRedemptionController,
            endpoint="coupon-redemption",
        ),
        route_controller(
            ctrl=CouponRedemptionValidateController,
            endpoint="coupon-redemption/validate",
        ),
    ),
)
