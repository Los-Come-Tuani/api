from math import asin, ceil, cos, radians, sin, sqrt
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from api_territory.models import PointOfInterest

########################################################################################
# El traslado estimado entre dos lugares. Es la misma cuenta que hacen el portal
# (`src/lib/itinerary.ts`) y la app (`itinerary_planner.dart`): si una cambia, cambian
# las tres.
########################################################################################

DETOUR_FACTOR: Final[float] = 1.3
WALKING_KMH: Final[float] = 4.5
VEHICLE_KMH: Final[float] = 30
VEHICLE_OVERHEAD_MINUTES: Final[int] = 5
SAME_PLACE_KM: Final[float] = 0.15
WALKABLE_KM: Final[float] = 1
EARTH_RADIUS_KM: Final[float] = 6371

type Coordinates = tuple[float, float]


def coordinates(point: PointOfInterest) -> Coordinates:
    found: Any = point

    return float(found.latitude), float(found.longitude)


def distance_km(origin: Coordinates, target: Coordinates) -> float:
    lat1, lat2 = radians(origin[0]), radians(target[0])
    d_lat = lat2 - lat1
    d_lon = radians(target[1] - origin[1])
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2

    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


# Redondea hacia arriba a múltiplos de 5, con 5 minutos como mínimo.
def round_up(minutes: float) -> int:
    return max(5, ceil(minutes / 5) * 5)


# A pie, o en vehículo cuando se pidió y el tramo pasa de un kilómetro por calle.
def estimated_leg(
    origin: PointOfInterest, target: PointOfInterest, travel_mode: str
) -> int:
    km = distance_km(coordinates(origin), coordinates(target)) * DETOUR_FACTOR

    if km < SAME_PLACE_KM:
        return 0

    if travel_mode == "walking" or km <= WALKABLE_KM:
        return round_up(km / WALKING_KMH * 60)

    return round_up(km / VEHICLE_KMH * 60 + VEHICLE_OVERHEAD_MINUTES)
