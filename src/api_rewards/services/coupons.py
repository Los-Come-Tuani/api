from decimal import Decimal
from secrets import choice
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Count, F, Q
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_catalogs.models import BenefitType, Currency
from api_core.services.pages import paginate
from api_core.services.uploads import UploadKinds
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_organizations.models import Business
from api_rewards.models import (
    COUPON_ALPHABET,
    BadgeMovement,
    CampaignStatus,
    Coupon,
    CouponCampaign,
    CouponStatus,
)
from api_rewards.schemas import (
    BenefitGet,
    BusinessRef,
    CampaignGet,
    CouponGet,
    RedemptionGet,
    RewardGet,
)
from api_rewards.services.badges import balance_of, ensure_tourist, lock_user
from api_territory.models import PointOfInterest
from api_territory.schemas.common import PillarRef
from api_territory.services.access import Actor, invalid
from api_territory.services.images import check_images, image_payload
from api_territory.services.places import city_ref

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_core.schemas.pagination import Paginated
    from api_rewards.schemas import (
        CampaignPatch,
        CampaignPost,
        CampaignQuery,
        RedemptionQuery,
        RewardQuery,
    )

########################################################################################

ACTIVE: Final[str] = "activa"
SOLD_OUT: Final[str] = "agotada"
WITHDRAWN: Final[str] = "retirada"
EXPIRED: Final[str] = "expirada"

CAMPAIGN_API: Final[dict[str, str]] = {
    ACTIVE: "active",
    EXPIRED: "expired",
    SOLD_OUT: "sold_out",
    WITHDRAWN: "withdrawn",
}
CAMPAIGN_BY_API: Final[dict[str, str]] = {
    name: code for code, name in CAMPAIGN_API.items()
}

VALID: Final[str] = "vigente"
CONSUMED: Final[str] = "consumido"
COUPON_EXPIRED: Final[str] = "expirado"

COUPON_API: Final[dict[str, str]] = {
    CONSUMED: "consumed",
    COUPON_EXPIRED: "expired",
    VALID: "valid",
}
COUPON_BY_API: Final[dict[str, str]] = {name: code for code, name in COUPON_API.items()}

# - cuántas campañas activas puede tener un comercio a la vez
MAX_ACTIVE_CAMPAIGNS: Final[int] = 3
CODE_LENGTH: Final[int] = 8
CODE_ATTEMPTS: Final[int] = 5

NOT_FOUND_CAMPAIGN: Final[str] = "No encontramos esa campaña."
NOT_FOUND_COUPON: Final[str] = "No encontramos ese cupón."

########################################################################################
# Vencimiento


def campaign_status(code: str) -> CampaignStatus:
    return CampaignStatus.objects.get(code=code)


def coupon_status(code: str) -> CouponStatus:
    return CouponStatus.objects.get(code=code)


# Lo que pasó su fecha límite: la campaña activa vence y el cupón sin usar también.
# Corre antes de cada lectura y con `syncevents` cada día.
def expire_sync() -> None:
    moment = now()

    CouponCampaign.objects.filter(status__code=ACTIVE, expires_at__lte=moment).update(
        status=campaign_status(EXPIRED)
    )
    Coupon.objects.filter(status__code=VALID, expires_at__lte=moment).update(
        status=coupon_status(COUPON_EXPIRED)
    )


########################################################################################
# Piezas


def benefit_label(benefit_type: BenefitType, amount: Decimal | None) -> str:
    found: Any = benefit_type

    if amount is None:
        return str(found.label)

    shown: str = f"{amount.normalize():f}"

    if found.is_percentage:
        return f"{shown}% de descuento"

    return f"C$ {shown} de descuento"


def benefit_payload(record: CouponCampaign | Coupon) -> BenefitGet:
    found: Any = record
    amount: Decimal | None = found.benefit_amount

    return BenefitGet(
        amount=None if amount is None else float(amount),
        currency=None if found.currency is None else str(found.currency.code),
        label=benefit_label(found.benefit_type, amount),
        type=PillarRef(
            code=str(found.benefit_type.code), label=str(found.benefit_type.label)
        ),
    )


def business_ref(business: Business) -> BusinessRef:
    found: Any = business
    place: PointOfInterest | None = PointOfInterest.objects.filter(
        business=business
    ).first()

    return BusinessRef(
        city=city_ref(found.city),
        id=found.pk,
        name=str(found.name),
        place_id=None if place is None else place.pk,
    )


def campaigns() -> QuerySet:
    return CouponCampaign.objects.select_related(
        "benefit_type",
        "business__city",
        "currency",
        "status",
    ).annotate(consumed=Count("coupons", filter=Q(coupons__consumed_at__isnull=False)))


def reward_payload(campaign: CouponCampaign) -> RewardGet:
    found: Any = campaign

    return RewardGet(
        benefit=benefit_payload(campaign),
        business=business_ref(found.business),
        cost_badges=int(found.cost_badges),
        description=str(found.description),
        expires_at=found.expires_at,
        id=found.pk,
        image=image_payload(str(found.image_key)) if found.image_key else None,
        remaining=max(0, int(found.stock_total) - int(found.stock_delivered)),
        terms=str(found.terms),
        title=str(found.title),
    )


def campaign_payload(campaign: CouponCampaign) -> CampaignGet:
    found: Any = campaign

    return CampaignGet(
        **dict(reward_payload(campaign)),
        consumed=int(getattr(found, "consumed", 0) or 0),
        created_at=found.created_at,
        status=CAMPAIGN_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        stock_delivered=int(found.stock_delivered),
        stock_total=int(found.stock_total),
        withdrawn_at=found.withdrawn_at,
        withdrawn_reason=str(found.withdrawn_reason),
    )


def coupon_payload(coupon: Coupon) -> CouponGet:
    found: Any = coupon

    return CouponGet(
        benefit=benefit_payload(coupon),
        business=business_ref(found.business),
        code=str(found.code),
        consumed_at=found.consumed_at,
        cost_badges=int(found.cost_badges),
        expires_at=found.expires_at,
        id=found.pk,
        redeemed_at=found.redeemed_at,
        status=COUPON_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        title=str(found.title),
    )


def redemption_payload(coupon: Coupon) -> RedemptionGet:
    found: Any = coupon

    return RedemptionGet(
        campaign_id=found.campaign_id,
        code=str(found.code),
        consumed_at=found.consumed_at,
        expires_at=found.expires_at,
        id=found.pk,
        redeemed_at=found.redeemed_at,
        status=COUPON_API[str(found.status.code)],  # ty: ignore[invalid-argument-type]
        title=str(found.title),
        tourist_name=found.user.display_name,
    )


########################################################################################
# La tienda de la app (pública)


def available() -> QuerySet:
    return campaigns().filter(
        expires_at__gt=now(),
        status__code=ACTIVE,
        stock_delivered__lt=F("stock_total"),
    )


def rewards_sync(query: RewardQuery) -> Paginated[RewardGet]:
    expire_sync()

    found = available()

    if query.city:
        found = found.filter(business__city__code=query.city)

    return paginate(
        found.order_by("expires_at", "id"), query, reward_payload, RewardGet
    )


def reward_sync(campaign_id: UUID) -> RewardGet:
    expire_sync()

    campaign: CouponCampaign | None = available().filter(pk=campaign_id).first()

    if campaign is None:
        raise NotFoundError(detail=NOT_FOUND_CAMPAIGN)

    return reward_payload(campaign)


########################################################################################
# Las campañas del comercio (portal)


def own_business(actor: Actor) -> Business | None:
    if actor.organization is None or not actor.operates("business"):
        return None

    return Business.objects.filter(pk=actor.organization.id).first()


# El comercio ve las suyas; el equipo con `content.moderate`, todas.
def visible_campaigns(actor: Actor) -> QuerySet:
    found = campaigns()

    if actor.can(P.CONTENT_MODERATE):
        return found

    business: Business | None = own_business(actor)

    if business is not None:
        return found.filter(business=business)

    raise ForbiddenError


def visible_campaign(actor: Actor, campaign_id: UUID) -> CouponCampaign:
    campaign: CouponCampaign | None = (
        visible_campaigns(actor).filter(pk=campaign_id).first()
    )

    if campaign is None:
        raise NotFoundError(detail=NOT_FOUND_CAMPAIGN)

    return campaign


def campaigns_sync(actor: Actor, query: CampaignQuery) -> Paginated[CampaignGet]:
    expire_sync()

    found = visible_campaigns(actor)

    if query.status is not None:
        found = found.filter(status__code=CAMPAIGN_BY_API[query.status])

    if query.business_id is not None:
        found = found.filter(business_id=query.business_id)

    return paginate(
        found.order_by("-created_at", "id"),
        query,
        campaign_payload,
        CampaignGet,
    )


def campaign_sync(actor: Actor, campaign_id: UUID) -> CampaignGet:
    expire_sync()

    return campaign_payload(visible_campaign(actor, campaign_id))


def benefit_fields(data: CampaignPost) -> dict[str, Any]:
    benefit_type: BenefitType | None = BenefitType.objects.filter(
        active=True, code=data.benefit_type
    ).first()

    if benefit_type is None:
        raise invalid("benefit_type", "Ese beneficio no existe.")

    found: Any = benefit_type

    if not found.requires_amount:
        return {"benefit_amount": None, "benefit_type": benefit_type, "currency": None}

    if data.benefit_amount is None:
        raise invalid("benefit_amount", "Di cuánto es el descuento.")

    amount = Decimal(str(round(data.benefit_amount, 2)))

    if found.is_percentage and amount > 100:  # ruff: ignore[magic-value-comparison]
        raise invalid("benefit_amount", "Un porcentaje no pasa de 100.")

    return {
        "benefit_amount": amount,
        "benefit_type": benefit_type,
        "currency": None if found.is_percentage else Currency.objects.get(code="NIO"),
    }


def check_image(key: str | None, current: str) -> str:
    if not key:
        return ""

    check_images(
        [key],
        current=[current] if current else [],
        field="image_key",
        kind=UploadKinds.COUPON_PHOTO,
    )

    return key


def create_campaign_sync(actor: Actor, data: CampaignPost) -> CampaignGet:
    business: Business | None = own_business(actor)

    if business is None:
        raise ForbiddenError(detail="Solo un comercio verificado publica cupones.")

    if data.expires_at <= now():
        raise invalid("expires_at", "La fecha límite tiene que ser futura.")

    benefit: dict[str, Any] = benefit_fields(data)
    image_key: str = check_image(data.image_key, "")

    with atomic():
        # se cuenta con el comercio bloqueado: dos altas a la vez no pasan del límite
        Business.objects.select_for_update().filter(pk=business.pk).first()
        expire_sync()

        active: int = CouponCampaign.objects.filter(
            business=business, status__code=ACTIVE
        ).count()

        if active >= MAX_ACTIVE_CAMPAIGNS:
            raise ConflictError(
                detail=(
                    f"Ya tienes {MAX_ACTIVE_CAMPAIGNS} campañas activas: retira una "
                    "o espera a que termine."
                )
            )

        campaign: CouponCampaign = CouponCampaign.objects.create(
            **benefit,
            business=business,
            cost_badges=data.cost_badges,
            description=data.description,
            expires_at=data.expires_at,
            image_key=image_key,
            status=campaign_status(ACTIVE),
            stock_total=data.stock_total,
            terms=data.terms,
            title=data.title,
        )

    return campaign_sync(actor, campaign.pk)


def update_campaign_sync(
    actor: Actor,
    campaign_id: UUID,
    patch: CampaignPatch,
) -> CampaignGet:
    campaign: Any = visible_campaign(actor, campaign_id)

    if own_business(actor) is None:
        raise ForbiddenError

    if campaign.status.code != ACTIVE:
        raise ConflictError(detail="Solo se edita una campaña activa.")

    changes: dict[str, Any] = patch.model_dump(exclude_unset=True)

    if "stock_total" in changes and changes["stock_total"] < campaign.stock_delivered:
        raise invalid(
            "stock_total",
            f"Ya se entregaron {campaign.stock_delivered} cupones.",
        )

    if "expires_at" in changes and (
        changes["expires_at"] is None or changes["expires_at"] <= now()
    ):
        raise invalid("expires_at", "La fecha límite tiene que ser futura.")

    if "image_key" in changes:
        changes["image_key"] = check_image(
            changes["image_key"], str(campaign.image_key)
        )

    if changes:
        CouponCampaign.objects.filter(pk=campaign.pk).update(**changes)

    return campaign_sync(actor, campaign.pk)


# Retirarla corta la emisión; los cupones entregados siguen valiendo (D-25). La retira
# el comercio o, al moderar, el equipo con `content.moderate`.
def withdraw_campaign_sync(actor: Actor, campaign_id: UUID, reason: str) -> CampaignGet:
    campaign: Any = visible_campaign(actor, campaign_id)

    if campaign.status.is_terminal:
        raise ConflictError(detail="Esa campaña ya no está activa.")

    CouponCampaign.objects.filter(pk=campaign.pk).update(
        status=campaign_status(WITHDRAWN),
        withdrawn_at=now(),
        withdrawn_reason=reason.strip(),
    )

    return campaign_sync(actor, campaign.pk)


########################################################################################
# Canje y billetera del turista


def new_code() -> str:
    return "".join(choice(COUPON_ALPHABET) for _ in range(CODE_LENGTH))


# Canjear y cobrar van juntos (RF-T-21): el cupón, el cargo al saldo y el cupo entregado
# se escriben en la misma transacción, con el turista y la campaña bloqueados.
def redeem_sync(user: ApiUser, campaign_id: UUID) -> CouponGet:
    ensure_tourist(user)
    expire_sync()

    with atomic():
        lock_user(user)

        campaign: Any = (
            CouponCampaign.objects
            .select_for_update(of=("self",))
            .select_related("status")
            .filter(pk=campaign_id)
            .first()
        )

        if (
            campaign is None
            or campaign.status.code != ACTIVE
            or campaign.expires_at <= now()
            or campaign.stock_delivered >= campaign.stock_total
        ):
            raise NotFoundError(detail="Esa recompensa ya no está disponible.")

        if balance_of(user) < campaign.cost_badges:
            raise ConflictError(detail="No te alcanzan las insignias para este cupón.")

        coupon: Coupon | None = None

        for _ in range(CODE_ATTEMPTS):
            code: str = new_code()

            if not Coupon.objects.filter(code=code).exists():
                try:
                    coupon = Coupon.objects.create(
                        benefit_amount=campaign.benefit_amount,
                        benefit_type_id=campaign.benefit_type_id,
                        business_id=campaign.business_id,
                        campaign=campaign,
                        code=code,
                        cost_badges=campaign.cost_badges,
                        currency_id=campaign.currency_id,
                        expires_at=campaign.expires_at,
                        status=coupon_status(VALID),
                        title=campaign.title,
                        user=user,
                    )
                    break
                except IntegrityError:
                    continue

        if coupon is None:
            raise ConflictError(
                detail="No pudimos generar el código. Intenta de nuevo."
            )

        BadgeMovement.objects.create(
            amount=-int(campaign.cost_badges),
            coupon=coupon,
            user=user,
        )

        delivered: int = int(campaign.stock_delivered) + 1

        CouponCampaign.objects.filter(pk=campaign.pk).update(
            status=campaign_status(
                SOLD_OUT if delivered >= campaign.stock_total else ACTIVE
            ),
            stock_delivered=F("stock_delivered") + 1,
        )

    return coupon_payload(own_coupons(user).get(pk=coupon.pk))


def own_coupons(user: ApiUser) -> QuerySet:
    return Coupon.objects.select_related(
        "benefit_type",
        "business__city",
        "currency",
        "status",
    ).filter(user=user)


def wallet_sync(user: ApiUser) -> list[CouponGet]:
    expire_sync()

    return [
        coupon_payload(item)
        for item in own_coupons(user).order_by("-redeemed_at", "id")
    ]


########################################################################################
# Lo canjeado en el comercio (portal)


def visible_redemptions(actor: Actor) -> QuerySet:
    found = Coupon.objects.select_related("status", "user")

    if actor.can(P.CONTENT_MODERATE):
        return found

    business: Business | None = own_business(actor)

    if business is not None:
        return found.filter(business=business)

    raise ForbiddenError


def redemptions_sync(actor: Actor, query: RedemptionQuery) -> Paginated[RedemptionGet]:
    expire_sync()

    found = visible_redemptions(actor)

    if query.status is not None:
        found = found.filter(status__code=COUPON_BY_API[query.status])

    if query.campaign_id is not None:
        found = found.filter(campaign_id=query.campaign_id)

    if query.code:
        found = found.filter(code=normalized_code(query.code))

    return paginate(
        found.order_by("-redeemed_at", "id"),
        query,
        redemption_payload,
        RedemptionGet,
    )


def normalized_code(raw: str) -> str:
    return "".join(char for char in raw.upper() if char.isalnum())


# El comercio valida el cupón en el mostrador (RF-C-10): solo los suyos, una sola vez y
# antes de su fecha límite. Un código de otro comercio no existe para él.
def validate_coupon_sync(actor: Actor, raw_code: str) -> RedemptionGet:
    business: Business | None = own_business(actor)

    if business is None:
        raise ForbiddenError(detail="Solo el comercio valida sus cupones.")

    expire_sync()

    with atomic():
        coupon: Any = (
            Coupon.objects
            .select_for_update(of=("self",))
            .select_related("status")
            .filter(business=business, code=normalized_code(raw_code))
            .first()
        )

        if coupon is None:
            raise NotFoundError(detail=NOT_FOUND_COUPON)

        if coupon.status.code == CONSUMED:
            raise ConflictError(detail="Ese cupón ya se usó.")

        if coupon.status.code == COUPON_EXPIRED:
            raise ConflictError(detail="Ese cupón venció.")

        Coupon.objects.filter(pk=coupon.pk).update(
            consumed_at=now(),
            consumed_by=actor.user,
            status=coupon_status(CONSUMED),
        )

    return redemption_payload(
        Coupon.objects.select_related("status", "user").get(pk=coupon.pk)
    )
