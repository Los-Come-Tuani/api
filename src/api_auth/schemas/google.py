from typing import Annotated

from pydantic import StringConstraints

from api_core.schemas.base import DTO

from .account import BirthDate, Nationality

########################################################################################

type GoogleToken = Annotated[str, StringConstraints(max_length=4096, min_length=20)]


class GooglePost(DTO):
    # Uno de los dos. El token de identidad (JWT) que entrega el SDK de Google, o, solo
    # en el portal, el token de acceso del selector de cuentas de Google
    # (`prompt=select_account`), que siempre deja elegir otra cuenta.
    id_token: GoogleToken | None = None
    access_token: GoogleToken | None = None

    # Solo hacen falta la primera vez, para crear la cuenta: Google no los entrega y el
    # registro exige mayoría de edad y nacionalidad (RF-S-05). Si faltan, la respuesta
    # es 400 con estos dos campos en `field_errors`; la app los pide y reintenta con el
    # mismo token.
    birth_date: BirthDate | None = None
    nationality: Nationality | None = None
