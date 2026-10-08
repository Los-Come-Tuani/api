from http import HTTPMethod, HTTPStatus
from typing import TYPE_CHECKING

from dmr.settings import Settings
from pghistory import DeleteEvent, InsertEvent, UpdateEvent
from psycopg.errors import DeadlockDetected, SerializationFailure

from api_core.config import CONFIG
from api_exceptions.handler import exc_handler
from api_exceptions.specs import ERROR_SPECS
from api_utils.env import OPENAPI, ROOT

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path
    from typing import Final

    from pghistory import Tracker
    from psycopg import OperationalError

########################################################################################

CACHES: Final[dict[str, dict]] = {"default": CONFIG.redis_cache}
DATABASES: Final[dict[str, dict]] = {"default": CONFIG.pg_database}
DEBUG: Final[bool] = CONFIG.DEBUG
SECRET_KEY: Final[str] = CONFIG.SECRET_KEY.get_secret_value()
USE_X_FORWARDED_HOST: Final[bool] = CONFIG.DEPLOY

########################################################################################

BASE_DIR: Final[Path] = ROOT / "src"

# outside `src` so the hot reload (which watches `src`) does not restart
# the worker on every temporary write made by the `Storage` health check.
MEDIA_ROOT: Final[Path] = ROOT / "media"

########################################################################################

ASGI_APPLICATION: Final[str] = "api_core.asgi.application"
WSGI_APPLICATION: Final[str] = "api_core.wsgi.application"

########################################################################################

AUTHENTICATION_BACKENDS: Final[Sequence[str]] = ("api_auth.backends.ApiUserBackend",)
AUTH_USER_MODEL: Final[str] = "apiauth.ApiUser"

########################################################################################

DEFAULT_FROM_EMAIL: Final[str] = CONFIG.DEFAULT_FROM_EMAIL
EMAIL_BACKEND: Final[str] = CONFIG.email_backend
EMAIL_HOST: Final[str] = CONFIG.EMAIL_HOST
EMAIL_HOST_PASSWORD: Final[str] = CONFIG.EMAIL_HOST_PASSWORD.get_secret_value()
EMAIL_HOST_USER: Final[str] = CONFIG.EMAIL_HOST_USER
EMAIL_PORT: Final[int] = CONFIG.EMAIL_PORT
EMAIL_TIMEOUT: Final[int] = 10
EMAIL_USE_TLS: Final[bool] = CONFIG.EMAIL_USE_TLS

LANGUAGE_CODE: Final[str] = "es-ni"
ROOT_URLCONF: Final[str] = "api_core.urls"
TIME_ZONE: Final[str] = "America/Managua"
USE_I18N: Final[bool] = True
USE_TZ: Final[bool] = True

########################################################################################

# hosts y orígenes salen de las variables `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y
# `CSRF_TRUSTED_ORIGINS` (ver `api_core.config`); el repositorio no fija dominios.
ALLOWED_HOSTS: Final[Sequence[str]] = CONFIG.allowed_hosts

CORS_ALLOW_ALL_ORIGINS: Final[bool] = False
CORS_ALLOW_CREDENTIALS: Final[bool] = True
CORS_ALLOWED_ORIGINS: Final[Sequence[str]] = CONFIG.cors_allowed_origins

CORS_EXPOSE_HEADERS: Final[Sequence[str]] = (CONFIG.csrf_header,)

CSRF_COOKIE_HTTPONLY: Final[bool] = True
CSRF_COOKIE_NAME: Final[str] = CONFIG.csrf_cookie_name
CSRF_COOKIE_SAMESITE: Final[str] = CONFIG.cookie_samesite
CSRF_COOKIE_SECURE: Final[bool] = CONFIG.cookie_secure
CSRF_TRUSTED_ORIGINS: Final[Sequence[str]] = CONFIG.csrf_trusted_origins

FILE_UPLOAD_MAX_MEMORY_SIZE: Final[int] = 2_621_440
DATA_UPLOAD_MAX_MEMORY_SIZE: Final[int] = 2_621_440
DATA_UPLOAD_MAX_NUMBER_FIELDS: Final[int] = 100
DATA_UPLOAD_MAX_NUMBER_FILES: Final[int] = 100

SECURE_HSTS_INCLUDE_SUBDOMAINS: Final[bool] = not DEBUG
SECURE_HSTS_PRELOAD: Final[bool] = not DEBUG
SECURE_HSTS_SECONDS: Final[int] = 0 if DEBUG else 31_536_000

SECURE_PROXY_SSL_HEADER: Final[Sequence[str] | None] = (
    None if DEBUG else ("HTTP_X_FORWARDED_PROTO", "https")
)

# `not DEBUG` when not on railway
SECURE_SSL_REDIRECT: Final[bool] = False

########################################################################################

INSTALLED_APPS: Final[Sequence[str]] = (
    "corsheaders",
    "health_check",
    "django.contrib.postgres",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "dmr.security.jwt.blocklist",
    "pgtrigger",
    "pghistory",
    "api_core",
    "api_auth",
    "api_catalogs",
    "api_territory",
    "api_organizations",
    "api_moderation",
    "api_roles",
    "api_profiles",
    "api_itineraries",
    "api_agenda",
    "api_rewards",
)

MIDDLEWARE: Final[Sequence[str]] = (
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "api_middlewares.cookies.cookie_partitioner",
    "django.middleware.csrf.CsrfViewMiddleware",
    "api_middlewares.history.contextful_history",
)

########################################################################################

AUTH_PASSWORD_VALIDATORS: Final[Sequence[dict[str, str]]] = (
    {
        "NAME": "api_auth.validators.ComplexityPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
)

SILENCED_SYSTEM_CHECKS: Final[Sequence[str]] = (
    # - ignore 30-character limit for constraints/indices
    #   - ok because postgres' limit is 63
    "models.E034",
    # - ignore missing `ClickjackingMiddleware`
    #   - ok because API does not serve HTML
    "security.W002",
    # - ignore `SECURE_SSL_REDIRECT=False`
    #   - ok when on railway
    "security.W008",
)

########################################################################################

DMR_SETTINGS: Final[dict] = {
    Settings.exclude_semantic_responses: frozenset({HTTPStatus.UNPROCESSABLE_ENTITY}),
    Settings.global_error_handler: exc_handler,
    Settings.openapi_config: OPENAPI,
    Settings.responses: ERROR_SPECS,
    Settings.validate_events: DEBUG,
    Settings.validate_negotiation: DEBUG,
    Settings.validate_responses: DEBUG,
}

PGHISTORY_APPEND_ONLY: Final[bool] = True
PGHISTORY_BASE_MODEL: Final[str] = "api_core.models.event.ApiEvent"
PGHISTORY_DEFAULT_TRACKERS: Sequence[Tracker] = (
    DeleteEvent(trigger_name="trg_log_delete"),
    InsertEvent(trigger_name="trg_log_insert"),
    UpdateEvent(trigger_name="trg_log_update"),
)

PGHISTORY_MIDDLEWARE_METHODS: Final[Sequence[str]] = (
    HTTPMethod.POST,
    HTTPMethod.PUT,
    HTTPMethod.PATCH,
    HTTPMethod.DELETE,
)

PGTRANSACTION_RETRY: Final[int] = 0
PGTRANSACTION_RETRY_EXCEPTIONS: Final[Sequence[type[OperationalError]]] = (
    DeadlockDetected,
    SerializationFailure,
)
