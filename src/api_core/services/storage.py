from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

import boto3

from botocore.client import Config
from botocore.exceptions import ClientError

from api_core.config import CONFIG
from api_exceptions.errors import ServiceUnavailableError

if TYPE_CHECKING:
    from typing import Any, Final

    from api_core.config import ApiConfig

########################################################################################

NOT_CONFIGURED_DETAIL: Final[str] = "El almacenamiento de archivos no está configurado."


# Lo que el cliente necesita para subir un archivo directo al almacenamiento: un `PUT` a
# `url` con estas cabeceras y el archivo como cuerpo. No es un formulario `POST`: R2 no
# lo admite, y el `PUT` firmado funciona igual en S3, R2 y MinIO.
@dataclass(frozen=True, slots=True)
class PresignedUpload:
    key: str
    url: str
    # las cabeceras que firmó la URL y que el cliente tiene que mandar tal cual
    headers: dict[str, str]
    expires_in: int
    max_bytes: int


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size: int
    content_type: str


class Storage(Protocol):
    def presign_upload(
        self,
        *,
        content_type: str,
        expires_in: int,
        key: str,
        max_bytes: int,
        size: int,
    ) -> PresignedUpload: ...

    def stat(self, key: str) -> StoredObject | None: ...

    def presign_download(self, key: str, *, expires_in: int) -> str: ...

    def delete(self, key: str) -> None: ...


########################################################################################


# Un bucket compatible con S3 (AWS, Cloudflare R2, MinIO). Las URLs se firman en el
# propio servidor, sin red: solo `stat` y `delete` hablan con el almacenamiento.
class S3Storage:
    def __init__(self, config: ApiConfig) -> None:
        self.bucket: str = config.STORAGE_BUCKET

        self.client: Any = boto3.client(
            "s3",
            aws_access_key_id=config.STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=config.STORAGE_SECRET_ACCESS_KEY.get_secret_value(),
            config=Config(
                connect_timeout=5,
                read_timeout=10,
                retries={"max_attempts": 2},
                s3={"addressing_style": "path"},
                signature_version="s3v4",
            ),
            endpoint_url=config.STORAGE_ENDPOINT_URL or None,
            region_name=config.STORAGE_REGION,
        )

    def presign_upload(
        self,
        *,
        content_type: str,
        expires_in: int,
        key: str,
        max_bytes: int,
        size: int,
    ) -> PresignedUpload:
        # el tipo y el tamaño van dentro de la firma: el propio almacenamiento rechaza
        # el `PUT` si el archivo no es del tipo ni del peso con que se pidió la URL
        url: str = self.client.generate_presigned_url(
            "put_object",
            ExpiresIn=expires_in,
            HttpMethod="PUT",
            Params={
                "Bucket": self.bucket,
                "ContentLength": size,
                "ContentType": content_type,
                "Key": key,
            },
        )

        return PresignedUpload(
            expires_in=expires_in,
            headers={"Content-Type": content_type},
            key=key,
            max_bytes=max_bytes,
            url=str(url),
        )

    def stat(self, key: str) -> StoredObject | None:
        try:
            head: dict[str, Any] = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return None

            raise

        return StoredObject(
            content_type=str(head.get("ContentType", "")),
            key=key,
            size=int(head.get("ContentLength", 0)),
        )

    def presign_download(self, key: str, *, expires_in: int) -> str:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                ExpiresIn=expires_in,
                Params={"Bucket": self.bucket, "Key": key},
            )
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


########################################################################################


# Sin bucket configurado: nada se sube y quien lo intente recibe un 503 que lo explica.
class DisabledStorage:
    def presign_upload(self, **kwargs: object) -> PresignedUpload:  # ruff: ignore[unused-method-argument, no-self-use]
        raise ServiceUnavailableError(detail=NOT_CONFIGURED_DETAIL)

    def stat(self, key: str) -> StoredObject | None:  # ruff: ignore[unused-method-argument, no-self-use]
        raise ServiceUnavailableError(detail=NOT_CONFIGURED_DETAIL)

    def presign_download(self, key: str, *, expires_in: int) -> str:  # ruff: ignore[unused-method-argument, no-self-use]
        raise ServiceUnavailableError(detail=NOT_CONFIGURED_DETAIL)

    def delete(self, key: str) -> None:  # ruff: ignore[unused-method-argument, no-self-use]
        raise ServiceUnavailableError(detail=NOT_CONFIGURED_DETAIL)


########################################################################################


# Un almacenamiento en memoria para las pruebas: `put` hace de la subida del cliente.
@dataclass
class MemoryStorage:
    objects: dict[str, StoredObject] = field(default_factory=dict)
    presigned: list[PresignedUpload] = field(default_factory=list)

    def put(self, key: str, *, content_type: str, size: int = 1024) -> None:
        self.objects[key] = StoredObject(content_type=content_type, key=key, size=size)

    def presign_upload(
        self,
        *,
        content_type: str,
        expires_in: int,
        key: str,
        max_bytes: int,
        size: int,  # ruff: ignore[unused-method-argument]
    ) -> PresignedUpload:
        signed = PresignedUpload(
            expires_in=expires_in,
            headers={"Content-Type": content_type},
            key=key,
            max_bytes=max_bytes,
            url=f"https://storage.example/bucket/{key}",
        )

        self.presigned.append(signed)

        return signed

    def stat(self, key: str) -> StoredObject | None:
        return self.objects.get(key)

    def presign_download(self, key: str, *, expires_in: int) -> str:  # ruff: ignore[no-self-use]
        return f"https://storage.example/bucket/{key}?expires={expires_in}"

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


########################################################################################

# - lo que usa el servicio; las pruebas lo reemplazan por un `MemoryStorage`
current: Storage | None = None


def get_storage() -> Storage:
    global current  # ruff: ignore[global-statement]

    if current is None:
        current = S3Storage(CONFIG) if CONFIG.storage_enabled else DisabledStorage()

    return current
