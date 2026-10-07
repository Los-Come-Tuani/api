from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_profiles.enums import CredentialStates, ProviderStates
from api_profiles.models import CredentialStatus, ProviderStatus

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - (código, etiqueta, visible, acepta reservas): `estado_prestador` del modelo
PROVIDER_STATES: Final[tuple[tuple[ProviderStates, str, bool, bool], ...]] = (
    (ProviderStates.UNACCREDITED, "Sin acreditar", False, False),
    (ProviderStates.IN_REVIEW, "En revisión", False, False),
    (ProviderStates.ACTIVE, "Activo", True, True),
    (ProviderStates.SUSPENDED, "Suspendido", False, False),
)

# - (código, etiqueta, acredita, es terminal): `estado_acreditacion` del modelo, más
#   `reemplazada`
CREDENTIAL_STATES: Final[tuple[tuple[CredentialStates, str, bool, bool], ...]] = (
    (CredentialStates.UPLOADED, "Cargada", False, False),
    (CredentialStates.IN_REVIEW, "En revisión", False, False),
    (CredentialStates.APPROVED, "Aprobada", True, False),
    (CredentialStates.REJECTED, "Rechazada", False, True),
    (CredentialStates.EXPIRED, "Vencida", False, True),
    (CredentialStates.REPLACED, "Reemplazada", False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, is_visible, accepts_bookings in PROVIDER_STATES:
        ProviderStatus.objects.get_or_create(
            code=code,
            defaults={
                "accepts_bookings": accepts_bookings,
                "is_visible": is_visible,
                "label": label,
            },
        )

    for code, label, accredits, is_terminal in CREDENTIAL_STATES:
        CredentialStatus.objects.get_or_create(
            code=code,
            defaults={
                "accredits": accredits,
                "is_terminal": is_terminal,
                "label": label,
            },
        )
