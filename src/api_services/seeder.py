from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_services.models import BookingStatus, RequestStatus

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - (código, etiqueta, admite postulaciones, terminal): `estado_convocatoria`
REQUEST_STATES: Final[tuple[tuple[str, str, bool, bool], ...]] = (
    ("abierta", "Abierta", True, False),
    ("adjudicada", "Adjudicada", False, True),
    ("cancelada", "Cancelada", False, True),
    ("expirada", "Expirada", False, True),
)

# - (código, etiqueta, admite cancelación, terminal): `estado_reserva`. Sin cobro en
#   línea hasta F8: `pendiente_pago` y `expirada` llegan con la pasarela
BOOKING_STATES: Final[tuple[tuple[str, str, bool, bool], ...]] = (
    ("confirmada", "Confirmada", True, False),
    ("en_curso", "En curso", False, False),
    ("prestada", "Prestada", False, False),
    ("cerrada", "Cerrada", False, True),
    ("cancelada", "Cancelada", False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, open_, terminal in REQUEST_STATES:
        RequestStatus.objects.update_or_create(
            code=code,
            defaults={
                "accepts_applications": open_,
                "is_terminal": terminal,
                "label": label,
            },
        )

    for code, label, cancellable, terminal in BOOKING_STATES:
        BookingStatus.objects.update_or_create(
            code=code,
            defaults={
                "allows_cancellation": cancellable,
                "is_terminal": terminal,
                "label": label,
            },
        )
