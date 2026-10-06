from datetime import time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from api_core.schemas.base import DTO
from api_organizations.schemas.application import ApplicationGet

########################################################################################
# Lo que quien se postuló mandó, con la forma de lo que manda al corregirlo: el
# cliente llena el formulario de corrección con esto y no se vuelve a escribir todo.


# Un archivo ya subido: su clave (para volver a mandarlo sin subirlo de nuevo) y una URL
# de lectura que vence en minutos; nula si el almacenamiento no está configurado.
class SubmittedFileGet(DTO):
    key: str
    url: str | None


class SubmittedHoursGet(DTO):
    # 0 es domingo, 6 es sábado
    weekday: int
    closed: bool
    opens: time | None
    closes: time | None


class SubmittedDishGet(DTO):
    name: str
    description: str
    reference_price: float
    # el código ISO de la moneda
    currency: str
    photo: SubmittedFileGet | None


class SubmittedBusinessGet(DTO):
    kind: Literal["business"]
    city_id: UUID
    business_type_id: UUID
    ruc: str
    name: str
    address: str
    phone: str
    alternate_phone: str
    latitude: float
    longitude: float
    hours: list[SubmittedHoursGet]
    # el platillo vigente
    signature_dish: SubmittedDishGet | None


class SubmittedInstitutionGet(DTO):
    kind: Literal["institution"]
    city_id: UUID
    institution_type_id: UUID
    name: str
    contact_email: str
    phone: str
    # el documento que acredita su existencia legal
    document: SubmittedFileGet


class SubmittedMunicipalityGet(DTO):
    kind: Literal["municipality"]
    city_id: UUID
    name: str
    contact_email: str
    phone: str
    # el documento que acredita la representación de quien solicita
    document: SubmittedFileGet


type Submitted = Annotated[
    SubmittedBusinessGet | SubmittedInstitutionGet | SubmittedMunicipalityGet,
    Field(discriminator="kind"),
]

########################################################################################


class MineApplicationGet(ApplicationGet):
    """La solicitud de quien entró, con los datos que mandó."""

    submitted: Submitted
