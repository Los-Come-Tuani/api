from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, NonNegativeInt, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_territory.schemas.common import (
    CityRef,
    ImageGet,
    ImageKey,
    Latitude,
    Longitude,
    PillarRef,
    Reference,
)

########################################################################################

type CampaignStatusName = Literal["active", "sold_out", "withdrawn", "expired"]
type CouponStatusName = Literal["valid", "consumed", "expired"]
type Moment = Annotated[datetime, Field(strict=False)]

########################################################################################
# Insignias y visitas


class QrGet(DTO):
    point_id: UUID
    # lo que va impreso en el QR del local; la app manda esto o solo el código
    payload: str
    token: str
    # cuántas insignias da la visita
    value: int
    active: bool


class VisitPost(DTO):
    # lo que leyó la cámara: `kplan://visit/<código>` o solo el código
    qr: Annotated[str, StringConstraints(max_length=200, min_length=8)]
    latitude: Latitude
    longitude: Longitude


class VisitPointRef(DTO):
    id: UUID
    name: str
    pillar: PillarRef


class VisitGet(DTO):
    id: UUID
    point: VisitPointRef
    # las insignias que dio y el saldo que quedó
    amount: int
    balance: int
    distance_meters: NonNegativeInt
    accredited_at: datetime


class PillarCountGet(DTO):
    code: str
    label: str
    count: NonNegativeInt


class MovementGet(DTO):
    amount: int
    kind: Literal["visit", "coupon"]
    # el lugar visitado o el cupón canjeado
    label: str
    recorded_at: datetime


class BalanceGet(DTO):
    balance: int
    earned: NonNegativeInt
    spent: NonNegativeInt
    # las insignias ganadas por pilar
    by_pillar: list[PillarCountGet]
    # los lugares que ya acreditó alguna vez
    visited_point_ids: list[UUID]
    # los últimos movimientos, del más reciente
    recent: list[MovementGet]


########################################################################################
# Campañas y cupones


class BenefitGet(DTO):
    type: PillarRef
    # el porcentaje o los córdobas; nulo si el tipo no lleva monto
    amount: float | None
    currency: str | None
    # listo para mostrar: "10% de descuento", "Producto gratis"
    label: str


class BusinessRef(DTO):
    id: UUID
    name: str
    city: CityRef
    # su lugar en el mapa, si ya lo tiene
    place_id: UUID | None


class RewardGet(DTO):
    id: UUID
    title: str
    description: str
    terms: str
    benefit: BenefitGet
    cost_badges: int
    # cuántos cupones quedan
    remaining: NonNegativeInt
    expires_at: datetime
    image: ImageGet | None
    business: BusinessRef


class CampaignGet(RewardGet):
    status: CampaignStatusName
    stock_total: int
    stock_delivered: int
    # cuántos se usaron en el mostrador
    consumed: NonNegativeInt
    withdrawn_at: datetime | None
    withdrawn_reason: str
    created_at: datetime


class RewardQuery(PageQuery):
    # el código de la ciudad del comercio
    city: Annotated[str, StringConstraints(max_length=40)] | None = None


class CampaignQuery(PageQuery):
    status: CampaignStatusName | None = None
    business_id: Reference | None = None


type Title = Annotated[str, StringConstraints(max_length=80, min_length=3)]
type LongText = Annotated[str, StringConstraints(max_length=1000)]


class CampaignPost(DTO):
    benefit_type: Annotated[str, StringConstraints(max_length=40, min_length=1)]
    title: Title
    description: LongText = ""
    terms: LongText = ""
    # el porcentaje o los córdobas, si el tipo lo exige
    benefit_amount: Annotated[float, Field(gt=0, le=1_000_000, strict=False)] | None = (
        None
    )
    cost_badges: Annotated[int, Field(ge=1, le=1000)]
    stock_total: Annotated[int, Field(ge=1, le=100_000)]
    expires_at: Moment
    image_key: ImageKey | None = None


# Solo se aplican los campos que llegan; el beneficio y el costo no cambian.
class CampaignPatch(DTO):
    title: Title = ""
    description: LongText = ""
    terms: LongText = ""
    stock_total: Annotated[int, Field(ge=1, le=100_000)] = 1
    expires_at: Moment | None = None
    image_key: ImageKey | None = None


class WithdrawPost(DTO):
    reason: Annotated[str, StringConstraints(max_length=500)] = ""


class CouponGet(DTO):
    id: UUID
    # se dicta o se muestra en el mostrador
    code: str
    title: str
    benefit: BenefitGet
    cost_badges: int
    status: CouponStatusName
    expires_at: datetime
    redeemed_at: datetime
    consumed_at: datetime | None
    business: BusinessRef


class CouponPost(DTO):
    campaign_id: Reference


class RedemptionGet(DTO):
    id: UUID
    code: str
    title: str
    campaign_id: UUID
    tourist_name: str
    status: CouponStatusName
    redeemed_at: datetime
    consumed_at: datetime | None
    expires_at: datetime


class RedemptionQuery(PageQuery):
    status: CouponStatusName | None = None
    campaign_id: Reference | None = None


class ValidatePost(DTO):
    # como lo dicta el turista: sin importar mayúsculas, espacios ni guiones
    code: Annotated[str, StringConstraints(max_length=20, min_length=8)]
