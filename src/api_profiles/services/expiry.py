from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from asgiref.sync import async_to_sync
from django.db.transaction import atomic

from api_auth.services.mail import send_provider_suspended
from api_profiles.enums import CredentialStates, ProviderStates
from api_profiles.models import Credential, ProviderProfile
from api_profiles.services.documents import (
    credential_state,
    in_force_by_type,
    missing_in_force,
    provider_state,
    required_of,
)

if TYPE_CHECKING:
    from datetime import date

    from api_catalogs.models import CredentialType

########################################################################################


@dataclass(slots=True)
class ExpiryReport:
    expired: int = 0
    # (correo, nombre, documentos que le faltan)
    suspended: list[tuple[str, str, list[str]]] = field(default_factory=list)


# El barrido diario: lo aprobado cuya fecha ya pasó queda vencido, y el prestador activo
# que se queda sin un documento en vigor de los que se le piden pasa a suspendido. Lo
# hace un proceso programado y no la app: si dependiera de que alguien abra el portal,
# una licencia vencida seguiría recibiendo reservas (RF-P-05).
def expire_credentials_sync(today: date) -> ExpiryReport:
    report = ExpiryReport()

    with atomic():
        report.expired = Credential.objects.filter(
            expires_on__lt=today,
            status__code=CredentialStates.APPROVED,
        ).update(status=credential_state(CredentialStates.EXPIRED))

        active: Any = (
            ProviderProfile.objects
            .select_related("user")
            .select_for_update(of=("self",))
            .filter(status__code=ProviderStates.ACTIVE)
        )

        for profile in active:
            lacking: list[CredentialType] = missing_in_force(
                required_of(profile),
                in_force_by_type(profile, today),
            )

            if not lacking:
                continue

            ProviderProfile.objects.filter(pk=profile.pk).update(
                status=provider_state(ProviderStates.SUSPENDED)
            )
            report.suspended.append((
                str(profile.user.email),
                str(profile.user.display_name),
                [str(item.label) for item in lacking],
            ))

    # los correos van fuera de la transacción: un proveedor lento no la deja abierta
    for email, name, documents in report.suspended:
        async_to_sync(send_provider_suspended)(documents=documents, name=name, to=email)

    return report
