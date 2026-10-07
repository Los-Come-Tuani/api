from decimal import Decimal
from typing import TYPE_CHECKING

from django.db.transaction import atomic

from api_territory.models import CircuitStatus, City

if TYPE_CHECKING:
    from typing import Final

########################################################################################

# - las diez Ciudades Creativas de la Red Nacional (`territorio` del modelo de dominio):
#   (código, nombre, latitud, longitud del centro). Ninguna está activa hasta que se
#   incorpora a la plataforma.
CITIES: Final[tuple[tuple[str, str, str, str], ...]] = (
    ("esteli", "Estelí", "13.091700", "-86.354700"),
    ("leon", "León", "12.437900", "-86.878000"),
    ("nagarote", "Nagarote", "12.259500", "-86.566700"),
    ("managua", "Managua", "12.136400", "-86.251400"),
    ("masaya", "Masaya", "11.974400", "-86.094200"),
    ("granada", "Granada", "11.929900", "-85.956000"),
    ("san_juan_de_oriente", "San Juan de Oriente", "11.900000", "-86.066700"),
    ("juigalpa", "Juigalpa", "12.100000", "-85.366700"),
    ("matagalpa", "Matagalpa", "12.916700", "-85.916700"),
    ("bluefields", "Bluefields", "12.013600", "-83.763400"),
)

########################################################################################


# - (código, etiqueta, visible, admite edición, terminal): `estado_circuito`
CIRCUIT_STATES: Final[tuple[tuple[str, str, bool, bool, bool], ...]] = (
    ("borrador", "Borrador", False, True, False),
    ("publicado", "Publicado", True, True, False),
    ("despublicado", "Despublicado", False, True, False),
    ("retirado", "Retirado", False, False, True),
)

########################################################################################


@atomic
def execute() -> None:
    for code, label, is_visible, allows_editing, is_terminal in CIRCUIT_STATES:
        CircuitStatus.objects.update_or_create(
            code=code,
            defaults={
                "allows_editing": allows_editing,
                "is_terminal": is_terminal,
                "is_visible": is_visible,
                "label": label,
            },
        )

    # `get_or_create`: la ciudad que se activa después no se vuelve a apagar al migrar
    for code, name, latitude, longitude in CITIES:
        City.objects.get_or_create(
            code=code,
            defaults={
                "latitude": Decimal(latitude),
                "longitude": Decimal(longitude),
                "name": name,
            },
        )
