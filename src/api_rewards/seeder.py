from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_rewards.models import CampaignStatus, CouponStatus

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - (código, etiqueta, admite canje, terminal): `estado_campania`
CAMPAIGN_STATES: Final[tuple[tuple[str, str, bool, bool], ...]] = (
    ("activa", "Activa", True, False),
    ("agotada", "Agotada", False, True),
    ("retirada", "Retirada", False, True),
    ("expirada", "Expirada", False, True),
)

# - (código, etiqueta, admite validación, terminal): `estado_cupon`
COUPON_STATES: Final[tuple[tuple[str, str, bool, bool], ...]] = (
    ("vigente", "Vigente", True, False),
    ("consumido", "Consumido", False, True),
    ("expirado", "Expirado", False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, redeemable, terminal in CAMPAIGN_STATES:
        CampaignStatus.objects.update_or_create(
            code=code,
            defaults={
                "allows_redemption": redeemable,
                "is_terminal": terminal,
                "label": label,
            },
        )

    for code, label, validable, terminal in COUPON_STATES:
        CouponStatus.objects.update_or_create(
            code=code,
            defaults={
                "allows_validation": validable,
                "is_terminal": terminal,
                "label": label,
            },
        )
