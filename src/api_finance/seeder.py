from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_finance.models import Tariff

if TYPE_CHECKING:
    from typing import Final

########################################################################################

COMMISSION_RATE: Final[str] = "comision_reserva"
BADGE_MONTHLY: Final[str] = "insignia_mensual"
COUPON_FEE: Final[str] = "cupon_validado"

# - (código, etiqueta, valor inicial, unidad). La comisión la decidió el equipo (15%);
#   las otras dos son valores de ejemplo que el equipo cambia desde el portal
TARIFFS: Final[tuple[tuple[str, str, str, str], ...]] = (
    (COMMISSION_RATE, "Comisión de K'Plan por reserva", "15", "percent"),
    (BADGE_MONTHLY, "Insignia de un lugar, por mes", "300", "nio"),
    (COUPON_FEE, "Cupón validado en el mostrador", "10", "nio"),
)

########################################################################################


@atomic
def execute() -> None:
    # `get_or_create`: lo que el equipo cambia no se pisa al migrar
    for code, label, value, unit in TARIFFS:
        Tariff.objects.get_or_create(
            code=code,
            defaults={"label": label, "unit": unit, "value": Decimal(value)},
        )
