from api_core.schemas.base import DTO

########################################################################################


# Una opción de una lista cerrada: lo que el formulario muestra y lo que manda.
class OptionGet(DTO):
    id: str
    code: str
    label: str


# Un documento que se le puede pedir a un guía o traductor.
class CredentialTypeGet(OptionGet):
    # el servicio que acredita (`guia`, `traductor`), o nulo si se le pide a todos
    service: str | None
    requires_expiry: bool
    # se le pide a quien lleva turistas en su vehículo
    requires_vehicle: bool


class CityGet(DTO):
    id: str
    code: str
    name: str
    # el centro de la ciudad, para encuadrar el mapa donde se ubica un lugar
    latitude: float
    longitude: float
    # ya se incorporó a la plataforma
    active: bool
