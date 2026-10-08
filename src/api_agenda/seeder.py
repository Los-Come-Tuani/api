from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_agenda.models import EventStatus

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - (código, etiqueta, visible, admite edición, genera avisos, terminal)
EVENT_STATES: Final[tuple[tuple[str, str, bool, bool, bool, bool], ...]] = (
    ("programado", "Programado", True, True, False, False),
    ("publicado", "En curso", True, True, True, False),
    ("finalizado", "Finalizado", False, False, False, True),
    ("cancelado", "Cancelado", True, False, False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, visible, editing, alerts, terminal in EVENT_STATES:
        EventStatus.objects.update_or_create(
            code=code,
            defaults={
                "allows_editing": editing,
                "generates_alerts": alerts,
                "is_terminal": terminal,
                "is_visible": visible,
                "label": label,
            },
        )
