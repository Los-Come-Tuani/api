from io import StringIO
from typing import TYPE_CHECKING

import pytest

from cryptography.fernet import Fernet
from django.core.management import call_command
from django.utils.timezone import now
from pydantic import SecretStr, ValidationError

from api_auth.models import ApiUserTotpDevice
from api_auth.services import crypto
from api_core import config as config_module
from api_core.config import derive_fernet_key
from api_tests.helpers import BASE_CONFIG, build_config, build_deployed_config

if TYPE_CHECKING:
    from api_auth.models import ApiUser

########################################################################################


def use_keys(monkeypatch: pytest.MonkeyPatch, *keys: bytes) -> None:
    # `totp_fernet_keys` es un `cached_property` del modelo congelado `ApiConfig`
    monkeypatch.setattr(
        type(config_module.CONFIG),
        "totp_fernet_keys",
        property(lambda _: keys),
    )


########################################################################################


def test_roundtrip_returns_the_original_secret() -> None:
    token = crypto.encrypt_secret("JBSWY3DPEHPK3PXP")

    assert token != "JBSWY3DPEHPK3PXP"
    assert crypto.decrypt_secret(token) == "JBSWY3DPEHPK3PXP"


def test_two_encryptions_of_the_same_secret_differ() -> None:
    first = crypto.encrypt_secret("JBSWY3DPEHPK3PXP")
    second = crypto.encrypt_secret("JBSWY3DPEHPK3PXP")

    assert first != second


def test_the_token_fits_in_the_column() -> None:
    assert len(crypto.encrypt_secret("A" * 64)) <= 255


def test_decrypting_with_the_wrong_key_is_a_server_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = crypto.encrypt_secret("JBSWY3DPEHPK3PXP")

    use_keys(monkeypatch, Fernet.generate_key())

    with pytest.raises(RuntimeError, match="TOTP_ENCRYPTION_KEYS"):
        crypto.decrypt_secret(token)


def test_old_keys_still_decrypt_and_rotation_moves_to_the_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old, new = Fernet.generate_key(), Fernet.generate_key()

    use_keys(monkeypatch, old)
    token = crypto.encrypt_secret("JBSWY3DPEHPK3PXP")

    # la llave nueva va primero y la vieja se conserva para poder leer lo anterior
    use_keys(monkeypatch, new, old)
    assert crypto.decrypt_secret(token) == "JBSWY3DPEHPK3PXP"
    assert not crypto.uses_primary_key(token)

    rotated = crypto.rotate_secret(token)
    assert crypto.uses_primary_key(rotated)

    # ya se puede retirar la llave vieja
    use_keys(monkeypatch, new)
    assert crypto.decrypt_secret(rotated) == "JBSWY3DPEHPK3PXP"


@pytest.mark.django_db
def test_rotatetotpkeys_reencrypts_a_confirmed_device(
    monkeypatch: pytest.MonkeyPatch,
    user: ApiUser,
) -> None:
    old, new = Fernet.generate_key(), Fernet.generate_key()

    use_keys(monkeypatch, old)
    device = ApiUserTotpDevice.objects.create(
        api_user=user,
        confirmed_at=now(),
        secret=crypto.encrypt_secret("JBSWY3DPEHPK3PXP"),
    )

    use_keys(monkeypatch, new, old)
    out = StringIO()
    call_command("rotatetotpkeys", stdout=out)

    device.refresh_from_db()
    assert "1 secretos" in out.getvalue()
    assert crypto.uses_primary_key(device.secret)
    assert crypto.decrypt_secret(device.secret) == "JBSWY3DPEHPK3PXP"

    # una segunda corrida no encuentra nada que rotar
    again = StringIO()
    call_command("rotatetotpkeys", stdout=again)
    assert "0 secretos" in again.getvalue()


########################################################################################


def test_the_development_key_is_derived_from_secret_key() -> None:
    key = derive_fernet_key("s" * 64)

    Fernet(key)  # es una llave Fernet válida

    assert key == derive_fernet_key("s" * 64)
    assert key != derive_fernet_key("t" * 64)


def test_without_explicit_keys_the_config_derives_one_from_secret_key() -> None:
    config = build_config()

    assert config.totp_fernet_keys == (derive_fernet_key("s" * 64),)


def test_explicit_keys_are_used_in_order() -> None:
    first, second = Fernet.generate_key().decode(), Fernet.generate_key().decode()

    config = build_config(TOTP_ENCRYPTION_KEYS=f"{first}, {second}")

    assert config.totp_fernet_keys == (first.encode(), second.encode())
    assert (SecretStr(first), SecretStr(second)) == config.TOTP_ENCRYPTION_KEYS


def test_deploy_requires_explicit_encryption_keys() -> None:
    with pytest.raises(ValidationError, match="TOTP_ENCRYPTION_KEYS"):
        build_deployed_config(TOTP_ENCRYPTION_KEYS="")


@pytest.mark.parametrize("bad", ["not-a-fernet-key", "abc"])
def test_malformed_encryption_keys_are_rejected(bad: str) -> None:
    with pytest.raises(ValidationError, match="Fernet"):
        build_config(TOTP_ENCRYPTION_KEYS=bad)


def test_a_config_error_never_prints_secrets() -> None:
    with pytest.raises(ValidationError) as caught:
        build_config(TOTP_ENCRYPTION_KEYS="not-a-fernet-key")

    message = str(caught.value)

    for secret in ("not-a-fernet-key", BASE_CONFIG["JWT_SECRET_KEY"], "user:pass"):
        assert secret not in message
    assert BASE_CONFIG["SECRET_KEY"] not in message
