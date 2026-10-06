from typing import Literal

from pydantic import PositiveInt

from api_core.schemas.base import DTO
from api_core.services.uploads import UploadKinds

########################################################################################


class UploadPost(DTO):
    kind: Literal[UploadKinds.LEGAL_DOCUMENT, UploadKinds.SIGNATURE_DISH_PHOTO]
    # el tipo MIME del archivo y su tamaño en bytes: la firma los lleva dentro y el
    # almacenamiento los hace cumplir
    content_type: str
    size: PositiveInt


class UploadGet(DTO):
    # la clave que se manda después al registrar lo que se sube
    key: str
    # se sube con un `PUT` a esta URL, con estas cabeceras y el archivo como cuerpo
    url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_in: PositiveInt
    max_bytes: PositiveInt
