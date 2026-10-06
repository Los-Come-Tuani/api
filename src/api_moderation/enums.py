from django.db.models import TextChoices

########################################################################################


class VerificationStates(TextChoices):
    # los códigos de `estado_verificacion`: el ciclo es el mismo para todo lo que se
    # verifica (ver el diagrama de estados de la verificación)
    SUBMITTED = "enviada"
    IN_REVIEW = "en_revision"
    APPROVED = "aprobada"
    REJECTED = "rechazada"


class VerificationKinds(TextChoices):
    # lo que se verifica: cuál de las llaves de `solicitud_verificacion` está presente
    BUSINESS = "business"
    INSTITUTION = "institution"
    MUNICIPALITY = "municipality"
