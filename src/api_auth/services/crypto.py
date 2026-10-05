from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.views.decorators.debug import sensitive_variables

from api_core.config import CONFIG

if TYPE_CHECKING:
    from typing import Final

########################################################################################

UNREADABLE_DETAIL: Final[str] = (
    "No se pudo descifrar un secreto guardado; revise `TOTP_ENCRYPTION_KEYS`."
)

########################################################################################


def build_cipher() -> MultiFernet:
    # se arma en cada uso (es barato) para que las pruebas puedan cambiar la llave;
    # `MultiFernet` cifra con la primera y descifra con cualquiera de la lista
    return MultiFernet([Fernet(key) for key in CONFIG.totp_fernet_keys])


@sensitive_variables()
def encrypt_secret(plaintext: str) -> str:
    return build_cipher().encrypt(plaintext.encode()).decode()


@sensitive_variables()
def decrypt_secret(token: str) -> str:
    try:
        return build_cipher().decrypt(token.encode()).decode()
    except InvalidToken as e:
        # llave equivocada o dato corrupto: es un fallo del servidor, no del usuario
        raise RuntimeError(UNREADABLE_DETAIL) from e


@sensitive_variables()
def rotate_secret(token: str) -> str:
    # vuelve a cifrar con la llave primaria; sirve para retirar llaves viejas
    try:
        return build_cipher().rotate(token.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError(UNREADABLE_DETAIL) from e


def uses_primary_key(token: str) -> bool:
    try:
        Fernet(CONFIG.totp_fernet_keys[0]).decrypt(token.encode())
    except InvalidToken:
        return False

    return True
