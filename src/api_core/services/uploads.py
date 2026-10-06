from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid7

from django.db.models import TextChoices

from api_core.config import CONFIG
from api_core.services.storage import get_storage
from api_exceptions.enums import BadRequestErrorTypes, RequestScopes
from api_exceptions.errors import BadRequestError

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


@dataclass(frozen=True, slots=True)
class UploadRule:
    content_types: tuple[str, ...]
    max_bytes: int


RULES: Final[dict[str, UploadRule]] = {
    UploadKinds.LEGAL_DOCUMENT: UploadRule(
        content_types=("application/pdf", "image/jpeg", "image/png"),
        max_bytes=10 * MEGABYTE,
    ),
    UploadKinds.SIGNATURE_DISH_PHOTO: UploadRule(
        content_types=("image/jpeg", "image/png", "image/webp"),
        max_bytes=5 * MEGABYTE,
    ),
}

########################################################################################


def fail(field: str, message: str) -> BadRequestError:
    return BadRequestError(
        field_errors={field: message},
        type=BadRequestErrorTypes.FAILED_VALIDATION,
    ).scoped(RequestScopes.BODY)


# Valida lo que el cliente quiere subir y le da una URL firmada para hacerlo. El archivo
# no pasa por el API: el almacenamiento rechaza lo que no sea del tipo ni del tamaño
# declarados.
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
