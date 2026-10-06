from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_catalogs.models import (
    BusinessType,
    Currency,
    InstitutionType,
    Reason,
    ReasonContext,
)

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - dónde se ofrece cada lista de motivos
CONTEXT_VERIFICATION_REJECTION: Final[str] = "rechazo_verificacion"

# - (código, etiqueta): `catalogos` y `organizaciones` del modelo de dominio
BUSINESS_TYPES: Final[tuple[tuple[str, str], ...]] = (
    ("restaurante", "Restaurante"),
    ("cafeteria", "Cafetería"),
    ("panaderia", "Panadería"),
    ("artesania", "Artesanía"),
    ("otro", "Otro"),
)

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

# - (código ISO, nombre, decimales)
CURRENCIES: Final[tuple[tuple[str, str, int], ...]] = (
    ("NIO", "Córdoba nicaragüense", 2),
    ("USD", "Dólar estadounidense", 2),
)

########################################################################################


@atomic
def execute() -> None:
    # `get_or_create`: lo que el equipo desactiva o ajusta después no se pisa al migrar
    for code, label in BUSINESS_TYPES:
        BusinessType.objects.get_or_create(code=code, defaults={"label": label})

    for code, label in INSTITUTION_TYPES:
        InstitutionType.objects.get_or_create(code=code, defaults={"label": label})

    for order, (code, label, requires_text) in enumerate(
        VERIFICATION_REJECTION_REASONS
    ):
        reason, _ = Reason.objects.get_or_create(
            code=code,
            defaults={"label": label, "requires_text": requires_text},
        )
        ReasonContext.objects.get_or_create(
            context=CONTEXT_VERIFICATION_REJECTION,
            reason=reason,
            defaults={"order": order},
        )

    for code, name, decimals in CURRENCIES:
        Currency.objects.get_or_create(
            code=code,
            defaults={"decimals": decimals, "name": name},
        )
