from typing import TYPE_CHECKING, NamedTuple

from django.db.transaction import atomic

from api_catalogs.models import (
    BenefitType,
    BusinessType,
    CredentialType,
    CulturalPillar,
    Currency,
    EventCategory,
    InstitutionType,
    Language,
    Reason,
    ReasonContext,
    ServiceType,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - dónde se ofrece cada lista de motivos
CONTEXT_VERIFICATION_REJECTION: Final[str] = "rechazo_verificacion"
CONTEXT_DOCUMENT_REJECTION: Final[str] = "rechazo_documento"
CONTEXT_PROVIDER_REJECTION: Final[str] = "rechazo_prestador"

# - el motivo con que se cierra un expediente cuando quien revisa pide correcciones: no
#   se ofrece en ninguna lista, lo pone el sistema
CHANGES_REQUESTED_REASON: Final[str] = "documentos_por_corregir"

# - (código, etiqueta): `catalogos` y `organizaciones` del modelo de dominio
BUSINESS_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("restaurante", "Restaurante"),
    ("cafeteria", "Cafetería"),
    ("panaderia", "Panadería"),
    ("artesania", "Artesanía"),
    ("otro", "Otro"),
)

# - (código, etiqueta): los pilares culturales que clasifican los lugares (RF-T-29), en
#   el orden en que la app los muestra
CULTURAL_PILLARS: Final[tuple[tuple[str, str], ...]] = (
    ("historia", "Historia"),
    ("cultura", "Cultura"),
    ("gastronomia", "Gastronomía"),
    ("naturaleza", "Naturaleza"),
    ("aventura", "Aventura"),
)

# - (código, etiqueta): las clases de evento de la agenda, en el orden del portal
EVENT_CATEGORIES: Final[tuple[tuple[str, str], ...]] = (
    ("tradicion", "Tradición"),
    ("feria", "Feria"),
    ("cultura", "Cultura"),
    ("taller", "Taller"),
    ("charla", "Charla"),
    ("musica", "Música"),
    ("gastronomia", "Gastronomía"),
)

# - (código, etiqueta, exige monto, es porcentaje): lo que da un cupón
BENEFIT_TYPES: Final[tuple[tuple[str, str, bool, bool], ...]] = (
    ("descuento_porcentaje", "Descuento en porcentaje", True, True),
    ("descuento_monto", "Descuento en córdobas", True, False),
    ("producto_gratis", "Producto gratis", False, False),
    ("regalo", "Regalo", False, False),
)

# - el pilar del lugar que se crea al aprobar un comercio, según su giro
PILLAR_BY_BUSINESS_TYPE: Final[dict[str, str]] = {
    "artesania": "cultura",
    "cafeteria": "gastronomia",
    "otro": "cultura",
    "panaderia": "gastronomia",
    "restaurante": "gastronomia",
}

INSTITUTION_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("casa_cultura", "Casa de cultura"),
    ("fundacion", "Fundación"),
    ("ticketera", "Ticketera"),
    ("teatro", "Teatro"),
)

# - (código, etiqueta, exige texto): por qué se rechaza un registro (RF-B-04)
VERIFICATION_REJECTION_REASONS: Final[tuple[tuple[str, str, bool], ...]] = (
    ("documento_ilegible", "El documento no se lee", False),
    ("documento_vencido", "El documento está vencido", False),
    ("datos_no_coinciden", "Los datos no coinciden con el documento", False),
    ("ruc_invalido", "El RUC no es válido", False),
    ("ubicacion_incorrecta", "La ubicación no es correcta", False),
    ("representacion_no_acreditada", "No se acredita la representación", False),
    ("registro_duplicado", "Ya existe un registro igual", False),
    ("otro", "Otro motivo", True),
)

# - (código, etiqueta, exige texto): por qué se rechaza un documento de un prestador
DOCUMENT_REJECTION_REASONS: Final[tuple[tuple[str, str, bool], ...]] = (
    ("documento_ilegible", "El documento no se lee", False),
    ("documento_vencido", "El documento está vencido", False),
    ("datos_no_coinciden", "Los datos no coinciden con el documento", False),
    ("documento_incompleto", "Falta una cara o una página", False),
    ("documento_no_corresponde", "No es el documento que se pide", False),
    ("otro", "Otro motivo", True),
)

# - (código, etiqueta, exige texto): por qué quien decide rechaza a un prestador
PROVIDER_REJECTION_REASONS: Final[tuple[tuple[str, str, bool], ...]] = (
    ("antecedentes_no_favorables", "Los antecedentes no son favorables", False),
    ("datos_no_coinciden", "Los datos no coinciden con el documento", False),
    ("registro_duplicado", "Ya existe un registro igual", False),
    ("otro", "Otro motivo", True),
)

# - (código ISO, nombre, decimales)
CURRENCIES: Final[tuple[tuple[str, str, int], ...]] = (
    ("NIO", "Córdoba nicaragüense", 2),
    ("USD", "Dólar estadounidense", 2),
)

# - (código ISO 639-1, nombre)
LANGUAGES: Final[tuple[tuple[str, str], ...]] = (
    ("es", "Español"),
    ("en", "Inglés"),
    ("fr", "Francés"),
    ("de", "Alemán"),
    ("it", "Italiano"),
    ("pt", "Portugués"),
)

# - (código, etiqueta): lo que ofrece un prestador
SERVICE_GUIDE: Final[str] = "guia"
SERVICE_TRANSLATOR: Final[str] = "traductor"

SERVICE_TYPES: Final[tuple[tuple[str, str], ...]] = (
    (SERVICE_GUIDE, "Guía de turismo"),
    (SERVICE_TRANSLATOR, "Traductor"),
)


class CredentialTypeSpec(NamedTuple):
    code: str
    label: str
    # el servicio que acredita, o nulo si se le pide a todos
    service: str | None
    requires_expiry: bool
    requires_vehicle: bool = False


# - los documentos que se le piden a un prestador, en el orden en que se muestran
CREDENTIAL_TYPES: Final[tuple[CredentialTypeSpec, ...]] = (
    CredentialTypeSpec("cedula", "Cédula de identidad", None, requires_expiry=True),
    CredentialTypeSpec(
        "record_policia", "Récord de policía", None, requires_expiry=False
    ),
    CredentialTypeSpec(
        "licencia_intur",
        "Licencia o carné del INTUR",
        SERVICE_GUIDE,
        requires_expiry=True,
    ),
    CredentialTypeSpec(
        "certificado_idioma",
        "Certificado de idiomas",
        SERVICE_TRANSLATOR,
        requires_expiry=False,
    ),
    CredentialTypeSpec(
        "licencia_conducir",
        "Licencia de conducir",
        None,
        requires_expiry=True,
        requires_vehicle=True,
    ),
    CredentialTypeSpec(
        "seguro_vehiculo",
        "Seguro del vehículo",
        None,
        requires_expiry=True,
        requires_vehicle=True,
    ),
)

########################################################################################


# Los catálogos de lugares, agenda y cupones (F4 y F6).
def seed_content_catalogs() -> None:
    for order, (code, label) in enumerate(CULTURAL_PILLARS):
        CulturalPillar.objects.get_or_create(
            code=code,
            defaults={"label": label, "order": order},
        )

    for order, (code, label) in enumerate(EVENT_CATEGORIES):
        EventCategory.objects.get_or_create(
            code=code,
            defaults={"label": label, "order": order},
        )

    for code, label, requires_amount, is_percentage in BENEFIT_TYPES:
        BenefitType.objects.get_or_create(
            code=code,
            defaults={
                "is_percentage": is_percentage,
                "label": label,
                "requires_amount": requires_amount,
            },
        )


@atomic
def execute() -> None:
    # `get_or_create`: lo que el equipo desactiva o ajusta después no se pisa al migrar
    for code, label in BUSINESS_TYPES:
        BusinessType.objects.get_or_create(code=code, defaults={"label": label})

    for code, label in INSTITUTION_TYPES:
        InstitutionType.objects.get_or_create(code=code, defaults={"label": label})

    for context, reasons in (
        (CONTEXT_VERIFICATION_REJECTION, VERIFICATION_REJECTION_REASONS),
        (CONTEXT_DOCUMENT_REJECTION, DOCUMENT_REJECTION_REASONS),
        (CONTEXT_PROVIDER_REJECTION, PROVIDER_REJECTION_REASONS),
    ):
        for order, (code, label, requires_text) in enumerate(reasons):
            reason, _ = Reason.objects.get_or_create(
                code=code,
                defaults={"label": label, "requires_text": requires_text},
            )
            ReasonContext.objects.get_or_create(
                context=context,
                reason=reason,
                defaults={"order": order},
            )

    Reason.objects.get_or_create(
        code=CHANGES_REQUESTED_REASON,
        defaults={"label": "Hay documentos por corregir"},
    )

    for code, name, decimals in CURRENCIES:
        Currency.objects.get_or_create(
            code=code,
            defaults={"decimals": decimals, "name": name},
        )

    for code, name in LANGUAGES:
        Language.objects.get_or_create(code=code, defaults={"name": name})

    seed_content_catalogs()

    services: dict[str, ServiceType] = {}

    for code, label in SERVICE_TYPES:
        services[code], _ = ServiceType.objects.get_or_create(
            code=code,
            defaults={"label": label},
        )

    for order, spec in enumerate(CREDENTIAL_TYPES):
        CredentialType.objects.get_or_create(
            code=spec.code,
            defaults={
                "label": spec.label,
                "order": order,
                "requires_expiry": spec.requires_expiry,
                "requires_vehicle": spec.requires_vehicle,
                "service": None if spec.service is None else services[spec.service],
            },
        )
