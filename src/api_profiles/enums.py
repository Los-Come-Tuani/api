from typing import TYPE_CHECKING

from django.db.models import TextChoices

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class ProviderStates(TextChoices):
    # los códigos de `estado_prestador` (ver el diagrama de estados del prestador)
    UNACCREDITED = "sin_acreditar"
    IN_REVIEW = "en_revision"
    ACTIVE = "activo"
    SUSPENDED = "suspendido"


PROVIDER_API_STATUS: Final[dict[str, str]] = {
    ProviderStates.ACTIVE: "active",
    ProviderStates.IN_REVIEW: "in_review",
    ProviderStates.SUSPENDED: "suspended",
    ProviderStates.UNACCREDITED: "unaccredited",
}


class CredentialStates(TextChoices):
    # los códigos de `estado_acreditacion`; solo `aprobada` está en vigor
    UPLOADED = "cargada"
    IN_REVIEW = "en_revision"
    APPROVED = "aprobada"
    REJECTED = "rechazada"
    EXPIRED = "vencida"
    # lo reemplazó uno más nuevo del mismo tipo (un aparte del modelo)
    REPLACED = "reemplazada"


CREDENTIAL_API_STATUS: Final[dict[str, str]] = {
    CredentialStates.APPROVED: "approved",
    CredentialStates.EXPIRED: "expired",
    CredentialStates.IN_REVIEW: "in_review",
    CredentialStates.REJECTED: "rejected",
    CredentialStates.REPLACED: "replaced",
    CredentialStates.UPLOADED: "uploaded",
}

# - los que todavía pueden quedar en vigor: el prestador no tiene que volver a subirlos
USABLE_CREDENTIAL_STATES: Final[frozenset[str]] = frozenset({
    CredentialStates.APPROVED,
    CredentialStates.IN_REVIEW,
    CredentialStates.UPLOADED,
})


class Verdicts(TextChoices):
    # lo que dijo quien revisó un documento, antes de que el expediente se resuelva
    ACCEPTED = "aceptada"
    REJECTED = "rechazada"


class LanguageLevels(TextChoices):
    BASIC = "basico"
    INTERMEDIATE = "intermedio"
    ADVANCED = "avanzado"
    NATIVE = "nativo"


LEVEL_API_NAMES: Final[dict[str, str]] = {
    LanguageLevels.ADVANCED: "advanced",
    LanguageLevels.BASIC: "basic",
    LanguageLevels.INTERMEDIATE: "intermediate",
    LanguageLevels.NATIVE: "native",
}

LEVEL_BY_API_NAME: Final[dict[str, str]] = {
    name: code for code, name in LEVEL_API_NAMES.items()
}
