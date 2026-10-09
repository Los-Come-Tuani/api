from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_catalogs.models import Reason, ReasonContext

if TYPE_CHECKING:
    from typing import Final

########################################################################################

CONTEXT_REPORT: Final[str] = "reporte"

# - (código, etiqueta, exige texto): por qué se reporta a alguien o un contenido
REPORT_REASONS: Final[tuple[tuple[str, str, bool], ...]] = (
    ("contenido_inapropiado", "Contenido inapropiado u ofensivo", False),
    ("acoso", "Acoso o trato irrespetuoso", False),
    ("fraude", "Fraude o cobro indebido", False),
    ("informacion_falsa", "Información falsa", False),
    ("incumplimiento", "No se presentó o no cumplió lo acordado", False),
    ("otro", "Otro motivo", True),
)

########################################################################################


@atomic
def execute() -> None:
    for order, (code, label, requires_text) in enumerate(REPORT_REASONS):
        reason, _ = Reason.objects.get_or_create(
            code=code,
            defaults={"label": label, "requires_text": requires_text},
        )
        ReasonContext.objects.get_or_create(
            context=CONTEXT_REPORT,
            reason=reason,
            defaults={"order": order},
        )
