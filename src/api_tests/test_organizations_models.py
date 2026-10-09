from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from django.db import DatabaseError
from django.db.transaction import atomic
from django.utils.timezone import now

from api_catalogs.models import (
    BusinessType,
    Currency,
    InstitutionType,
    Reason,
    ReasonContext,
)
from api_catalogs.seeder import (
    BUSINESS_TYPES,
    CONTEXT_VERIFICATION_REJECTION,
    CURRENCIES,
    INSTITUTION_TYPES,
    VERIFICATION_REJECTION_REASONS,
    execute as seed_catalogs,
)
from api_organizations.models import (
    Business,
    BusinessHours,
    CulturalInstitution,
    Photo,
    SignatureDish,
)
from api_territory.models import City, Municipality
from api_territory.seeder import (
    CITIES,
    execute as seed_cities,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

########################################################################################

pytestmark = pytest.mark.django_db

RUC = "J0310000000001"


def rejected(call: Callable[[], Any]) -> None:
    # un savepoint propio: la base aborta la transacción entera al rechazar una fila
    with pytest.raises(DatabaseError), atomic():
        call()


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
        ruc=RUC,
    )


########################################################################################
# Semillas


def test_the_catalogs_are_seeded_with_what_the_model_defines() -> None:
    assert set(BusinessType.objects.values_list("code", flat=True)) >= {
        code for code, _ in BUSINESS_TYPES
    }
    assert set(InstitutionType.objects.values_list("code", flat=True)) == {
        code for code, _ in INSTITUTION_TYPES
    }
    assert set(Currency.objects.values_list("code", flat=True)) >= {
        code for code, _, _ in CURRENCIES
    }


def test_the_ten_creative_cities_exist_and_none_is_active_yet() -> None:
    assert City.objects.count() == len(CITIES) == 10
    assert not City.objects.filter(active=True).exists()


def test_every_rejection_reason_is_offered_in_the_verification_list() -> None:
    offered = ReasonContext.objects.filter(context=CONTEXT_VERIFICATION_REJECTION)

    assert offered.count() == len(VERIFICATION_REJECTION_REASONS)
    # «otro» se explica con una nota
    assert Reason.objects.get(code="otro").requires_text is True
    assert Reason.objects.get(code="ruc_invalido").requires_text is False


def test_seeding_again_changes_nothing_the_team_adjusted() -> None:
    City.objects.filter(code="granada").update(active=True)
    BusinessType.objects.filter(code="panaderia").update(active=False)
    cities, types = City.objects.count(), BusinessType.objects.count()

    seed_cities()
    seed_catalogs()

    assert (City.objects.count(), BusinessType.objects.count()) == (cities, types)
    assert City.objects.get(code="granada").active is True
    assert BusinessType.objects.get(code="panaderia").active is False


########################################################################################
# Comercio


def test_a_business_starts_unverified(business: Business) -> None:
    assert business.verified_at is None
    assert business.created_at is not None


@pytest.mark.parametrize(
    "ruc", ["corto", "J031-000000001-ñ", "j0310000000001", "x" * 20]
)
def test_the_ruc_has_the_provisional_official_format(city: City, ruc: str) -> None:
    rejected(
        lambda: Business.objects.create(
            address="Calle 1",
            business_type=BusinessType.objects.get(code="otro"),
            city=city,
            latitude=Decimal("12.4"),
            longitude=Decimal("-86.8"),
            name="Sin formato",
            phone="1",
            ruc=ruc,
        )
    )


def test_the_ruc_is_unique(business: Business, city: City) -> None:
    rejected(
        lambda: Business.objects.create(
            address="Otra calle",
            business_type=business.business_type,
            city=city,
            latitude=Decimal("12.4"),
            longitude=Decimal("-86.8"),
            name="Copia",
            phone="2",
            ruc=RUC,
        )
    )


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [("9.5", "-86.8"), ("15.5", "-86.8"), ("12.4", "-88.0"), ("12.4", "-82.0")],
)
def test_a_business_must_be_inside_nicaragua(
    city: City,
    latitude: str,
    longitude: str,
) -> None:
    rejected(
        lambda: Business.objects.create(
            address="Fuera del mapa",
            business_type=BusinessType.objects.get(code="otro"),
            city=city,
            latitude=Decimal(latitude),
            longitude=Decimal(longitude),
            name="Remoto",
            phone="3",
            ruc="K0310000000009",
        )
    )


def test_the_ruc_can_be_corrected_while_the_record_is_pending(
    business: Business,
) -> None:
    business.ruc = "J0310000000002"  # ty: ignore[invalid-assignment]
    business.save(update_fields=["ruc"])

    assert Business.objects.get(pk=business.pk).ruc == "J0310000000002"


def test_a_verified_business_keeps_its_ruc(business: Business) -> None:
    Business.objects.filter(pk=business.pk).update(verified_at=now())
    business.refresh_from_db()

    business.ruc = "J0310000000002"  # ty: ignore[invalid-assignment]

    rejected(lambda: business.save(update_fields=["ruc"]))


def test_verification_is_never_taken_back(business: Business) -> None:
    Business.objects.filter(pk=business.pk).update(verified_at=now())

    rejected(lambda: Business.objects.filter(pk=business.pk).update(verified_at=None))


def test_the_creation_date_is_not_rewritten(business: Business) -> None:
    rejected(lambda: Business.objects.filter(pk=business.pk).update(created_at=now()))


def test_changes_to_a_business_are_recorded(business: Business) -> None:
    business.name = "El Sacuanjoche II"  # ty: ignore[invalid-assignment]
    business.save(update_fields=["name"])

    # el historial guarda cada versión con el id de la ficha: la inserción y el cambio
    history = Business.pgh_event_model.objects.filter(id=business.pk)

    assert history.count() == 2
    assert set(history.values_list("name", flat=True)) == {
        "El Sacuanjoche",
        "El Sacuanjoche II",
    }


########################################################################################
# Horarios


def test_an_open_day_needs_both_hours_and_a_closed_day_none(business: Business) -> None:
    BusinessHours.objects.create(
        business=business,
        closed=False,
        opens=time(8),
        closes=time(17),
        weekday=1,
    )
    BusinessHours.objects.create(business=business, closed=True, weekday=0)

    # abierto sin hora de cierre
    rejected(
        lambda: BusinessHours.objects.create(
            business=business,
            closed=False,
            opens=time(8),
            weekday=2,
        )
    )
    # cerrado con horario
    rejected(
        lambda: BusinessHours.objects.create(
            business=business,
            closed=True,
            opens=time(8),
            closes=time(17),
            weekday=3,
        )
    )


def test_a_closing_before_the_opening_means_early_morning_but_not_equal(
    business: Business,
) -> None:
    BusinessHours.objects.create(
        business=business,
        closed=False,
        opens=time(18),
        closes=time(2),
        weekday=5,
    )

    rejected(
        lambda: BusinessHours.objects.create(
            business=business,
            closed=False,
            opens=time(9),
            closes=time(9),
            weekday=6,
        )
    )


def test_there_is_one_row_per_weekday_and_the_weekday_is_in_range(
    business: Business,
) -> None:
    BusinessHours.objects.create(business=business, closed=True, weekday=4)

    rejected(
        lambda: BusinessHours.objects.create(business=business, closed=True, weekday=4)
    )
    rejected(
        lambda: BusinessHours.objects.create(business=business, closed=True, weekday=7)
    )


########################################################################################
# Platillo estrella y fotos


def make_dish(business: Business, name: str = "Vigorón") -> SignatureDish:
    return SignatureDish.objects.create(
        business=business,
        currency=Currency.objects.get(code="NIO"),
        name=name,
        reference_price=Decimal("120.00"),
    )


def test_a_business_has_one_current_signature_dish(business: Business) -> None:
    first = make_dish(business)

    rejected(lambda: make_dish(business, "Nacatamal"))

    # reemplazar es retirar y volver a insertar, no actualizar
    SignatureDish.objects.filter(pk=first.pk).update(withdrawn_at=now())
    second = make_dish(business, "Nacatamal")

    assert SignatureDish.objects.filter(business=business).count() == 2
    assert second.withdrawn_at is None


def test_a_withdrawn_dish_does_not_come_back(business: Business) -> None:
    dish = make_dish(business)
    SignatureDish.objects.filter(pk=dish.pk).update(withdrawn_at=now())

    rejected(lambda: SignatureDish.objects.filter(pk=dish.pk).update(withdrawn_at=None))


def test_the_reference_price_is_positive(business: Business) -> None:
    rejected(
        lambda: SignatureDish.objects.create(
            business=business,
            currency=Currency.objects.get(code="NIO"),
            name="Gratis",
            reference_price=Decimal(0),
        )
    )


def test_a_photo_needs_an_owner(business: Business) -> None:
    Photo.objects.create(business=business, file_key="comercio/foto-1.jpg")

    rejected(lambda: Photo.objects.create(file_key="huerfana.jpg"))


def test_deleting_the_photo_leaves_the_dish(business: Business) -> None:
    photo = Photo.objects.create(business=business, file_key="comercio/foto-1.jpg")
    dish = make_dish(business)
    SignatureDish.objects.filter(pk=dish.pk).update(photo=photo)

    photo.delete()

    dish.refresh_from_db()
    assert dish.photo is None


########################################################################################
# Institución cultural y alcaldía


def make_institution(city: City, name: str = "Teatro Municipal") -> CulturalInstitution:
    return CulturalInstitution.objects.create(
        city=city,
        contact_email="teatro@example.com",
        document_key="documentos/teatro.pdf",
        institution_type=InstitutionType.objects.get(code="teatro"),
        name=name,
        phone="2311-1111",
    )


def test_an_institution_is_not_registered_twice_in_the_same_city(city: City) -> None:
    make_institution(city)

    rejected(lambda: make_institution(city, "TEATRO MUNICIPAL"))
    # en otra ciudad, el mismo nombre es otra institución
    make_institution(City.objects.get(code="granada"))


def test_an_institution_starts_unverified_and_stays_verified(city: City) -> None:
    institution = make_institution(city)
    assert institution.verified_at is None

    CulturalInstitution.objects.filter(pk=institution.pk).update(verified_at=now())

    rejected(
        lambda: CulturalInstitution.objects.filter(pk=institution.pk).update(
            verified_at=None
        )
    )


def test_a_city_has_at_most_one_municipality(city: City) -> None:
    Municipality.objects.create(
        city=city,
        contact_email="alcaldia@example.com",
        document_key="documentos/acta.pdf",
        name="Alcaldía de León",
        phone="2311-2222",
    )

    rejected(
        lambda: Municipality.objects.create(
            city=city,
            contact_email="otra@example.com",
            document_key="documentos/otra.pdf",
            name="Otra alcaldía de León",
            phone="2311-3333",
        )
    )


def test_a_verified_municipality_stays_verified(city: City) -> None:
    municipality = Municipality.objects.create(
        city=city,
        contact_email="alcaldia@example.com",
        document_key="documentos/acta.pdf",
        name="Alcaldía de León",
        phone="2311-2222",
    )
    Municipality.objects.filter(pk=municipality.pk).update(verified_at=now())

    rejected(
        lambda: Municipality.objects.filter(pk=municipality.pk).update(verified_at=None)
    )


def test_the_schema_uses_the_spanish_names_of_the_domain_model() -> None:
    names = {
        model: model._meta.db_table  # ruff: ignore[private-member-access]
        for model in (
            Business,
            BusinessHours,
            City,
            CulturalInstitution,
            Municipality,
            Photo,
            SignatureDish,
        )
    }

    assert names == {
        Business: "comercio",
        BusinessHours: "comercio_horario",
        City: "ciudad",
        CulturalInstitution: "institucion_cultural",
        Municipality: "alcaldia",
        Photo: "foto",
        SignatureDish: "platillo_estrella",
    }
