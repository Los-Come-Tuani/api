from http import HTTPStatus
from io import StringIO
from typing import TYPE_CHECKING

import pytest

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils.timezone import now

from api_agenda.models import Event
from api_auth.models import ApiUser, ApiUserGroups, ApiUserTotpDevice
from api_catalogs.models import ServiceType
from api_core.config import CONFIG
from api_profiles.enums import ProviderStates
from api_profiles.models import ProviderProfile, ProviderService, ProviderStatus
from api_rewards.models import CouponCampaign
from api_roles.models import RoleAssignment
from api_services.models import GuidedDeparture
from api_territory.apps import seed_content
from api_territory.management.commands import seedcontent
from api_territory.models import Circuit, PointOfInterest
from api_tests.helpers import body

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

TEAM_EMAIL = "kplan.nic@gmail.com"
BUSINESS_EMAIL = "alice1003army@gmail.com"
GUIDE_EMAIL = "sunbeam-managua@events.hackclub.com"

########################################################################################


def seed(*args: str) -> str:
    output = StringIO()
    call_command("seedcontent", *args, stderr=output, stdout=output)

    return output.getvalue()


def totals() -> tuple[int, ...]:
    return (
        PointOfInterest.objects.count(),
        Circuit.objects.count(),
        Event.objects.count(),
        ProviderProfile.objects.count(),
        GuidedDeparture.objects.count(),
        CouponCampaign.objects.count(),
    )


def deploying(monkeypatch: pytest.MonkeyPatch, branch: str) -> None:
    # `CONFIG` es un modelo congelado: se reemplaza el valor en su `__dict__`
    monkeypatch.setitem(CONFIG.__dict__, "DEPLOY", value=True)
    monkeypatch.setitem(CONFIG.__dict__, "RAILWAY_GIT_BRANCH", branch)


########################################################################################


def test_the_sample_content_reaches_the_app(client: DMRClient) -> None:
    seed()

    circuits = body(client.get("/circuit/"))
    creative = [circuit for circuit in circuits if circuit["kind"] == "creative"]
    guides = body(client.get("/guide/"))
    rewards = body(client.get("/reward/"))
    departures = client.get(f"/circuit/{creative[0]['id']}/departure/")

    assert creative
    assert not Circuit.objects.filter(
        kind="creative", municipality__verified_at__isnull=True
    ).exists()
    assert guides["elements"] == ProviderProfile.objects.count()
    assert departures.status_code == HTTPStatus.OK
    assert departures.json()
    assert rewards["elements"] == CouponCampaign.objects.count()
    assert Event.objects.exists()


def test_the_team_gets_a_superuser_that_signs_in_with_google() -> None:
    seed()

    admin = ApiUser.objects.get(email=TEAM_EMAIL)

    assert admin.is_superuser
    assert admin.verified_at is not None
    assert not admin.has_usable_password()


def test_an_existing_account_is_promoted_without_what_its_creator_set(
    make_user: Callable[..., ApiUser],
) -> None:
    # en un API de pruebas cualquiera pudo crear la cuenta con ese correo
    squatter = make_user(email=TEAM_EMAIL)
    ApiUserTotpDevice.objects.create(api_user=squatter, confirmed_at=now(), secret="x")

    seed()
    squatter.refresh_from_db()

    assert squatter.is_superuser
    assert not squatter.has_usable_password()
    assert squatter.sessions_revoked_at is not None
    assert not ApiUserTotpDevice.objects.filter(api_user=squatter).exists()


def test_an_existing_account_runs_its_business_and_keeps_its_password(
    make_user: Callable[..., ApiUser],
) -> None:
    owner = make_user(email=BUSINESS_EMAIL)

    seed()
    seed()
    owner.refresh_from_db()

    assignments = RoleAssignment.objects.filter(
        revoked_at__isnull=True, role__name="Negocio", user=owner
    )

    assert owner.has_usable_password()
    assert [str(item.business.name) for item in assignments] == ["Café Cocibolca"]


def test_an_existing_account_becomes_a_guide_and_keeps_its_password(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    guide = make_user(email=GUIDE_EMAIL)

    seed()
    guide.refresh_from_db()

    listed = body(client.get("/guide/?page_size=100"))["results"]

    assert guide.has_usable_password()
    assert ApiUserGroups.objects.filter(api_user=guide, group__name="Guía").exists()
    assert str(guide.pk) in {row["user_id"] for row in listed}


def test_an_application_sent_from_the_app_is_approved(
    make_user: Callable[..., ApiUser],
) -> None:
    guide = make_user(email=GUIDE_EMAIL)
    profile = ProviderProfile.objects.create(
        phone="8888-0000",
        status=ProviderStatus.objects.get(code=ProviderStates.IN_REVIEW),
        user=guide,
    )
    ProviderService.objects.create(
        provider=profile, service=ServiceType.objects.get(code="guia")
    )

    seed()
    profile.refresh_from_db()

    assert profile.approved_at is not None
    assert str(profile.status.code) == ProviderStates.ACTIVE
    assert ApiUserGroups.objects.filter(api_user=guide, group__name="Guía").exists()


def test_loading_again_does_not_repeat_anything() -> None:
    seed()
    first = totals()

    seed()

    assert totals() == first


def test_with_deploy_it_asks_for_force(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(CONFIG.__dict__, "DEPLOY", value=True)

    with pytest.raises(CommandError):
        seed()

    assert not Circuit.objects.exists()


def test_a_deploy_of_another_branch_loads_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deploying(monkeypatch, "production")

    output = seed("--on-deploy")

    assert "No se carga contenido de ejemplo" in output
    assert not Circuit.objects.exists()


def test_a_deploy_of_develop_loads_the_content(monkeypatch: pytest.MonkeyPatch) -> None:
    deploying(monkeypatch, "develop-a")

    seed("--on-deploy")

    assert Circuit.objects.exists()
    assert GuidedDeparture.objects.exists()


def test_the_develop_domain_loads_it_without_the_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deploying(monkeypatch, "")
    monkeypatch.setitem(CONFIG.__dict__, "ALLOWED_HOSTS", ("develop-api.kplan.dev",))

    seed("--on-deploy")

    assert Circuit.objects.exists()


def test_the_azure_domain_loads_it_too(monkeypatch: pytest.MonkeyPatch) -> None:
    deploying(monkeypatch, "")
    monkeypatch.setitem(CONFIG.__dict__, "ALLOWED_HOSTS", ("azure-api.kplan.dev",))

    seed("--on-deploy")

    assert Circuit.objects.filter(kind="creative").count() >= 2
    assert ApiUser.objects.get(email=TEAM_EMAIL).is_superuser


def test_migrating_a_deploy_ends_with_the_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deploying(monkeypatch, "develop-a")

    seed_content()

    assert Circuit.objects.exists()


def test_migrating_outside_a_deploy_loads_nothing() -> None:
    seed_content()

    assert not Circuit.objects.exists()


def test_a_failure_while_deploying_does_not_stop_the_deploy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_: object) -> None:
        raise ValueError("fixture dañada")

    deploying(monkeypatch, "develop-a")
    monkeypatch.setattr(seedcontent.Command, "load_events", broken)

    output = seed("--on-deploy")

    assert "No se cargó el contenido de ejemplo: fixture dañada" in output
    # nada queda a medias
    assert not Circuit.objects.exists()
