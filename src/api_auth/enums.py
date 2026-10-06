from django.db.models import TextChoices

########################################################################################


class ApiUserTypes(TextChoices):
    ADMIN = "Administrador"
    CLIENT = "Cliente"
    STAFF = "Personal"


########################################################################################


class ApiUserStatus(TextChoices):
    # estados de la cuenta (RF-S-10). Solo `ACTIVE` permite operar; `is_active` es el
    # reflejo de eso en la base y una restricción impide que se desalineen.
    PENDING = "pending"  # sin verificar el correo, o invitación sin aceptar
    ACTIVE = "active"
    SUSPENDED = "suspended"  # suspendida temporalmente
    EXPELLED = "expelled"  # expulsada de forma permanente
    CLOSING = "closing"  # en proceso de baja (treinta días antes de destruirse)


class IdentityProviders(TextChoices):
    GOOGLE = "google"


class GroupKinds(TextChoices):
    # de dónde es un grupo: decide por cuál superficie entra quien lo tiene (RF-S-08)
    OPERATOR = "operator"  # negocios, alcaldías e instituciones: portal
    PUBLIC = "public"  # turistas, guías y traductores: app móvil
    STAFF = "staff"  # el equipo de K'Plan: portal


class Surfaces(TextChoices):
    MOBILE = "mobile"
    WEB = "web"


class AccountRoles(TextChoices):
    # el papel que ven los clientes (`role` del usuario de la sesión)
    ADMIN = "admin"
    ALCALDIA = "alcaldia"
    GUIA = "guia"
    INSTITUCION = "institucion"
    NEGOCIO = "negocio"
    TRADUCTOR = "traductor"
    TURISTA = "turista"


class VerificationPurposes(TextChoices):
    EMAIL = "email"  # alta de una cuenta nueva
    INVITATION = "invitation"  # una persona del equipo acepta su invitación
    PASSWORD_RESET = "password_reset"  # ruff: ignore[hardcoded-password-string]


########################################################################################


class TokenTypes(TextChoices):
    ACCESS = "access"
    CHALLENGE = "challenge"
    REFRESH = "refresh"


########################################################################################


class PermissionTypes(TextChoices):
    ADD = "add"
    CHANGE = "change"
    DELETE = "delete"
    VIEW = "view"
