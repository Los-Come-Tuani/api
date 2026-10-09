from base64 import urlsafe_b64encode
from datetime import timedelta
from functools import cached_property
from typing import Annotated, Final, Literal, Self
from urllib.parse import unquote, urlsplit

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from psycopg import IsolationLevel
from pydantic import (
    BeforeValidator,
    NonNegativeInt,
    PositiveInt,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    StringConstraints,
    model_validator,
)
from pydantic_core import MultiHostHost
from pydantic_settings import BaseSettings, SettingsConfigDict

from api_core.schemas.base import PermissiveDTO
from api_utils.env import ROOT

########################################################################################

MAX_SECRET_LENGTH: Final[int] = 256
MIN_SECRET_LENGTH: Final[int] = 64

# - Redis administrado con TLS (`rediss://`): Azure genera claves de 44 caracteres que
#   no se pueden alargar, y la conexión cifrada no deja ver la clave en la red
MIN_TLS_REDIS_SECRET_LENGTH: Final[int] = 32

type LongSecret = Annotated[
    SecretStr,
    StringConstraints(max_length=MAX_SECRET_LENGTH, min_length=MIN_SECRET_LENGTH),
]

type OptionalSecret = Annotated[
    SecretStr,
    StringConstraints(max_length=MAX_SECRET_LENGTH),
]

########################################################################################

# - desarrollo local: `localhost`/`127.0.0.1`, el portal (Vite, `:5173`) y el
#   emulador de Android, que llega al `localhost` de la máquina como `10.0.2.2`
DEV_ALLOWED_HOSTS: Final[tuple[str, ...]] = ("localhost", "127.0.0.1", "10.0.2.2")

DEV_ORIGINS: Final[tuple[str, ...]] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

# - Railway consulta `/health/` con este host; no depende del dominio del servicio
RAILWAY_HEALTHCHECK_HOST: Final[str] = "healthcheck.railway.app"

# - valores que estaban escritos a mano en `settings.py`. Se conservan solo mientras
#   el despliegue no defina `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y
#   `CSRF_TRUSTED_ORIGINS` como variables de entorno; después se pueden borrar.
LEGACY_DEPLOY_HOSTS: Final[tuple[str, ...]] = (
    "127.0.0.1",
    "localhost",
    RAILWAY_HEALTHCHECK_HOST,
    "api.kplan.dev",
    "staging-api.kplan.dev",
    "portal.kplan.dev",
    "staging-portal.kplan.dev",
)

LEGACY_DEPLOY_ORIGINS: Final[tuple[str, ...]] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://api.kplan.dev",
    "https://staging-api.kplan.dev",
    "https://portal.kplan.dev",
    "https://staging-portal.kplan.dev",
    # la landing manda las solicitudes de demo desde el navegador
    "https://kplan.dev",
    "https://www.kplan.dev",
)

LOCAL_HOSTNAMES: Final[frozenset[str]] = frozenset({"localhost", "127.0.0.1"})

########################################################################################


def split_csv(value: object) -> object:
    # `"a, b"` -> `("a", "b")`; cualquier otro valor pasa intacto
    if isinstance(value, str):
        return tuple(item.strip() for item in value.split(",") if item.strip())

    return value


type CsvList = Annotated[tuple[str, ...], BeforeValidator(split_csv)]

type SecretCsv = Annotated[tuple[SecretStr, ...], BeforeValidator(split_csv)]

########################################################################################


def derive_fernet_key(secret: str) -> bytes:
    # solo para desarrollo y pruebas, donde no hay `TOTP_ENCRYPTION_KEYS`
    key: bytes = HKDF(
        algorithm=SHA256(),
        info=b"kplan:totp-encryption",
        length=32,
        salt=None,
    ).derive(secret.encode())

    return urlsafe_b64encode(key)


########################################################################################


class ApiConfig(BaseSettings, PermissiveDTO):
    model_config = SettingsConfigDict(
        enable_decoding=False,
        env_file=(ROOT / ".env"),
        env_file_encoding="utf-8",
        # un error de configuración no debe volcar en los logs las claves ni la URL
        # de la base de datos que venían en la entrada
        hide_input_in_errors=True,
        validate_default=True,
    )

    DEBUG: bool = False
    DEPLOY: bool = False
    SKIP_SEEDERS: bool = False

    # - el contenido de ejemplo (`seedcontent --on-deploy`, al final de cada `migrate`
    #   con `DEPLOY=True`) solo se carga en develop-api y en el API de Azure: cuando
    #   Railway despliega una de estas ramas (`RAILWAY_GIT_BRANCH` la pone Railway si el
    #   despliegue viene de GitHub) o cuando `ALLOWED_HOSTS` incluye uno de estos
    #   dominios.
    RAILWAY_GIT_BRANCH: str = ""
    SEED_CONTENT_BRANCHES: CsvList = ("develop-a",)
    SEED_CONTENT_HOSTS: CsvList = ("develop-api.kplan.dev", "azure-api.kplan.dev")

    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"

    JWT_ACCESS_LIFETIME: timedelta = timedelta(hours=3)
    JWT_CHALLENGE_LIFETIME: timedelta = timedelta(minutes=5)
    JWT_REFRESH_LIFETIME: timedelta = timedelta(days=1)

    TOTP_DIGITS: Literal[6, 8] = 6
    TOTP_ISSUER: Annotated[
        str,
        StringConstraints(max_length=64, min_length=1),
    ] = "K'Plan"

    TOTP_LOCKOUT: timedelta = timedelta(minutes=15)
    TOTP_MAX_FAILURES: PositiveInt = 5
    TOTP_PERIOD: PositiveInt = 30
    TOTP_RECOVERY_CODES: PositiveInt = 10
    TOTP_TOLERANCE: NonNegativeInt = 1

    # - cinco intentos fallidos seguidos sobre el mismo identificador bloquean el acceso
    #   quince minutos (RF-S-06)
    LOGIN_LOCKOUT: timedelta = timedelta(minutes=15)
    LOGIN_MAX_FAILURES: PositiveInt = 5

    # - códigos de un solo uso por correo: alta de cuenta, invitación y recuperación
    VERIFICATION_LIFETIME: timedelta = timedelta(minutes=15)
    VERIFICATION_MAX_ATTEMPTS: PositiveInt = 5
    VERIFICATION_RESEND_AFTER: timedelta = timedelta(seconds=60)
    #   Solo en un API de pruebas sin proveedor de correo, donde el código de alta nunca
    #   llega: cualquier código de seis dígitos sirve para crear una cuenta. Hay que
    #   pedirlo igual, y sigue venciendo y gastándose. La recuperación de contraseña y
    #   las invitaciones no cambian. Con `EMAIL_HOST` no tiene efecto.
    VERIFICATION_ACCEPT_ANY_SIGNUP_CODE: bool = False

    # - plazo entre pedir la baja de la cuenta y destruir sus datos (RF-S-11)
    ACCOUNT_CLOSING_DELAY: timedelta = timedelta(days=30)

    # - inicio de sesión con Google. Son los Client ID de OAuth que pueden aparecer como
    #   `aud` del token de identidad (el de tipo "Web" que usan la app y el portal).
    #   Son públicos; no se necesita ningún secreto. Vacío = Google deshabilitado.
    GOOGLE_OAUTH_CLIENT_IDS: CsvList = ()

    # - avisos push con Firebase Cloud Messaging (API HTTP v1): el id del proyecto y la
    #   cuenta de servicio (el JSON completo en una línea). Vacíos = los avisos quedan
    #   solo en la bandeja de la app. Ver `docs/avisos.md`.
    FCM_PROJECT_ID: str = ""
    FCM_SERVICE_ACCOUNT: Annotated[SecretStr, StringConstraints(max_length=8192)] = (
        SecretStr(secret_value="")
    )

    # - la pasarela con la que se cobran las reservas. `manual`: el turista recibe estas
    #   instrucciones y el equipo confirma el pago a mano. Ver `docs/finanzas.md`.
    PAYMENT_GATEWAY: Literal["manual"] = "manual"
    PAYMENT_INSTRUCTIONS: Annotated[str, StringConstraints(max_length=2000)] = (
        "El equipo de K'Plan te escribirá para confirmar el pago de tu reserva."
    )

    # - correo saliente. Sin `EMAIL_HOST` los correos salen por consola en desarrollo y
    #   se descartan con `DEPLOY=True`, para que ningún código de verificación quede
    #   escrito en los logs de producción.
    DEFAULT_FROM_EMAIL: Annotated[
        str,
        StringConstraints(max_length=254, min_length=3),
    ] = "K'Plan <no-reply@localhost>"
    EMAIL_HOST: str = ""
    EMAIL_HOST_PASSWORD: OptionalSecret = SecretStr(secret_value="")
    EMAIL_HOST_USER: str = ""
    EMAIL_PORT: PositiveInt = 587
    EMAIL_USE_TLS: bool = True

    # - almacenamiento de archivos (documentos legales y fotos): un bucket compatible
    #   con S3, por ejemplo Cloudflare R2. Se sube directo desde el cliente con una URL
    #   firmada; el API nunca recibe el archivo. Vacío = sin almacenamiento (subir
    #   responde 503). `STORAGE_ENDPOINT_URL` vacío usa el de AWS; en R2 lleva la URL
    #   de la cuenta. Ver `docs/archivos.md`.
    STORAGE_ACCESS_KEY_ID: str = ""
    STORAGE_BUCKET: str = ""
    STORAGE_DOWNLOAD_EXPIRES: timedelta = timedelta(minutes=5)
    STORAGE_ENDPOINT_URL: str = ""
    # - las fotos del contenido público (lugares, circuitos, eventos, cupones) se ven en
    #   la app durante una sesión larga: su URL firmada dura más que la de un documento
    STORAGE_PUBLIC_EXPIRES: timedelta = timedelta(hours=24)
    STORAGE_REGION: str = "auto"
    STORAGE_SECRET_ACCESS_KEY: OptionalSecret = SecretStr(secret_value="")
    STORAGE_UPLOAD_EXPIRES: timedelta = timedelta(minutes=10)
    # - llaves Fernet con las que se cifra el secreto TOTP en la base, separadas por
    #   comas y la más nueva primero: rotar es anteponer una llave nueva y correr
    #   `rotatetotpkeys`. Obligatoria con `DEPLOY=True`; en desarrollo y pruebas, si se
    #   omite, se deriva de `SECRET_KEY`. Se genera con `just fernet-key`.
    TOTP_ENCRYPTION_KEYS: SecretCsv = ()

    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn

    JWT_SECRET_KEY: LongSecret
    SECRET_KEY: LongSecret

    REDIS_SECRET_KEY: OptionalSecret = SecretStr(secret_value="")

    # - listas separadas por comas. Vacías = valores de desarrollo; en producción se
    #   definen como variables del servicio, nunca en el repositorio.
    ALLOWED_HOSTS: CsvList = ()
    CORS_ALLOWED_ORIGINS: CsvList = ()
    CSRF_TRUSTED_ORIGINS: CsvList = ()

    @model_validator(mode="after")
    def check_allowed_hosts(self) -> Self:
        for host in self.ALLOWED_HOSTS:
            if "/" in host:
                raise ValueError(
                    f"`ALLOWED_HOSTS` solo admite nombres de host, no '{host}'.",
                )
            if host == "*" and self.DEPLOY:
                raise ValueError("`ALLOWED_HOSTS` no admite `*` si `DEPLOY=True`.")

        return self

    @model_validator(mode="after")
    def check_origins(self) -> Self:
        for name in ("CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"):
            for origin in getattr(self, name):
                parts = urlsplit(origin)

                if (
                    parts.scheme not in {"http", "https"}
                    or not parts.hostname
                    or origin != f"{parts.scheme}://{parts.netloc}"
                ):
                    raise ValueError(
                        f"`{name}` solo admite orígenes `esquema://host[:puerto]`, "
                        f"sin ruta ni `/` final; recibió '{origin}'.",
                    )

                if (
                    self.DEPLOY
                    and parts.scheme == "http"
                    and parts.hostname not in LOCAL_HOSTNAMES
                ):
                    raise ValueError(
                        f"`{name}` exige `https://` si `DEPLOY=True`; "
                        f"recibió '{origin}'.",
                    )

        return self

    @model_validator(mode="after")
    def check_cookie_policy(self) -> Self:
        if self.cookie_samesite == "None" and not self.cookie_secure:
            raise ValueError("`SameSite=None` requiere `Secure`.")

        return self

    @model_validator(mode="after")
    def check_database_url(self) -> Self:
        if self.DATABASE_URL.path is None:
            raise ValueError(
                "`DATABASE_URL` no define el nombre de la base de datos en `path`.",
            )
        if len(self.DATABASE_URL.hosts()) > 1:
            raise ValueError("`DATABASE_URL` debería tener un único host.")

        host = self.pg_host

        if host["host"] is None:
            raise ValueError("`DATABASE_URL` no define el host de la base de datos.")
        if host["username"] is None:
            raise ValueError("`DATABASE_URL` no define un usuario.")
        if host["password"] is None:
            raise ValueError("`DATABASE_URL` no define una contraseña.")

        return self

    @model_validator(mode="after")
    def check_totp_encryption_keys(self) -> Self:
        if self.DEPLOY and not self.TOTP_ENCRYPTION_KEYS:
            raise ValueError(
                "`TOTP_ENCRYPTION_KEYS` es obligatorio cuando `DEPLOY=True`; "
                "genere una llave con `just fernet-key`.",
            )

        for key in self.TOTP_ENCRYPTION_KEYS:
            try:
                Fernet(key.get_secret_value())
            except ValueError as e:
                raise ValueError(
                    "`TOTP_ENCRYPTION_KEYS` solo admite llaves Fernet "
                    "(32 bytes en base64 url-safe); genere una con `just fernet-key`.",
                ) from e

        return self

    @model_validator(mode="after")
    def check_storage(self) -> Self:
        # o está completo, o no está: a medias nunca funcionaría y fallaría al subir
        given = {
            "STORAGE_ACCESS_KEY_ID": bool(self.STORAGE_ACCESS_KEY_ID),
            "STORAGE_BUCKET": bool(self.STORAGE_BUCKET),
            "STORAGE_SECRET_ACCESS_KEY": bool(
                self.STORAGE_SECRET_ACCESS_KEY.get_secret_value()
            ),
        }

        if any(given.values()) and not all(given.values()):
            missing = ", ".join(name for name, value in given.items() if not value)

            raise ValueError(
                f"El almacenamiento está a medias: falta {missing}. "
                "Defina las tres variables o ninguna."
            )

        endpoint = self.STORAGE_ENDPOINT_URL

        if endpoint and not endpoint.startswith("https://") and self.DEPLOY:
            raise ValueError(
                "`STORAGE_ENDPOINT_URL` debe ser `https` cuando `DEPLOY=True`."
            )

        return self

    @property
    def storage_enabled(self) -> bool:
        return bool(self.STORAGE_BUCKET)

    @model_validator(mode="after")
    def check_redis_secret_key(self) -> Self:
        minimum = (
            MIN_TLS_REDIS_SECRET_LENGTH
            if self.REDIS_URL.scheme == "rediss"
            else MIN_SECRET_LENGTH
        )

        if self.DEPLOY and len(self.REDIS_SECRET_KEY.get_secret_value()) < minimum:
            raise ValueError(
                "`REDIS_SECRET_KEY` es obligatorio; "
                f"debe tener al menos {minimum} "
                "caracteres cuando `DEPLOY=True`.",
            )

        return self

    @cached_property
    def allowed_hosts(self) -> tuple[str, ...]:
        if self.ALLOWED_HOSTS:
            hosts = self.ALLOWED_HOSTS
        elif self.DEPLOY:
            hosts = LEGACY_DEPLOY_HOSTS
        else:
            hosts = DEV_ALLOWED_HOSTS

        if self.DEPLOY and RAILWAY_HEALTHCHECK_HOST not in hosts:
            hosts = (*hosts, RAILWAY_HEALTHCHECK_HOST)

        return hosts

    @cached_property
    def email_backend(self) -> str:
        if self.EMAIL_HOST:
            return "django.core.mail.backends.smtp.EmailBackend"

        if self.DEPLOY:
            return "django.core.mail.backends.dummy.EmailBackend"

        return "django.core.mail.backends.console.EmailBackend"

    @cached_property
    def totp_fernet_keys(self) -> tuple[bytes, ...]:
        if self.TOTP_ENCRYPTION_KEYS:
            return tuple(
                key.get_secret_value().encode() for key in self.TOTP_ENCRYPTION_KEYS
            )

        return (derive_fernet_key(self.SECRET_KEY.get_secret_value()),)

    @cached_property
    def cors_allowed_origins(self) -> tuple[str, ...]:
        if self.CORS_ALLOWED_ORIGINS:
            return self.CORS_ALLOWED_ORIGINS

        return LEGACY_DEPLOY_ORIGINS if self.DEPLOY else DEV_ORIGINS

    @cached_property
    def csrf_trusted_origins(self) -> tuple[str, ...]:
        return self.CSRF_TRUSTED_ORIGINS or self.cors_allowed_origins

    @cached_property
    def cookie_samesite(self) -> Literal["Lax", "None"]:
        return "Lax" if self.DEBUG and not self.DEPLOY else "None"

    @cached_property
    def cookie_secure(self) -> bool:
        return not self.DEBUG or self.DEPLOY

    @cached_property
    def csrf_cookie_name(self) -> str:
        return "csrftoken"

    @cached_property
    def csrf_header(self) -> str:
        return f"x-{self.csrf_cookie_name}"

    @cached_property
    def pg_database(self) -> dict:
        return {
            "ATOMIC_REQUESTS": False,
            "CONN_HEALTH_CHECKS": True,
            "ENGINE": "django.db.backends.postgresql",
            "HOST": unquote(
                errors="strict",
                string=self.pg_host["host"] or "",
            ),
            "NAME": unquote(
                errors="strict",
                string=(self.DATABASE_URL.path or "").removeprefix("/"),
            ),
            "PASSWORD": unquote(
                errors="strict",
                string=self.pg_host["password"] or "",
            ),
            "PORT": self.pg_host["port"] or 5432,
            "OPTIONS": {
                "client_encoding": "utf-8",
                "isolation_level": IsolationLevel.READ_COMMITTED,
                "pool": True,
            },
            "USER": unquote(
                errors="strict",
                string=self.pg_host["username"] or "",
            ),
        }

    @cached_property
    def pg_host(self) -> MultiHostHost:
        return self.DATABASE_URL.hosts()[0]

    @cached_property
    def redis_cache(self) -> dict:
        cache: dict = {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": unquote(
                errors="strict",
                string=(
                    f"{self.REDIS_URL.scheme}://"
                    f"{self.REDIS_URL.host}:{self.REDIS_URL.port or 6379}"
                ),
            ),
        }

        password = self.REDIS_SECRET_KEY.get_secret_value()

        if password:
            cache["OPTIONS"] = {
                "password": unquote(errors="strict", string=password),
                "username": unquote(
                    errors="strict",
                    string=self.REDIS_URL.username or "default",
                ),
            }

        return cache


########################################################################################

CONFIG: Final[ApiConfig] = ApiConfig()
