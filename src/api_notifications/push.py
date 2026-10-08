import json
import logging

from threading import Lock
from time import time
from typing import TYPE_CHECKING, Any, Final
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import jwt

from api_core.config import CONFIG

if TYPE_CHECKING:
    from collections.abc import Mapping

########################################################################################
# Firebase Cloud Messaging, API HTTP v1. La cuenta de servicio firma un JWT que se
# cambia por un token de acceso de una hora; con él se manda un mensaje por teléfono.
########################################################################################

logger = logging.getLogger(__name__)

OAUTH_ENDPOINT: Final[str] = "https://oauth2.googleapis.com/token"
SCOPE: Final[str] = "https://www.googleapis.com/auth/firebase.messaging"
SEND_URL: Final[str] = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"
TIMEOUT: Final[int] = 5
# - se renueva un poco antes de que venza
MARGIN: Final[int] = 300

_cache: dict[str, Any] = {}
_lock = Lock()


def enabled() -> bool:
    return bool(CONFIG.FCM_PROJECT_ID and CONFIG.FCM_SERVICE_ACCOUNT.get_secret_value())


def access_token() -> str:
    with _lock:
        if _cache.get("expires", 0) > time() + MARGIN:
            return str(_cache["token"])

        account: dict[str, str] = json.loads(
            CONFIG.FCM_SERVICE_ACCOUNT.get_secret_value()
        )
        issued = int(time())
        assertion = jwt.encode(
            {
                "aud": OAUTH_ENDPOINT,
                "exp": issued + 3600,
                "iat": issued,
                "iss": account["client_email"],
                "scope": SCOPE,
            },
            account["private_key"],
            algorithm="RS256",
        )
        payload = urlencode({
            "assertion": assertion,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        }).encode()

        request = Request(OAUTH_ENDPOINT, data=payload)

        with urlopen(request, timeout=TIMEOUT) as response:  # ruff: ignore[suspicious-url-open-usage]
            answer: dict[str, Any] = json.loads(response.read())

        _cache["token"] = answer["access_token"]
        _cache["expires"] = issued + int(answer.get("expires_in", 3600))

        return str(_cache["token"])


# Manda un aviso a un teléfono. Devuelve `False` si el token ya no sirve (desinstaló la
# app o venció): quien llama lo borra.
def send(token: str, title: str, body: str, data: Mapping[str, str]) -> bool:
    message = {
        "message": {
            "data": {key: str(value) for key, value in data.items()},
            "notification": {"body": body, "title": title},
            "token": token,
        }
    }
    request = Request(  # ruff: ignore[suspicious-url-open-usage]
        SEND_URL.format(project=CONFIG.FCM_PROJECT_ID),
        data=json.dumps(message).encode(),
        headers={
            "Authorization": f"Bearer {access_token()}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=TIMEOUT):  # ruff: ignore[suspicious-url-open-usage]
            return True
    except HTTPError as error:
        # 404 `UNREGISTERED` o 400 de token inválido: el teléfono ya no recibe
        if error.code in {400, 404}:
            return False

        logger.warning("FCM respondió %s", error.code)
        raise
    except URLError:
        logger.warning("FCM no respondió")
        raise
