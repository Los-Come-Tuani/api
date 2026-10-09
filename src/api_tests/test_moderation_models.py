from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from django.db import DatabaseError
from django.db.transaction import atomic
from django.utils.timezone import now

from api_catalogs.models import BusinessType, InstitutionType, Reason
from api_moderation.enums import VerificationStates
from api_moderation.models import (
    VerificationRequest,
    VerificationResolution,
    VerificationStatus,
)
from api_moderation.seeder import STATES
from api_organizations.models import Business, CulturalInstitution
from api_territory.models import City, Municipality

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db


def rejected(call: Callable[[], Any]) -> None:
    # un savepoint propio: la base aborta la transacción entera al rechazar una fila
    with pytest.raises(DatabaseError), atomic():
        call()


def state(code: VerificationStates) -> VerificationStatus:
    return VerificationStatus.objects.get(code=code)


@pytest.fixture
def city() -> City:
    return City.objects.get(code="leon")


@pytest.fixture
def business(city: City) -> Business:
    return Business.objects.create(
        address="Frente a la catedral",
        business_type=BusinessType.objects.get(code="restaurante"),
        city=city,
        latitude=Decimal("12.437900"),
        longitude=Decimal("-86.878000"),
        name="El Sacuanjoche",
        phone="2311-0000",
        ruc="J0310000000001",
    )


@pytest.fixture
def institution(city: City) -> CulturalInstitution:
    return CulturalInstitution.objects.create(
        city=city,
        contact_email="teatro@example.com",
        document_key="documentos/teatro.pdf",
        institution_type=InstitutionType.objects.get(code="teatro"),
        name="Teatro Municipal",
        phone="2311-1111",
    )


@pytest.fixture
def municipality(city: City) -> Municipality:
    return Municipality.objects.create(
        city=city,
        contact_email="alcaldia@example.com",
        document_key="documentos/acta.pdf",
        name="Alcaldía de León",
        phone="2311-2222",
    )


def submit(**owner: object) -> VerificationRequest:
    return VerificationRequest.objects.create(
        status=state(VerificationStates.SUBMITTED),
        **owner,
    )


def resolve(
    request: VerificationRequest,
    moderator: ApiUser,
    *,
    approved: bool,
    reason: str | None = None,
) -> VerificationResolution:
    return VerificationResolution.objects.create(
        approved=approved,
        reason=Reason.objects.get(code=reason) if reason else None,
        request=request,
        resolved_by=moderator,
    )


########################################################################################
# Estados


def test_the_four_states_are_seeded_with_their_flags() -> None:
    flags = {
        status.code: (status.in_queue, status.is_terminal)
        for status in VerificationStatus.objects.all()
    }

    assert flags == {code: (queue, final) for code, _, queue, final in STATES}
    # la bandeja del moderador son las dos primeras
    assert {code for code, (queue, _) in flags.items() if queue} == {
        VerificationStates.SUBMITTED,
        VerificationStates.IN_REVIEW,
    }


########################################################################################
# Solicitud


def test_a_request_is_about_exactly_one_object(
    business: Business,
    institution: CulturalInstitution,
) -> None:
    submit(business=business)

    rejected(submit)
    rejected(lambda: submit(business=business, institution=institution))


def test_a_record_has_one_open_request_and_a_new_one_after_it_closes(
    business: Business,
    user: ApiUser,
) -> None:
    first = submit(business=business)

    rejected(lambda: submit(business=business))

    resolve(first, user, approved=False, reason="datos_no_coinciden")
    VerificationRequest.objects.filter(pk=first.pk).update(resolved_at=now())

    # corregir y volver a enviar abre otro expediente, y el primero se conserva
    again = submit(business=business)

    assert again.pk != first.pk
    assert VerificationRequest.objects.filter(business=business).count() == 2


def test_what_is_verified_and_when_it_arrived_are_frozen(
    business: Business,
    institution: CulturalInstitution,
) -> None:
    request = submit(business=business)

    rejected(
        lambda: VerificationRequest.objects.filter(pk=request.pk).update(
            business=None,
            institution=institution,
        )
    )
    rejected(
        lambda: VerificationRequest.objects.filter(pk=request.pk).update(
            submitted_at=now(),
        )
    )


def test_a_moderator_takes_a_request_and_gives_it_back(
    business: Business,
    user: ApiUser,
) -> None:
    request = submit(business=business)

    VerificationRequest.objects.filter(pk=request.pk).update(
        status=state(VerificationStates.IN_REVIEW),
        taken_by=user,
    )
    VerificationRequest.objects.filter(pk=request.pk).update(
        status=state(VerificationStates.SUBMITTED),
        taken_by=None,
    )

    request.refresh_from_db()
    assert request.taken_by is None


########################################################################################
# Resolución


def test_approving_makes_the_object_visible_by_the_trigger(
    business: Business,
    institution: CulturalInstitution,
    municipality: Municipality,
    user: ApiUser,
) -> None:
    for owner in (
        {"business": business},
        {"institution": institution},
        {"municipality": municipality},
    ):
        resolve(submit(**owner), user, approved=True)

    for record in (business, institution, municipality):
        record.refresh_from_db()
        assert record.verified_at is not None


def test_rejecting_leaves_the_object_unverified(
    business: Business,
    user: ApiUser,
) -> None:
    resolve(submit(business=business), user, approved=False, reason="ruc_invalido")

    business.refresh_from_db()
    assert business.verified_at is None


def test_a_rejection_without_a_reason_is_impossible(
    business: Business,
    user: ApiUser,
) -> None:
    request = submit(business=business)

    rejected(lambda: resolve(request, user, approved=False))


def test_a_request_closes_once(business: Business, user: ApiUser) -> None:
    request = submit(business=business)
    resolve(request, user, approved=True)

    rejected(lambda: resolve(request, user, approved=False, reason="otro"))


def test_a_resolution_is_never_rewritten_or_deleted(
    business: Business,
    user: ApiUser,
) -> None:
    resolution = resolve(submit(business=business), user, approved=True)

    rejected(
        lambda: VerificationResolution.objects.filter(pk=resolution.pk).update(
            approved=False,
            reason=Reason.objects.get(code="otro"),
        )
    )
    rejected(lambda: VerificationResolution.objects.filter(pk=resolution.pk).delete())


def test_the_schema_uses_the_spanish_names_of_the_domain_model() -> None:
    assert {
        model._meta.db_table  # ruff: ignore[private-member-access]
        for model in (VerificationRequest, VerificationResolution, VerificationStatus)
    } == {"solicitud_verificacion", "resolucion_verificacion", "estado_verificacion"}
