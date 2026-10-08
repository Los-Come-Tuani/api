from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.mixins import PublicEndpointMixin
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath
from api_rewards.schemas import (
    BalanceGet,
    CampaignGet,
    CampaignPatch,
    CampaignPost,
    CampaignQuery,
    CouponGet,
    CouponPost,
    QrGet,
    RedemptionGet,
    RedemptionQuery,
    RewardGet,
    RewardQuery,
    ValidatePost,
    VisitGet,
    VisitPost,
    WithdrawPost,
)
from api_rewards.services import badges, coupons
from api_territory.controllers import as_actor
from api_territory.services.places import visible_place

if TYPE_CHECKING:
    from uuid import UUID

    from api_territory.services.access import Actor

########################################################################################
# La tienda de recompensas de la app: pública


class RewardController(
    PublicEndpointMixin, BaseController[CustomPydanticFastSerializer]
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_query: StrictQuery[RewardQuery]) -> Paginated[RewardGet]:  # ruff: ignore[no-self-use]
        return await sync_to_async(coupons.rewards_sync)(parsed_query)


class RewardDetailController(
    PublicEndpointMixin,
    BaseController[CustomPydanticFastSerializer],
):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> RewardGet:  # ruff: ignore[no-self-use]
        return await sync_to_async(coupons.reward_sync)(parsed_path.id)


########################################################################################
# El turista: visitas, saldo, canje y billetera


class VisitController(BaseController[CustomPydanticFastSerializer]):
    # escaneó el QR del lugar estando cerca: gana su insignia
    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[VisitPost]) -> VisitGet:
        return await sync_to_async(badges.accredit_visit_sync)(
            self.request.user,
            parsed_body,
        )


class MineBadgeController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> BalanceGet:
        return await sync_to_async(badges.balance_sync)(self.request.user)


class CouponController(BaseController[CustomPydanticFastSerializer]):
    # canjea insignias por un cupón de una campaña
    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[CouponPost]) -> CouponGet:
        return await sync_to_async(coupons.redeem_sync)(
            self.request.user,
            parsed_body.campaign_id,
        )


class MineCouponController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[CouponGet]:
        return await sync_to_async(coupons.wallet_sync)(self.request.user)


########################################################################################
# El portal: el QR de un lugar, las campañas del comercio y la validación


def place_qr_sync(actor: Actor, point_id: UUID) -> QrGet:
    return badges.qr_payload(visible_place(actor, point_id))


class PlaceQrController(BaseController[CustomPydanticFastSerializer]):
    # lo que se imprime en el local: quien ve el lugar lo descarga
    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> QrGet:
        return await as_actor(self.request.user, place_qr_sync, parsed_path.id)


class CouponCampaignController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[CampaignQuery],
    ) -> Paginated[CampaignGet]:
        return await as_actor(self.request.user, coupons.campaigns_sync, parsed_query)

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[CampaignPost]) -> CampaignGet:
        return await as_actor(
            self.request.user,
            coupons.create_campaign_sync,
            parsed_body,
        )


class CouponCampaignDetailController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> CampaignGet:
        return await as_actor(self.request.user, coupons.campaign_sync, parsed_path.id)

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[CampaignPatch],
        parsed_path: Path[UuidInstancePath],
    ) -> CampaignGet:
        return await as_actor(
            self.request.user,
            coupons.update_campaign_sync,
            parsed_path.id,
            parsed_body,
        )


class CouponCampaignWithdrawController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(
        self,
        parsed_body: Body[WithdrawPost],
        parsed_path: Path[UuidInstancePath],
    ) -> CampaignGet:
        return await as_actor(
            self.request.user,
            coupons.withdraw_campaign_sync,
            parsed_path.id,
            parsed_body.reason,
        )


class CouponRedemptionController(BaseController[CustomPydanticFastSerializer]):
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self,
        parsed_query: StrictQuery[RedemptionQuery],
    ) -> Paginated[RedemptionGet]:
        return await as_actor(
            self.request.user,
            coupons.redemptions_sync,
            parsed_query,
        )


class CouponRedemptionValidateController(
    BaseController[CustomPydanticFastSerializer],
):
    # el turista muestra o dicta su código en el mostrador
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_body: Body[ValidatePost]) -> RedemptionGet:
        return await as_actor(
            self.request.user,
            coupons.validate_coupon_sync,
            parsed_body.code,
        )
