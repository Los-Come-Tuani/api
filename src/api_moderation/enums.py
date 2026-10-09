from typing import TYPE_CHECKING

from django.db.models import TextChoices

if TYPE_CHECKING:
    from typing import Final

########################################################################################


class VerificationStates(TextChoices):
    # los códigos de `estado_verificacion`: el ciclo es el mismo para todo lo que se
    # verifica (ver el diagrama de estados de la verificación)
    SUBMITTED = "enviada"
    IN_REVIEW = "en_revision"
    APPROVED = "aprobada"
    REJECTED = "rechazada"


# - cómo se llaman los estados hacia afuera: el API habla en inglés, y los códigos del
#   catálogo son los del modelo de dominio
API_STATUS: Final[dict[str, str]] = {
    VerificationStates.APPROVED: "approved",
    VerificationStates.IN_REVIEW: "in_review",
    VerificationStates.REJECTED: "rejected",
    VerificationStates.SUBMITTED: "submitted",
}


class VerificationKinds(TextChoices):
    # lo que se verifica: cuál de las llaves de `solicitud_verificacion` está presente
    BUSINESS = "business"
    INSTITUTION = "institution"
    MUNICIPALITY = "municipality"


class VerificationProcedures(TextChoices):
    # el trámite: el alta de lo que aspira a existir, o renovar un documento de lo que
    # ya existe (un prestador aprobado)
    APPLICATION = "alta"
    RENEWAL = "renovacion"


PROCEDURE_API_NAMES: Final[dict[str, str]] = {
    VerificationProcedures.APPLICATION: "application",
    VerificationProcedures.RENEWAL: "renewal",
}
