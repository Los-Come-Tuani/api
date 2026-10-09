from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid7

from django.db.models import TextChoices

from api_core.config import CONFIG
from api_core.services.storage import get_storage
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError, ServiceUnavailableError

if TYPE_CHECKING:
    from typing import Final

    from api_core.services.storage import PresignedUpload, StoredObject

########################################################################################

MEGABYTE: Final[int] = 1024 * 1024

EXTENSIONS: Final[dict[str, str]] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


# Qué se sube: cada clase de archivo tiene sus propios tipos y su propio tamaño máximo.
class UploadKinds(TextChoices):
    # el documento que acredita a una organización: existencia legal o representación
    LEGAL_DOCUMENT = "legal-document"
    # la fotografía del platillo estrella de un comercio
    SIGNATURE_DISH_PHOTO = "signature-dish-photo"
    # un documento de un guía o traductor (cédula, licencia...): casi siempre una foto
    # tomada con el teléfono (RF-P-20)
    PROVIDER_DOCUMENT = "provider-document"
    # la foto del perfil público de un guía o traductor
    PROVIDER_PHOTO = "provider-photo"
    # una foto de un lugar o de una de sus novedades
    PLACE_PHOTO = "place-photo"
    # una foto de un circuito oficial
    CIRCUIT_PHOTO = "circuit-photo"
    # una foto de un evento de la agenda
    EVENT_PHOTO = "event-photo"
    # la imagen de una campaña de cupones
    COUPON_PHOTO = "coupon-photo"


@dataclass(frozen=True, slots=True)
class UploadRule:
    content_types: tuple[str, ...]
    max_bytes: int


DOCUMENT_RULE: Final[UploadRule] = UploadRule(
    content_types=("application/pdf", "image/jpeg", "image/png"),
    max_bytes=10 * MEGABYTE,
)

PHOTO_RULE: Final[UploadRule] = UploadRule(
    content_types=("image/jpeg", "image/png", "image/webp"),
    max_bytes=5 * MEGABYTE,
)

RULES: Final[dict[str, UploadRule]] = {
    UploadKinds.CIRCUIT_PHOTO: PHOTO_RULE,
    UploadKinds.COUPON_PHOTO: PHOTO_RULE,
    UploadKinds.EVENT_PHOTO: PHOTO_RULE,
    UploadKinds.LEGAL_DOCUMENT: DOCUMENT_RULE,
    UploadKinds.PLACE_PHOTO: PHOTO_RULE,
    UploadKinds.PROVIDER_DOCUMENT: DOCUMENT_RULE,
    UploadKinds.PROVIDER_PHOTO: PHOTO_RULE,
    UploadKinds.SIGNATURE_DISH_PHOTO: PHOTO_RULE,
}

########################################################################################


def fail(field: str, message: str) -> BadRequestError:
    return BadRequestError(
        field_errors={field: message},
        type=BadRequestErrorTypes.FAILED_VALIDATION,
    ).scoped(RequestScopes.BODY)


# Valida lo que el cliente quiere subir y le da una URL firmada para hacerlo (un `PUT`).
# El archivo no pasa por el API: el almacenamiento rechaza lo que no sea del tipo ni del
# tamaño declarados, porque ambos van dentro de la firma.
def issue_upload(kind: str, content_type: str, size: int) -> PresignedUpload:
    rule: UploadRule = RULES[kind]

    if content_type not in rule.content_types:
        raise fail(
            "content_type",
            "Ese tipo de archivo no se admite aquí. Usa "
            + ", ".join(
                EXTENSIONS[item].removeprefix(".") for item in rule.content_types
            )
            + ".",
        )

    if size > rule.max_bytes:
        raise fail(
            "size",
            f"El archivo pesa más de {rule.max_bytes // MEGABYTE} MB.",
        )

    return get_storage().presign_upload(
        content_type=content_type,
        expires_in=int(CONFIG.STORAGE_UPLOAD_EXPIRES.total_seconds()),
        key=f"{kind}/{uuid7()}{EXTENSIONS[content_type]}",
        max_bytes=rule.max_bytes,
        size=size,
    )


# Comprueba que `key` sea de esa clase de archivo y que ya esté subido con lo declarado.
# Quien manda una solicitud referencia sus archivos por la clave que recibió al
# subirlos; sin esta comprobación podría apuntar a cualquier objeto del almacenamiento.
def verify_upload(kind: str, key: str, *, field: str) -> StoredObject:
    rule: UploadRule = RULES[kind]

    if not key.startswith(f"{kind}/"):
        raise fail(field, "Ese archivo no es del tipo que se pide.")

    stored: StoredObject | None = get_storage().stat(key)

    if stored is None:
        raise fail(field, "No encontramos ese archivo. Súbelo de nuevo.")

    if stored.content_type not in rule.content_types or stored.size > rule.max_bytes:
        raise fail(field, "El archivo no es del tipo o del tamaño permitidos.")

    return stored


# Una URL para ver un archivo del almacenamiento privado; vence en minutos (en horas
# las del contenido público, `public`). Es nula si el almacenamiento no está
# configurado: lo demás se lee igual, sin el enlace.
def read_url(key: str, *, public: bool = False) -> str | None:
    expires = (
        CONFIG.STORAGE_PUBLIC_EXPIRES if public else CONFIG.STORAGE_DOWNLOAD_EXPIRES
    )

    try:
        return get_storage().presign_download(
            key,
            expires_in=int(expires.total_seconds()),
        )
    except ServiceUnavailableError:
        return None
