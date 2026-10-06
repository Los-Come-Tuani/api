from api_core.schemas.base import DTO

########################################################################################


# Una opción de una lista cerrada: lo que el formulario muestra y lo que manda.
class OptionGet(DTO):
    id: str
    code: str
    label: str


class CityGet(DTO):
    id: str
    code: str
    name: str
    # ya se incorporó a la plataforma
    active: bool
