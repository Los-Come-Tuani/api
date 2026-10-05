from typing import TYPE_CHECKING

import pytest

from pydantic import ValidationError

from api_core.config import (
    DEV_ALLOWED_HOSTS,
    DEV_ORIGINS,
    LEGACY_DEPLOY_HOSTS,
    LEGACY_DEPLOY_ORIGINS,
    RAILWAY_HEALTHCHECK_HOST,
)
from api_tests.helpers import build_config, build_deployed_config

if TYPE_CHECKING:
    from collections.abc import Callable

########################################################################################


def test_dev_defaults_cover_portal_and_android_emulator() -> None:
    config = build_config()

    assert config.allowed_hosts == DEV_ALLOWED_HOSTS
    assert "10.0.2.2" in config.allowed_hosts

    assert config.cors_allowed_origins == DEV_ORIGINS
    assert "http://localhost:5173" in config.cors_allowed_origins

    # CSRF confía en los mismos orígenes que CORS mientras no se defina aparte
    assert config.csrf_trusted_origins == config.cors_allowed_origins


def test_deploy_without_overrides_keeps_legacy_values() -> None:
    config = build_deployed_config()

    assert config.allowed_hosts == LEGACY_DEPLOY_HOSTS
    assert config.cors_allowed_origins == LEGACY_DEPLOY_ORIGINS
    assert "10.0.2.2" not in config.allowed_hosts


def test_overrides_replace_defaults_and_keep_the_railway_healthcheck() -> None:
    config = build_deployed_config(
        ALLOWED_HOSTS="api.example.com, .example.org",
        CORS_ALLOWED_ORIGINS="https://portal.example.com",
    )

    assert config.allowed_hosts == (
        "api.example.com",
        ".example.org",
        RAILWAY_HEALTHCHECK_HOST,
    )
    assert config.cors_allowed_origins == ("https://portal.example.com",)
    assert config.csrf_trusted_origins == ("https://portal.example.com",)


def test_csrf_origins_can_be_defined_separately() -> None:
    config = build_config(
        CORS_ALLOWED_ORIGINS="https://portal.example.com",
        CSRF_TRUSTED_ORIGINS="https://admin.example.com",
    )

    assert config.csrf_trusted_origins == ("https://admin.example.com",)


def test_lists_are_read_from_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com,10.0.0.5")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")

    config = build_config()

    assert config.allowed_hosts == ("api.example.com", "10.0.0.5")
    # vacío = valores de desarrollo
    assert config.cors_allowed_origins == DEV_ORIGINS


@pytest.mark.parametrize(
    "overrides",
    [
        {"CORS_ALLOWED_ORIGINS": "http://localhost:5173/"},
        {"CORS_ALLOWED_ORIGINS": "portal.example.com"},
        {"CSRF_TRUSTED_ORIGINS": "https://portal.example.com/app"},
        {"ALLOWED_HOSTS": "https://api.example.com"},
        {"ALLOWED_HOSTS": "api.example.com/health"},
    ],
)
def test_malformed_hosts_and_origins_are_rejected(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        build_config(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        # en producción: `http` solo para localhost y nunca `*`
        {"CORS_ALLOWED_ORIGINS": "http://portal.example.com"},
        {"ALLOWED_HOSTS": "*"},
    ],
)
def test_unsafe_hosts_and_origins_are_rejected_when_deployed(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        build_deployed_config(**overrides)


def test_http_localhost_origin_is_still_accepted_when_deployed() -> None:
    config = build_deployed_config(CORS_ALLOWED_ORIGINS="http://localhost:5173")

    assert config.cors_allowed_origins == ("http://localhost:5173",)


########################################################################################


def test_email_goes_to_the_console_in_development_without_a_server() -> None:
    assert build_config().email_backend == (
        "django.core.mail.backends.console.EmailBackend"
    )


def test_email_is_discarded_when_deployed_without_a_server() -> None:
    # nunca por consola con `DEPLOY=True`: los códigos quedarían en los logs
    assert build_deployed_config().email_backend == (
        "django.core.mail.backends.dummy.EmailBackend"
    )


@pytest.mark.parametrize("build", [build_config, build_deployed_config])
def test_email_uses_smtp_once_a_server_is_configured(build: Callable) -> None:
    assert build(EMAIL_HOST="smtp.example.com").email_backend == (
        "django.core.mail.backends.smtp.EmailBackend"
    )
