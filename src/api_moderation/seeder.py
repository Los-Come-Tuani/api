from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_moderation.enums import VerificationStates
from api_moderation.models import VerificationStatus

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - (código, etiqueta, en bandeja, es terminal): `estado_verificacion` del modelo de
#   dominio. Las dos primeras son la bandeja del moderador; las otras cierran el
#   expediente.
STATES: Final[tuple[tuple[VerificationStates, str, bool, bool], ...]] = (
    (VerificationStates.SUBMITTED, "Enviada", True, False),
    (VerificationStates.IN_REVIEW, "En revisión", True, False),
    (VerificationStates.APPROVED, "Aprobada", False, True),
    (VerificationStates.REJECTED, "Rechazada", False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, in_queue, is_terminal in STATES:
        VerificationStatus.objects.get_or_create(
            code=code,
            defaults={
                "in_queue": in_queue,
                "is_terminal": is_terminal,
                "label": label,
            },
        )
