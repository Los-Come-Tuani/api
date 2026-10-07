from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_itineraries.models import ItineraryStatus

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - (código, etiqueta, admite edición, admite reserva, terminal): `estado_itinerario`
ITINERARY_STATES: Final[tuple[tuple[str, str, bool, bool, bool], ...]] = (
    ("planificado", "Planificado", True, True, False),
    ("en_curso", "En curso", True, False, False),
    ("completado", "Completado", False, False, False),
    ("eliminado", "Eliminado", False, False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, allows_editing, allows_booking, is_terminal in ITINERARY_STATES:
        ItineraryStatus.objects.update_or_create(
            code=code,
            defaults={
                "allows_booking": allows_booking,
                "allows_editing": allows_editing,
                "is_terminal": is_terminal,
                "label": label,
            },
        )
