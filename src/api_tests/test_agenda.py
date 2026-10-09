from datetime import time, timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.utils.timezone import localdate, now

from api_agenda.models import Event, EventStatus
from api_catalogs.models import EventCategory
from api_tests.helpers import body
from api_tests.territory_helpers import (
    city,
    operator,
    signed_in,
    verified_business,
    verified_institution,
    verified_municipality,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import date

    from dmr.test import DMRClient

    from api_auth.models import ApiUser
    from api_organizations.models import CulturalInstitution

########################################################################################

pytestmark = pytest.mark.django_db

MANAGED = "/cultural-event/"


@pytest.fixture
def institution() -> CulturalInstitution:
    return verified_institution()


@pytest.fixture
def theater(
    make_user: Callable[..., ApiUser],
    institution: CulturalInstitution,
) -> ApiUser:
    return operator(make_user(email="teatro@example.com"), institution, "Institución")


def days(offset: int) -> date:
    return localdate() + timedelta(days=offset)


def event_body(**override: object) -> dict:
    return {
        "category": "musica",
        "city_id": str(city().pk),
        "description": "Concierto de marimba en el patio central.",
        "end_date": days(3).isoformat(),
        "end_time": "22:00",
        "entry_price": 100,
        "latitude": 12.4343,
        "longitude": -86.8780,
        "name": "Noche de marimba",
        "start_date": days(2).isoformat(),
        "start_time": "18:00",
        "venue": "Teatro Municipal",
        **override,
    }


def make_event(
    institution: CulturalInstitution,
    *,
    start: int,
    end: int,
    status: str = "programado",
    **extra: object,
) -> Event:
    return Event.objects.create(
        category=EventCategory.objects.get(code="feria"),
        city=city(),
        end_date=days(end),
        end_time=time(20),
        institution=institution,
        latitude=city().latitude,
        longitude=city().longitude,
        name=extra.pop("name", "Feria"),
        start_date=days(start),
        start_time=time(10),
        status=EventStatus.objects.get(code=status),
        venue="Parque Central",
        **extra,
    )


########################################################################################
# Quién programa


def test_an_institution_schedules_an_event_that_the_app_sees(
    client: DMRClient,
    theater: ApiUser,
) -> None:
    response = signed_in(theater).post(MANAGED, event_body())

    assert response.status_code == HTTPStatus.CREATED, response.content
    created = body(response)
    assert created["status"] == "scheduled"
    assert created["organizer"]["kind"] == "institution"
    assert created["start_time"] == "18:00"

    public = body(client.get("/event/", {"city": "leon"}))
    assert [item["id"] for item in public["results"]] == [created["id"]]


def test_an_event_that_starts_today_is_ongoing(theater: ApiUser) -> None:
    response = signed_in(theater).post(
        MANAGED, event_body(start_date=days(0).isoformat())
    )

    assert body(response)["status"] == "ongoing"


def test_a_municipality_also_schedules_events(
    make_user: Callable[..., ApiUser],
) -> None:
    mayor = operator(
        make_user(email="alcaldia@example.com"),
        verified_municipality(),
        "Alcaldía",
    )

    response = signed_in(mayor).post(MANAGED, event_body())

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["organizer"]["kind"] == "municipality"


def test_a_business_does_not_schedule_events(make_user: Callable[..., ApiUser]) -> None:
    owner = operator(
        make_user(email="negocio@example.com"), verified_business(), "Negocio"
    )

    assert signed_in(owner).post(MANAGED, event_body()).status_code == (
        HTTPStatus.FORBIDDEN
    )


def test_the_team_schedules_a_kplan_special(
    make_member: Callable[..., ApiUser],
) -> None:
    team = signed_in(make_member("equipo@example.com", "content.moderate"))

    response = team.post(MANAGED, event_body(featured=True))

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["organizer"] == {
        "id": None,
        "kind": "kplan",
        "name": "K'Plan",
    }
    assert body(response)["featured"] is True


def test_the_portal_agenda_needs_a_session(client: DMRClient) -> None:
    assert client.get(MANAGED).status_code == HTTPStatus.UNAUTHORIZED


########################################################################################
# Fechas


@pytest.mark.parametrize(
    "override",
    [
        {"start_date": days(-1).isoformat()},
        {"end_date": days(1).isoformat()},
        {"end_time": "18:00"},
        {"category": "inventada"},
    ],
)
def test_the_dates_and_the_schedule_have_to_make_sense(
    theater: ApiUser,
    override: dict,
) -> None:
    response = signed_in(theater).post(MANAGED, event_body(**override))

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content


def test_only_the_team_features_an_event(theater: ApiUser) -> None:
    response = signed_in(theater).post(MANAGED, event_body(featured=True))

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_the_calendar_moves_the_events_along(
    client: DMRClient,
    institution: CulturalInstitution,
) -> None:
    started = make_event(institution, start=-1, end=1, name="Empezó")
    finished = make_event(institution, start=-5, end=-2, name="Terminó")

    public = body(client.get("/event/"))
    started.refresh_from_db()
    finished.refresh_from_db()

    assert [item["name"] for item in public["results"]] == ["Empezó"]
    assert started.status.code == "publicado"  # ty: ignore[unresolved-attribute]
    assert finished.status.code == "finalizado"  # ty: ignore[unresolved-attribute]


########################################################################################
# Editar, cancelar y clonar


def test_an_institution_corrects_its_event(
    client: DMRClient,
    institution: CulturalInstitution,
    theater: ApiUser,
) -> None:
    event = make_event(institution, start=2, end=2)

    response = signed_in(theater).patch(
        f"{MANAGED}{event.pk}/", {"entry_price": 0, "start_time": "09:30"}
    )

    assert response.status_code == HTTPStatus.OK, response.content
    public = body(client.get(f"/event/{event.pk}/"))
    assert public["entry_price"] == 0
    assert public["start_time"] == "09:30"


def test_an_event_of_another_institution_does_not_exist(theater: ApiUser) -> None:
    other = make_event(verified_institution("granada"), start=2, end=2)

    response = signed_in(theater).patch(f"{MANAGED}{other.pk}/", {"entry_price": 0})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_team_filters_the_agenda_by_organizer(
    institution: CulturalInstitution,
    make_member: Callable[..., ApiUser],
) -> None:
    make_event(institution, start=2, end=2, name="Del teatro")
    make_event(verified_institution("granada"), start=2, end=2, name="De otro")
    team = signed_in(make_member("equipo@example.com", "content.moderate"))

    listed = body(team.get(MANAGED, {"organizer_id": str(institution.pk)}))

    assert [item["name"] for item in listed["results"]] == ["Del teatro"]


def test_a_cancelled_event_stays_visible_and_is_not_edited(
    client: DMRClient,
    institution: CulturalInstitution,
    theater: ApiUser,
) -> None:
    event = make_event(institution, start=2, end=2)
    portal = signed_in(theater)

    cancelled = portal.post(f"{MANAGED}{event.pk}/cancel/", {"reason": "Lluvia"})
    edited = portal.patch(f"{MANAGED}{event.pk}/", {"entry_price": 0})

    assert cancelled.status_code == HTTPStatus.OK, cancelled.content
    assert edited.status_code == HTTPStatus.CONFLICT
    public = body(client.get(f"/event/{event.pk}/"))
    assert public["status"] == "cancelled"
    assert public["cancellation_reason"] == "Lluvia"


def test_cloning_copies_everything_but_the_dates(
    institution: CulturalInstitution,
    theater: ApiUser,
) -> None:
    original = make_event(institution, start=-10, end=-10, status="finalizado")

    response = signed_in(theater).post(
        f"{MANAGED}{original.pk}/clone/",
        {"end_date": days(8).isoformat(), "start_date": days(7).isoformat()},
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    clone = body(response)
    assert clone["cloned_from_id"] == str(original.pk)
    assert clone["venue"] == "Parque Central"
    assert clone["status"] == "scheduled"


########################################################################################
# Moderación posterior


def test_the_team_hides_an_event_from_the_app(
    client: DMRClient,
    institution: CulturalInstitution,
    make_member: Callable[..., ApiUser],
) -> None:
    event = make_event(institution, start=2, end=2)
    team = signed_in(make_member("equipo@example.com", "content.moderate"))

    hidden = team.post(f"{MANAGED}{event.pk}/hide/", {"reason": "Contenido falso"})
    gone = client.get(f"/event/{event.pk}/")
    shown = team.post(f"{MANAGED}{event.pk}/show/", {})

    assert hidden.status_code == HTTPStatus.OK, hidden.content
    assert body(hidden)["hidden"] is True
    assert gone.status_code == HTTPStatus.NOT_FOUND
    assert body(shown)["hidden"] is False
    assert client.get(f"/event/{event.pk}/").status_code == HTTPStatus.OK


def test_an_institution_does_not_moderate(
    institution: CulturalInstitution,
    theater: ApiUser,
) -> None:
    event = make_event(institution, start=2, end=2)

    response = signed_in(theater).post(
        f"{MANAGED}{event.pk}/hide/", {"reason": "No corresponde"}
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_hidden_events_are_left_out_of_the_app(
    client: DMRClient,
    institution: CulturalInstitution,
) -> None:
    make_event(institution, start=2, end=2, hidden_at=now(), name="Oculto")
    make_event(institution, start=2, end=2, name="Visible")

    public = body(client.get("/event/"))

    assert [item["name"] for item in public["results"]] == ["Visible"]
