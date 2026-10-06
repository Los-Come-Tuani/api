from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from asgiref.sync import async_to_sync
from dmr.test import DMRAsyncRequestFactory, assert_async_throttling
from dmr.throttling import Rate
from pydantic import ValidationError

from api_core.controllers.upload import UploadController
from api_core.services import storage as storage_module
from api_core.services.storage import (
    NOT_CONFIGURED_DETAIL,
    DisabledStorage,
    MemoryStorage,
    S3Storage,
)
from api_core.services.uploads import MEGABYTE, UploadKinds, verify_upload
from api_exceptions.errors import BadRequestError
from api_tests.helpers import body, build_config, build_deployed_config

if TYPE_CHECKING:
    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

PHOTO = {"content_type": "image/jpeg", "kind": "signature-dish-photo", "size": 200_000}
DOCUMENT = {
    "content_type": "application/pdf",
    "kind": "legal-document",
    "size": 900_000,
}


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


########################################################################################
# Pedir la URL firmada


def test_anyone_can_ask_for_a_signed_upload_without_a_session(
    client: DMRClient,
    memory: MemoryStorage,
) -> None:
    response = client.post("/upload/", PHOTO)

    assert response.status_code == HTTPStatus.CREATED, response.content
    signed = body(response)
    # la clave es de la clase de archivo y conserva la extensión del tipo
    assert signed["key"].startswith("signature-dish-photo/")
    assert signed["key"].endswith(".jpg")
    assert signed["url"] == "https://storage.example/bucket"
    assert signed["fields"]["Content-Type"] == "image/jpeg"
    assert signed["max_bytes"] == 5 * MEGABYTE
    assert signed["expires_in"] == 600
    assert memory.presigned[0].key == signed["key"]


def test_each_kind_of_file_has_its_own_limit(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    assert body(client.post("/upload/", DOCUMENT))["max_bytes"] == 10 * MEGABYTE


def test_two_requests_never_get_the_same_key(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    first = body(client.post("/upload/", PHOTO))["key"]
    second = body(client.post("/upload/", PHOTO))["key"]

    assert first != second


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        # un PDF no es la foto de un platillo
        ({**PHOTO, "content_type": "application/pdf"}, "body.content_type"),
        # ni un ejecutable un documento legal
        ({**DOCUMENT, "content_type": "application/x-msdownload"}, "body.content_type"),
        ({**PHOTO, "size": 5 * MEGABYTE + 1}, "body.size"),
        ({**DOCUMENT, "size": 10 * MEGABYTE + 1}, "body.size"),
    ],
)
def test_a_type_or_size_that_the_kind_does_not_allow_is_refused(
    client: DMRClient,
    memory: MemoryStorage,
    field: str,
    payload: dict,
) -> None:
    response = client.post("/upload/", payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert field in body(response)["field_errors"]
    assert memory.presigned == []


@pytest.mark.parametrize(
    "payload",
    [
        {**PHOTO, "kind": "otra-cosa"},
        {**PHOTO, "size": 0},
        {**PHOTO, "size": -1},
        {"kind": "legal-document"},
        {**PHOTO, "extra": "no"},
    ],
)
def test_a_malformed_request_is_refused(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    payload: dict,
) -> None:
    assert client.post("/upload/", payload).status_code == HTTPStatus.BAD_REQUEST


def test_without_a_bucket_uploading_says_so(
    client: DMRClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(storage_module, "current", DisabledStorage())

    response = client.post("/upload/", PHOTO)

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert body(response)["detail"] == NOT_CONFIGURED_DETAIL


def test_asking_for_uploads_is_throttled(memory: MemoryStorage) -> None:  # ruff: ignore[unused-function-argument]
    factory = DMRAsyncRequestFactory()

    async_to_sync(assert_async_throttling)(
        UploadController,
        lambda: factory.post("/upload/", PHOTO),
        max_requests=10,
        rate=Rate.minute,
        success_status=HTTPStatus.CREATED,
    )


########################################################################################
# Comprobar lo subido


def test_a_key_is_accepted_once_the_file_is_really_there(memory: MemoryStorage) -> None:
    key = "signature-dish-photo/abc.jpg"
    memory.put(key, content_type="image/jpeg", size=300_000)

    stored = verify_upload(UploadKinds.SIGNATURE_DISH_PHOTO, key, field="photo")

    assert (stored.key, stored.size) == (key, 300_000)


@pytest.mark.parametrize(
    ("key", "content_type", "size"),
    [
        # nunca se subió
        ("signature-dish-photo/falta.jpg", None, 0),
        # es de otra clase de archivo
        ("legal-document/acta.pdf", "application/pdf", 10),
        # se subió con otro tipo del que se declaró
        ("signature-dish-photo/raro.jpg", "application/zip", 10),
        # y con más peso del permitido
        ("signature-dish-photo/pesada.jpg", "image/jpeg", 6 * MEGABYTE),
    ],
)
def test_a_key_that_is_not_what_it_claims_is_refused(
    memory: MemoryStorage,
    content_type: str | None,
    key: str,
    size: int,
) -> None:
    if content_type is not None:
        memory.put(key, content_type=content_type, size=size)

    with pytest.raises(BadRequestError) as refused:
        verify_upload(UploadKinds.SIGNATURE_DISH_PHOTO, key, field="photo")

    assert "body.photo" in refused.value.field_errors


########################################################################################
# Configuración


def test_the_storage_is_off_without_a_bucket() -> None:
    assert build_config().storage_enabled is False


def test_the_storage_comes_on_with_the_three_settings() -> None:
    config = build_config(
        STORAGE_ACCESS_KEY_ID="clave",
        STORAGE_BUCKET="kplan",
        STORAGE_ENDPOINT_URL="https://cuenta.r2.cloudflarestorage.com",
        STORAGE_SECRET_ACCESS_KEY="secreto",
    )

    assert config.storage_enabled is True
    assert isinstance(S3Storage(config), S3Storage)


@pytest.mark.parametrize(
    "overrides",
    [
        {"STORAGE_BUCKET": "kplan"},
        {"STORAGE_BUCKET": "kplan", "STORAGE_ACCESS_KEY_ID": "clave"},
        {"STORAGE_ACCESS_KEY_ID": "clave", "STORAGE_SECRET_ACCESS_KEY": "secreto"},
    ],
)
def test_a_half_configured_storage_is_refused(overrides: dict) -> None:
    with pytest.raises(ValidationError, match="a medias"):
        build_config(**overrides)


def test_a_deployed_storage_needs_https() -> None:
    complete = {
        "STORAGE_ACCESS_KEY_ID": "clave",
        "STORAGE_BUCKET": "kplan",
        "STORAGE_SECRET_ACCESS_KEY": "secreto",
    }

    with pytest.raises(ValidationError, match="https"):
        build_deployed_config(**complete, STORAGE_ENDPOINT_URL="http://almacen.interno")

    # en desarrollo se admite un MinIO local
    assert build_config(
        **complete, STORAGE_ENDPOINT_URL="http://localhost:9000"
    ).storage_enabled
    assert build_deployed_config(
        **complete, STORAGE_ENDPOINT_URL="https://almacen.example"
    ).storage_enabled


def test_the_signed_form_asks_the_bucket_to_enforce_type_and_size() -> None:
    config = build_config(
        STORAGE_ACCESS_KEY_ID="clave",
        STORAGE_BUCKET="kplan",
        STORAGE_ENDPOINT_URL="https://cuenta.r2.cloudflarestorage.com",
        STORAGE_SECRET_ACCESS_KEY="secreto",
    )

    signed = S3Storage(config).presign_upload(
        content_type="image/jpeg",
        expires_in=600,
        key="signature-dish-photo/abc.jpg",
        max_bytes=5 * MEGABYTE,
    )

    assert signed.url.startswith("https://cuenta.r2.cloudflarestorage.com/kplan")
    assert signed.fields["key"] == "signature-dish-photo/abc.jpg"
    assert signed.fields["Content-Type"] == "image/jpeg"
    # la política firmada es lo que hace cumplir el límite de tamaño
    assert "policy" in signed.fields
    assert "x-amz-signature" in signed.fields
