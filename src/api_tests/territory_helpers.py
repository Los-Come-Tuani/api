from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import Group
from django.utils.timezone import now
from dmr.test import DMRClient

from api_catalogs.models import BusinessType, CulturalPillar
from api_organizations.models import Business
from api_roles.services import grant_role_sync
from api_territory.models import (
    Circuit,
    CircuitStatus,
    CircuitStop,
    City,
    Municipality,
    PointOfInterest,
)
from api_tests.helpers import bearer, body, credentials, web_login

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

    from api_auth.models import ApiUser

########################################################################################

PLACE_PHOTO: Final[str] = "place-photo/catedral.jpg"
CIRCUIT_PHOTO: Final[str] = "circuit-photo/portada.jpg"

########################################################################################


def city(code: str = "leon") -> City:
    return City.objects.get(code=code)


def make_point(
    code: str = "leon",
    name: str = "Catedral de León",
    **extra: object,
) -> PointOfInterest:
    found: City = city(code)

    return PointOfInterest.objects.create(
        city=found,
        latitude=found.latitude,
        longitude=found.longitude,
        name=name,
        pillar=CulturalPillar.objects.get(code="historia"),
        **extra,
    )


def verified_municipality(code: str = "leon") -> Municipality:
    return Municipality.objects.create(
        city=city(code),
        contact_email=f"alcaldia.{code}@example.com",
        document_key="legal-document/acta.pdf",
        name=f"Alcaldía de {city(code).name}",
        phone="2311-2222",
        verified_at=now(),
    )


def verified_business(
    code: str = "leon",
    *,
    name: str = "El Sacuanjoche",
    ruc: str = "J0310000000001",
    verified: bool = True,
) -> Business:
    found: City = city(code)
    business = Business.objects.create(
        address="Frente a la catedral",
        business_type=BusinessType.objects.get(code="restaurante"),
        city=found,
        latitude=Decimal("12.437900"),
        longitude=Decimal("-86.878000"),
        name=name,
        phone="2311-0000",
        ruc=ruc,
    )
    if verified:
        Business.objects.filter(pk=business.pk).update(verified_at=now())
        business.refresh_from_db()

    return business


def operator(
    user: ApiUser,
    organization: Business | Municipality,
    role: str,
) -> ApiUser:
    grant_role_sync(
        granted_by=user,
        role=Group.objects.get(name=role),
        scope_object=organization,
        user=user,
    )

    return user


def signed_in(user: ApiUser) -> DMRClient:
    client = DMRClient()
    web_login(client, user)

    return client


# Como la app: el token de acceso va en la cabecera de cada petición.
def mobile_headers(user: ApiUser) -> dict[str, str]:
    response = DMRClient().post("/auth/mobile/login/", credentials(user))

    assert response.status_code == HTTPStatus.OK, response.content

    return bearer(body(response)["access"])


def make_circuit(
    points: Sequence[PointOfInterest],
    *,
    kind: str = "private",
    municipality: Municipality | None = None,
    status: str = "publicado",
    title: str = "León colonial a pie",
) -> Circuit:
    circuit = Circuit.objects.create(
        booking_mode="group" if kind == "creative" else "private",
        bonus_badges=3 if kind == "creative" else 0,
        category="city",
        city=points[0].city,
        description="Un recorrido por las iglesias y los murales del centro de León.",
        difficulty="easy",
        kind=kind,
        meeting_latitude=points[0].latitude,
        meeting_longitude=points[0].longitude,
        meeting_point="Parque Central",
        municipality=municipality,
        published_at=now() if status == "publicado" else None,
        short_title="León colonial",
        status=CircuitStatus.objects.get(code=status),
        subtitle="Iglesias y murales",
        title=title,
        travel_mode="walking",
    )
    CircuitStop.objects.bulk_create(
        CircuitStop(circuit=circuit, order=order, point=point)
        for order, point in enumerate(points)
    )

    return circuit


def circuit_body(points: Sequence[PointOfInterest], **override: object) -> dict:
    first: Any = points[0]

    return {
        "category": "city",
        "city_id": str(first.city_id),
        "description": (
            "Un recorrido a pie por las iglesias coloniales, los murales y la "
            "comida del centro histórico."
        ),
        "difficulty": "easy",
        "images": [CIRCUIT_PHOTO],
        "kind": "private",
        "meeting_latitude": float(first.latitude),
        "meeting_longitude": float(first.longitude),
        "meeting_point": "Parque Central",
        "short_title": "León colonial",
        "start_times": ["08:30", "14:00"],
        "stops": [{"point_id": str(point.pk)} for point in points],
        "subtitle": "Iglesias y murales",
        "title": "León colonial a pie",
        **override,
    }
