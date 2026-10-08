from typing import TYPE_CHECKING, Any

from django.db.models import Prefetch

from api_core.services.uploads import read_url, verify_upload
from api_organizations.models import Photo
from api_territory.schemas.common import ImageGet

from .access import invalid

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.db.models import Model

########################################################################################

# - las imágenes del contenido de ejemplo y de lo que ya se publicó fuera del
#   almacenamiento son direcciones públicas: se devuelven tal cual
EXTERNAL_PREFIX: str = "https://"


def image_payload(key: str) -> ImageGet:
    return ImageGet(
        key=key,
        url=key if key.startswith(EXTERNAL_PREFIX) else read_url(key, public=True),
    )


def ordered_photos(prefix: str = "") -> Prefetch:
    return Prefetch(
        f"{prefix}photos",
        queryset=Photo.objects.order_by("order", "id"),
    )


def photos_payload(owner: Model) -> list[ImageGet]:
    found: Any = owner

    return [image_payload(str(photo.file_key)) for photo in found.photos.all()]


# Comprueba las claves que llegan: las que el objeto ya tiene pasan; las nuevas tienen
# que ser archivos ya subidos de esa clase. Va fuera de la transacción: consulta el
# almacenamiento.
def check_images(
    keys: Sequence[str],
    *,
    current: Sequence[str],
    field: str,
    kind: str,
) -> list[str]:
    if len(set(keys)) != len(keys):
        raise invalid(field, "Hay una foto repetida.")

    known: set[str] = set(current)

    for key in keys:
        if key not in known:
            verify_upload(kind, key, field=field)

    return list(keys)


# Reemplaza las fotos de un dueño por las de la lista, en ese orden.
def replace_photos(owner_field: str, owner: Model, keys: Sequence[str]) -> None:
    Photo.objects.filter(**{owner_field: owner}).delete()
    Photo.objects.bulk_create(
        Photo(file_key=key, order=order, **{owner_field: owner})
        for order, key in enumerate(keys)
    )


def current_keys(owner_field: str, owner: Model) -> list[str]:
    return [
        str(key)
        for key in Photo.objects
        .filter(**{owner_field: owner})
        .order_by("order", "id")
        .values_list("file_key", flat=True)
    ]
