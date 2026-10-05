import logging

from os import environ
from typing import TYPE_CHECKING, Any

import pytest
import schemathesis as st

from django.core.signals import request_finished, request_started
from django.core.wsgi import get_wsgi_application
from django.db import close_old_connections
from dmr.test import DMRClient
from hypothesis import (
    HealthCheck,
    settings as h_settings,
)
from requests.structures import CaseInsensitiveDict
from schemathesis.checks import not_a_server_error
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    status_code_conformance,
)

from api_auth.models import ApiUser
from api_tests.helpers import PASSWORD, body

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Final

    from schemathesis.specs.openapi.schemas import OpenApiSchema

########################################################################################

ADMIN: Final[str] = "contract-admin@example.com"

# más ejemplos en CI que en local; son pruebas generativas, no un benchmark
MAX_EXAMPLES: Final[int] = 15 if environ.get("CI") else 10

# - no se revisa el esquema del cuerpo (`response_schema_conformance`): las respuestas
#   `204` salen con `Content-Type: application/json` y cuerpo vacío, algo que el
#   framework hace de forma uniforme y que ese chequeo marca como JSON inválido.
CHECKS: Final = [
    not_a_server_error,
    status_code_conformance,
    content_type_conformance,
]

# lo llena el fixture; el proveedor de autenticación no puede tocar la base de datos
SESSION: Final[dict[str, str]] = {}

########################################################################################


@pytest.fixture(autouse=True)
def _quiet_logs() -> Iterator[None]:
    # cada 4xx que generan las pruebas deja una línea de log; con cientos es ruido
    logging.disable(logging.CRITICAL)

    yield

    logging.disable(logging.NOTSET)


@pytest.fixture
def api_schema(db: None) -> Iterator[OpenApiSchema]:  # ruff: ignore[unused-function-argument]
    ApiUser.objects.create_superuser(email=ADMIN, password=PASSWORD)

    # el token se pide antes de que arranque schemathesis: cada petición del cliente de
    # pruebas de Django vuelve a conectar las señales que se desconectan abajo
    login = DMRClient().post(
        "/auth/mobile/login/",
        {"email": ADMIN, "password": PASSWORD},
    )
    SESSION["access"] = body(login)["access"]

    # el handler WSGI real cierra las conexiones "viejas" en cada petición, y con eso
    # rompe la transacción que envuelve la prueba. El cliente de pruebas de Django
    # desconecta estas señales por la misma razón; aquí se hace igual porque
    # schemathesis llama directo a la aplicación WSGI.
    request_started.disconnect(close_old_connections)
    request_finished.disconnect(close_old_connections)

    yield st.openapi.from_wsgi("/openapi/", get_wsgi_application())

    request_started.connect(close_old_connections)
    request_finished.connect(close_old_connections)
    SESSION.clear()


schema = st.pytest.from_fixture("api_schema")


@st.auth()
class SuperuserBearer:
    # con una sesión de superusuario las pruebas recorren también las rutas protegidas
    # y no se quedan en el 401

    # la firma la impone schemathesis, aunque aquí no se use todo
    def get(self, case: st.Case, ctx: st.AuthContext) -> str:  # ruff: ignore[no-self-use, unused-method-argument]
        return SESSION["access"]

    def set(self, case: st.Case, data: str, ctx: st.AuthContext) -> None:  # ruff: ignore[no-self-use, unused-method-argument]
        case.headers = case.headers or CaseInsensitiveDict()
        case.headers["Authorization"] = f"Bearer {data}"


@schema.parametrize()
@h_settings(
    deadline=None,
    max_examples=MAX_EXAMPLES,
    # - `filter_too_much`: las rutas que leen cookies (`/auth/web/*`) generan valores
    #   de cookie que casi siempre se descartan por inválidos; es una limitación del
    #   generador, no un fallo del API.
    suppress_health_check=[
        HealthCheck.filter_too_much,
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
    ],
)
def test_api_matches_its_openapi_schema(case: st.Case[Any]) -> None:
    # werkzeug no pone `REMOTE_ADDR`, y el throttling necesita la dirección del cliente
    case.call_and_validate(
        checks=CHECKS,  # ty: ignore[invalid-argument-type]
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
