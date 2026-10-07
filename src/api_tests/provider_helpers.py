from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

from django.core import mail
from django.utils.timezone import localdate
from dmr.test import DMRClient

from api_tests.helpers import PASSWORD, body, extract_code, web_login

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from typing import Final

    from api_auth.models import ApiUser
    from api_core.services.storage import MemoryStorage

########################################################################################

EMAIL: Final[str] = "marlene@example.com"
PHOTO_KEY: Final[str] = "provider-photo/marlene.jpg"

# - los tipos de documento y si vencen (la siembra de `api_catalogs`)
EXPIRES: Final[dict[str, bool]] = {
    "cedula": True,
    "certificado_idioma": False,
    "licencia_conducir": True,
    "licencia_intur": True,
    "record_policia": False,
    "seguro_vehiculo": True,
}

GUIDE_DOCUMENTS: Final[tuple[str, ...]] = ("cedula", "record_policia", "licencia_intur")


def key_of(code: str, version: int = 1) -> str:
    return f"provider-document/{code}-{version}.jpg"


def fill(storage: MemoryStorage, versions: int = 3) -> None:
    for code in EXPIRES:
        for version in range(1, versions + 1):
            storage.put(key_of(code, version), content_type="image/jpeg", size=400_000)

    storage.put(PHOTO_KEY, content_type="image/jpeg", size=200_000)


def document(code: str, version: int = 1, **override: object) -> dict:
    today = localdate()

    return {
        "expires_on": (
            (today + timedelta(days=5 * 365)).isoformat() if EXPIRES[code] else None
        ),
        "file_key": key_of(code, version),
        "issued_on": (today - timedelta(days=2 * 365)).isoformat(),
        "number": f"{code.upper()}-{version}",
        "type": code,
        **override,
    }


def documents(codes: Iterable[str], version: int = 1) -> list[dict]:
    return [document(code, version) for code in codes]


def profile_data(**override: object) -> dict:
    return {
        "carries_tourists": False,
        "city_id": None,
        "languages": [
            {"code": "es", "level": "native"},
            {"code": "en", "level": "advanced"},
        ],
        "phone": "+505 8831 4476",
        "presentation": "Seis años en Granada: historia colonial y gastronomía.",
        "services": ["guia"],
        **override,
    }


def code_for(client: DMRClient, email: str = EMAIL) -> str:
    # el mismo código del correo que usa el registro de la app
    mail.outbox.clear()
    response = client.post("/auth/register-code/", {"email": email})

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content

    return extract_code(mail.outbox[-1])


def application_payload(code: str, email: str = EMAIL, **override: object) -> dict:
    return {
        "birth_date": "1990-05-01",
        "code": code,
        "documents": documents(GUIDE_DOCUMENTS),
        "email": email,
        "first_name": "Marlene",
        "last_name": "Ríos",
        "nationality": "NI",
        "password": PASSWORD,
        **profile_data(),
        **override,
    }


def apply(client: DMRClient, email: str = EMAIL, **override: object) -> dict:
    # se postula de punta a punta, como la app: código del correo y alta
    response = client.post(
        "/provider-application/",
        application_payload(code_for(client, email), email, **override),
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


def provider_client(access: str) -> DMRClient:
    # como la app: el token va en la cabecera
    return DMRClient(headers={"Authorization": f"Bearer {access}"})


def team(
    make_member: Callable[..., ApiUser],
    *permissions: str,
    email: str = "revisora@example.com",
) -> DMRClient:
    client = DMRClient()
    web_login(client, make_member(email, *permissions))

    return client


def accept_all(client: DMRClient, request_id: str) -> dict:
    # quien revisa acepta cada documento que falta revisar
    detail = body(client.get(f"/provider-request/{request_id}/"))

    for item in detail["documents"]:
        if item["review"] is None:
            response = client.post(
                f"/provider-request/{request_id}/document-review/",
                {"accepted": True, "document_id": item["id"]},
            )

            assert response.status_code == HTTPStatus.OK, response.content
            detail = body(response)

    return detail


def approve(client: DMRClient, request_id: str) -> dict:
    accept_all(client, request_id)
    response = client.post(f"/provider-request/{request_id}/approve/", {})

    assert response.status_code == HTTPStatus.OK, response.content

    return body(response)
