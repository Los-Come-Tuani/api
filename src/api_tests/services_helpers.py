from datetime import time, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

from django.contrib.auth.models import Group
from django.utils.timezone import localdate

from api_auth.models import ApiUserGroups
from api_catalogs.models import ServiceType
from api_profiles.models import ProviderProfile, ProviderService, ProviderStatus
from api_services.models import Booking, GuidedDeparture
from api_tests.helpers import body
from api_tests.territory_helpers import city

if TYPE_CHECKING:
    from datetime import date

    from dmr.test import DMRClient

    from api_auth.models import ApiUser
    from api_territory.models import Circuit

########################################################################################


def make_guide(user: ApiUser, *, code: str | None = "leon") -> ProviderProfile:
    provider = ProviderProfile.objects.create(
        city=None if code is None else city(code),
        phone="8888-0000",
        presentation="Guía de León desde hace diez años.",
        status=ProviderStatus.objects.get(code="activo"),
        user=user,
    )
    ProviderService.objects.create(
        provider=provider, service=ServiceType.objects.get(code="guia")
    )
    ApiUserGroups.objects.create(api_user=user, group=Group.objects.get(name="Guía"))

    return provider


def days(offset: int) -> date:
    return localdate() + timedelta(days=offset)


def publish_departure(
    client: DMRClient,
    guide: dict[str, str],
    circuit: Circuit,
    **override: object,
) -> dict:
    response = client.post(
        "/departure/",
        {
            "capacity": 4,
            "circuit_id": str(circuit.pk),
            "date": days(3).isoformat(),
            "start_time": "08:30",
            **override,
        },
        headers=guide,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


def book(
    client: DMRClient,
    headers: dict[str, str],
    departure: dict,
    **party: int,
) -> dict:
    response = client.post(
        "/booking/",
        {"departure_id": departure["id"], **party},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


# Lleva la reserva al día de hoy, la inicia y la termina como el guía.
def deliver(client: DMRClient, guide: dict[str, str], booking: dict) -> dict:
    Booking.objects.filter(pk=booking["id"]).update(
        date=localdate(), start_time=time(0)
    )
    GuidedDeparture.objects.filter(bookings__pk=booking["id"]).update(date=localdate())

    started = client.post(f"/booking/{booking['id']}/start/", {}, headers=guide)
    finished = client.post(f"/booking/{booking['id']}/finish/", {}, headers=guide)

    assert started.status_code == HTTPStatus.OK, started.content
    assert finished.status_code == HTTPStatus.OK, finished.content

    return body(finished)
