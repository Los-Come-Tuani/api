from http import HTTPStatus
from re import search
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet

from api_core.config import ApiConfig

if TYPE_CHECKING:
    from typing import Final

    from django.core.mail import EmailMessage
    from django.http import HttpResponse
    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

PASSWORD: Final[str] = "Clave-Segura-2026!"

# lo mínimo para construir un `ApiConfig` sin leer el entorno de quien corre las pruebas
BASE_CONFIG: Final[dict[str, str]] = {
    "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/db",
    "JWT_SECRET_KEY": "j" * 64,
    "REDIS_URL": "redis://127.0.0.1:6379",
    "SECRET_KEY": "s" * 64,
}

# lo que exige `DEPLOY=True` además de lo básico
DEPLOY_CONFIG: Final[dict[str, object]] = {
    "DEPLOY": True,
    "REDIS_SECRET_KEY": "r" * 64,
    "TOTP_ENCRYPTION_KEYS": Fernet.generate_key().decode(),
}

########################################################################################


def credentials(user: ApiUser, password: str = PASSWORD) -> dict[str, str]:
    # único lugar que sabe con qué campo se identifica quien inicia sesión
    return {"email": str(user.email), "password": password}


def bearer(access: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access}"}


def extract_code(message: EmailMessage) -> str:
    # los correos traen un único número de seis dígitos: el código
    match = search(r"\b(\d{6})\b", message.body)

    assert match is not None, message.body

    return match.group(1)


def body(response: HttpResponse) -> dict:
    data: dict = response.json()  # ty: ignore[unresolved-attribute]

    return data


def web_login(client: DMRClient, user: ApiUser, password: str = PASSWORD) -> dict:
    # como el portal: la sesión queda en las cookies del cliente
    response = client.post("/auth/web/login/", credentials(user, password))

    assert response.status_code == HTTPStatus.OK, response.content

    return body(response)


def build_config(**overrides: object) -> ApiConfig:
    return ApiConfig(**{**BASE_CONFIG, **overrides})  # ty: ignore[invalid-argument-type]


def build_deployed_config(**overrides: object) -> ApiConfig:
    return build_config(**{**DEPLOY_CONFIG, **overrides})
