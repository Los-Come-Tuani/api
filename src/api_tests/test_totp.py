from typing import TYPE_CHECKING
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from api_auth.services import totp
from api_core.config import CONFIG

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# RFC 6238, apéndice B (SHA-1): el secreto es la cadena ASCII "12345678901234567890".
RFC_SECRET: Final[str] = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"

# (segundos Unix, código de 8 dígitos publicado en el RFC)
RFC_VECTORS: Final[tuple[tuple[int, str], ...]] = (
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
)

########################################################################################


@pytest.mark.parametrize(("seconds", "published"), RFC_VECTORS)
def test_build_totp_matches_the_rfc_6238_vectors(seconds: int, published: str) -> None:
    # el servidor genera 6 dígitos: son los últimos 6 del código de 8 del RFC
    expected = published[-CONFIG.TOTP_DIGITS :]

    assert totp.build_totp(RFC_SECRET, seconds // CONFIG.TOTP_PERIOD) == expected


def test_match_totp_accepts_the_current_window_and_its_neighbours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(totp, "current_step", lambda: 1000)

    assert totp.match_totp(totp.build_totp(RFC_SECRET, 1000), RFC_SECRET) == 1000
    assert totp.match_totp(totp.build_totp(RFC_SECRET, 999), RFC_SECRET) == 999
    assert totp.match_totp(totp.build_totp(RFC_SECRET, 1001), RFC_SECRET) == 1001


def test_match_totp_rejects_codes_outside_the_tolerance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(totp, "current_step", lambda: 1000)

    assert totp.match_totp(totp.build_totp(RFC_SECRET, 1005), RFC_SECRET) is None
    assert totp.match_totp(totp.build_totp(RFC_SECRET, 990), RFC_SECRET) is None


def test_match_totp_refuses_to_replay_a_used_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(totp, "current_step", lambda: 1000)

    code = totp.build_totp(RFC_SECRET, 1000)

    assert totp.match_totp(code, RFC_SECRET, after=999) == 1000
    assert totp.match_totp(code, RFC_SECRET, after=1000) is None


@pytest.mark.parametrize("code", ["", "12345", "1234567", "abcdef", "12 456"])
def test_match_totp_rejects_malformed_codes(code: str) -> None:
    assert totp.match_totp(code, RFC_SECRET) is None


def test_provisioning_uri_carries_the_issuer_and_the_secret() -> None:
    uri = totp.build_provisioning_uri(RFC_SECRET, "ana@example.com")
    parts = urlsplit(uri)
    params = parse_qs(parts.query)

    assert parts.scheme == "otpauth"
    assert parts.netloc == "totp"
    assert unquote(parts.path) == f"/{CONFIG.TOTP_ISSUER}:ana@example.com"
    assert params["secret"] == [RFC_SECRET]
    assert params["issuer"] == [CONFIG.TOTP_ISSUER]
    assert params["digits"] == [str(CONFIG.TOTP_DIGITS)]


def test_recovery_codes_are_unique_and_hash_ignores_formatting() -> None:
    codes = totp.build_recovery_codes()

    assert len(codes) == len(set(codes)) == CONFIG.TOTP_RECOVERY_CODES

    code = codes[0]
    assert totp.hash_recovery_code(code) == totp.hash_recovery_code(code.lower())
    assert totp.hash_recovery_code(code) == totp.hash_recovery_code(
        code.replace("-", " "),
    )
    assert totp.hash_recovery_code(code) != totp.hash_recovery_code(codes[1])


def test_build_secret_is_valid_base32_and_not_repeated() -> None:
    first, second = totp.build_secret(), totp.build_secret()

    assert first != second
    assert len(totp.decode_secret(first)) == totp.SECRET_BYTES
