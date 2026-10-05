from typing import Annotated

from pydantic import StringConstraints

from api_core.schemas.base import DTO

from .account import BirthDate, Nationality

########################################################################################


class GooglePost(DTO):
    # el token de identidad (JWT) que entrega el SDK de Google
    id_token: Annotated[str, StringConstraints(max_length=4096, min_length=20)]

    # Solo hacen falta la primera vez, para crear la cuenta: Google no los entrega y el
    # registro exige mayoría de edad y nacionalidad (RF-S-05). Si faltan, la respuesta
    # es 400 con estos dos campos en `field_errors`; la app los pide y reintenta con el
    # mismo token.
    birth_date: BirthDate | None = None
    nationality: Nationality | None = None
