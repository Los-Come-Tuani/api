from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.utils.timezone import localdate, now

from api_catalogs.models import BenefitType
from api_finance.models import (
    BalanceMovement,
    BankAccount,
    Commission,
    Payment,
    Statement,
)
from api_finance.services.statements import issue_statements
from api_notifications.models import Notification
from api_profiles.models import ProviderProfile
from api_rewards.models import (
    Badge,
    CampaignStatus,
    Coupon,
    CouponCampaign,
    CouponStatus,
)
from api_services.models import Booking, BookingStatus, GuidedDeparture
from api_territory.models import Circuit, PointOfInterest
from api_territory.services.places import ensure_business_place_sync
from api_tests.helpers import body
from api_tests.services_helpers import book, deliver, make_guide, publish_departure
from api_tests.territory_helpers import (
    make_circuit,
    make_point,
    mobile_headers,
    operator,
    signed_in,
    tourist,
    verified_business,
    verified_municipality,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db


@pytest.fixture
def circuit() -> Circuit:
    circuit = make_circuit([make_point(name="Uno"), make_point(name="Dos")])
    Circuit.objects.filter(pk=circuit.pk).update(price_adult=1000, price_child=0)

    return circuit


@pytest.fixture
def guide_user(make_user: Callable[..., ApiUser]) -> ApiUser:
    user = make_user(email="guia@example.com", first_name="Pedro")
    make_guide(user)

    return user


@pytest.fixture
def guide(guide_user: ApiUser) -> dict[str, str]:
    return mobile_headers(guide_user)


@pytest.fixture
def ana(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user(email="turista@example.com", first_name="Ana")


@pytest.fixture
def headers(ana: ApiUser) -> dict[str, str]:
    return tourist(ana)


@pytest.fixture
def billing(make_member: Callable[..., ApiUser]) -> DMRClient:
    return signed_in(make_member("cobros@example.com", "billing.manage"))


def payment_of(billing: DMRClient, booking: dict) -> dict:
    listed = body(billing.get("/payment/"))

    return next(
        item for item in listed["results"] if item["booking_id"] == booking["id"]
    )


########################################################################################
# El cobro de una reserva (pasarela manual)


def test_a_booking_opens_a_pending_payment_with_instructions(
    billing: DMRClient,
    circuit: Circuit,
    client: DMRClient,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    booking = book(client, headers, publish_departure(client, guide, circuit))

    payment = payment_of(billing, booking)

    assert booking["payment_status"] == "pendiente"
    assert booking["payment_instructions"]
    assert payment["status"] == "pending"
    assert payment["amount"] == 1000
    assert payment["gateway"] == "manual"


def test_the_team_confirms_the_payment_and_the_tourist_is_told(
    ana: ApiUser,
    billing: DMRClient,
    circuit: Circuit,
    client: DMRClient,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    booking = book(client, headers, publish_departure(client, guide, circuit))
    payment = payment_of(billing, booking)

    response = billing.post(
        f"/payment/{payment['id']}/confirm/", {"reference": "TRF-123"}
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["status"] == "confirmed"
    assert (
        body(client.get(f"/booking/{booking['id']}/", headers=headers))[
            "payment_status"
        ]
        == "pagado"
    )
    assert Notification.objects.filter(kind="pago", user=ana).exists()


def test_a_paid_tour_closes_with_the_commission_and_the_guide_balance(
    billing: DMRClient,
    circuit: Circuit,
    client: DMRClient,
    guide: dict[str, str],
    guide_user: ApiUser,
    headers: dict[str, str],
) -> None:
    booking = book(client, headers, publish_departure(client, guide, circuit))
    billing.post(f"/payment/{payment_of(billing, booking)['id']}/confirm/", {})

    finished = deliver(client, guide, booking)

    assert finished["status"] == "closed"
    assert Commission.objects.get(booking_id=booking["id"]).amount == 150
    assert body(client.get("/balance/mine/", headers=guide))["balance"] == 850
    assert (
        BalanceMovement.objects.filter(
            provider=ProviderProfile.objects.get(user=guide_user)
        ).count()
        == 1
    )


def test_a_tour_paid_after_it_ended_closes_then(
    billing: DMRClient,
    circuit: Circuit,
    client: DMRClient,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    booking = book(client, headers, publish_departure(client, guide, circuit))
    delivered = deliver(client, guide, booking)

    billing.post(f"/payment/{payment_of(billing, booking)['id']}/confirm/", {})

    assert delivered["status"] == "delivered"
    assert (
        body(client.get(f"/booking/{booking['id']}/", headers=headers))["status"]
        == "closed"
    )


def test_cancelling_leaves_a_paid_booking_to_refund_and_voids_an_unpaid_one(
    billing: DMRClient,
    circuit: Circuit,
    client: DMRClient,
    guide: dict[str, str],
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
) -> None:
    paid = book(client, headers, publish_departure(client, guide, circuit))
    payment = payment_of(billing, paid)
    billing.post(f"/payment/{payment['id']}/confirm/", {})
    other = tourist(make_user(email="otra@example.com"))
    unpaid = book(
        client,
        other,
        publish_departure(client, guide, circuit, start_time="14:00"),
    )

    client.post(f"/booking/{paid['id']}/cancel/", {}, headers=headers)
    client.post(f"/booking/{unpaid['id']}/cancel/", {}, headers=other)
    refunded = billing.post(f"/payment/{payment['id']}/refund/", {"reference": "DEV-9"})

    assert payment_of(billing, unpaid)["status"] == "void"
    assert body(refunded)["status"] == "refunded"


@pytest.mark.parametrize(
    ("permissions", "listed", "confirmed"),
    [
        ((), HTTPStatus.FORBIDDEN, HTTPStatus.FORBIDDEN),
        (("billing.view",), HTTPStatus.OK, HTTPStatus.FORBIDDEN),
        (("billing.manage",), HTTPStatus.OK, HTTPStatus.OK),
    ],
)
def test_who_sees_and_confirms_payments(
    circuit: Circuit,
    client: DMRClient,
    confirmed: HTTPStatus,
    guide: dict[str, str],
    headers: dict[str, str],
    listed: HTTPStatus,
    make_member: Callable[..., ApiUser],
    permissions: tuple[str, ...],
) -> None:
    booking = book(client, headers, publish_departure(client, guide, circuit))
    team = signed_in(make_member("equipo@example.com", *permissions))
    payment_id = str(Payment.objects.get(booking_id=booking["id"]).pk)

    assert team.get("/payment/").status_code == listed
    assert team.post(f"/payment/{payment_id}/confirm/", {}).status_code == confirmed


########################################################################################
# Tarifas


def test_the_team_changes_the_commission(
    billing: DMRClient,
    circuit: Circuit,
    client: DMRClient,
    guide: dict[str, str],
    headers: dict[str, str],
) -> None:
    changed = billing.put("/pricing/", {"commission_rate": 10})
    booking = book(client, headers, publish_departure(client, guide, circuit))
    billing.post(f"/payment/{payment_of(billing, booking)['id']}/confirm/", {})
    deliver(client, guide, booking)

    rates = {item["code"]: item["value"] for item in body(changed)}
    assert rates["comision_reserva"] == 10
    assert Commission.objects.get(booking_id=booking["id"]).rate == Decimal("10.00")


def test_only_billing_manage_changes_the_pricing(
    make_member: Callable[..., ApiUser],
) -> None:
    viewer = signed_in(make_member("equipo@example.com", "billing.view"))

    assert viewer.get("/pricing/").status_code == HTTPStatus.OK
    assert viewer.put("/pricing/", {"coupon_fee": 1}).status_code == (
        HTTPStatus.FORBIDDEN
    )


def test_a_business_reads_what_it_pays_but_does_not_change_it(
    make_user: Callable[..., ApiUser],
) -> None:
    owner = signed_in(
        operator(make_user(email="negocio@example.com"), verified_business(), "Negocio")
    )
    mayor = signed_in(
        operator(
            make_user(email="alcaldia@example.com"), verified_municipality(), "Alcaldía"
        )
    )

    assert owner.get("/pricing/").status_code == HTTPStatus.OK
    assert owner.put("/pricing/", {"coupon_fee": 1}).status_code == (
        HTTPStatus.FORBIDDEN
    )
    assert mayor.get("/pricing/").status_code == HTTPStatus.FORBIDDEN


########################################################################################
# Cuenta bancaria y retiros del guía


# Un servicio ya cerrado que le dejó saldo al guía.
def give_balance(guide_user: ApiUser, amount: int) -> None:
    provider = ProviderProfile.objects.get(user=guide_user)
    circuit = make_circuit(
        [make_point(name="Tres"), make_point(name="Cuatro")], title="Otro"
    )
    departure = GuidedDeparture.objects.create(
        capacity=1,
        circuit=circuit,
        date=localdate(),
        provider=provider,
        start_time="06:00",
    )
    booking = Booking.objects.create(
        adults=1,
        amount=amount,
        circuit=circuit,
        date=localdate(),
        departure=departure,
        provider=provider,
        start_time="06:00",
        status=BookingStatus.objects.get(code="cerrada"),
        user=guide_user,
    )
    BalanceMovement.objects.create(
        amount=amount, booking=booking, kind="servicio", provider=provider
    )


def test_the_first_account_counts_now_and_a_change_waits_a_day(
    client: DMRClient,
    guide: dict[str, str],
) -> None:
    first = client.post(
        "/bank-account/mine/",
        {
            "account_type": "ahorro",
            "bank": "BAC",
            "holder": "Pedro Pérez",
            "number": "1234-5678-9012",
        },
        headers=guide,
    )
    change = client.post(
        "/bank-account/mine/",
        {
            "account_type": "corriente",
            "bank": "Banpro",
            "holder": "Pedro Pérez",
            "number": "9999 0000 4321",
        },
        headers=guide,
    )

    assert first.status_code == HTTPStatus.CREATED, first.content
    assert body(first)["active"]["last4"] == "9012"
    assert body(change)["active"]["bank"] == "BAC"
    assert body(change)["pending"]["last4"] == "4321"
    # el número se guarda cifrado
    assert all(
        "1234" not in str(account.number_encrypted)
        for account in BankAccount.objects.all()
    )


def test_a_guide_withdraws_what_it_earned_and_the_team_pays(
    client: DMRClient,
    billing: DMRClient,
    guide: dict[str, str],
    guide_user: ApiUser,
) -> None:
    give_balance(guide_user, 900)
    client.post(
        "/bank-account/mine/",
        {
            "account_type": "ahorro",
            "bank": "BAC",
            "holder": "Pedro",
            "number": "12345678",
        },
        headers=guide,
    )

    too_much = client.post("/withdrawal/", {"amount": 1000}, headers=guide)
    requested = client.post("/withdrawal/", {"amount": 600}, headers=guide)
    queue = body(billing.get("/guide-withdrawal/", {"status": "pending"}))
    paid = billing.post(
        f"/guide-withdrawal/{body(requested)['id']}/pay/", {"reference": "TRF-1"}
    )

    assert too_much.status_code == HTTPStatus.BAD_REQUEST
    assert requested.status_code == HTTPStatus.CREATED, requested.content
    assert queue["results"][0]["account_number"] == "12345678"
    assert body(paid)["status"] == "paid"
    assert body(client.get("/balance/mine/", headers=guide))["balance"] == 300


def test_a_rejected_withdrawal_goes_back_to_the_balance(
    client: DMRClient,
    billing: DMRClient,
    guide: dict[str, str],
    guide_user: ApiUser,
) -> None:
    give_balance(guide_user, 500)
    client.post(
        "/bank-account/mine/",
        {
            "account_type": "ahorro",
            "bank": "BAC",
            "holder": "Pedro",
            "number": "12345678",
        },
        headers=guide,
    )
    requested = body(client.post("/withdrawal/", {"amount": 500}, headers=guide))
    path = f"/guide-withdrawal/{requested['id']}/reject/"

    without = billing.post(path, {})
    rejected = billing.post(path, {"note": "La cuenta no existe."})

    assert without.status_code == HTTPStatus.BAD_REQUEST
    assert body(rejected)["status"] == "rejected"
    assert body(client.get("/balance/mine/", headers=guide))["balance"] == 500


def test_without_an_account_there_is_no_withdrawal(
    client: DMRClient,
    guide: dict[str, str],
    guide_user: ApiUser,
) -> None:
    give_balance(guide_user, 500)

    response = client.post("/withdrawal/", {"amount": 100}, headers=guide)

    assert response.status_code == HTTPStatus.BAD_REQUEST


########################################################################################
# Estados de cuenta de los comercios


def test_the_month_statement_charges_the_badge_and_the_validated_coupons(
    billing: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    business = verified_business()
    place: PointOfInterest = ensure_business_place_sync(business)
    PointOfInterest.objects.filter(pk=place.pk).update(has_badge=True)
    Badge.objects.create(name=place.name, point=place, qr_token="token-de-prueba-1234")
    owner = operator(make_user(email="negocio@example.com"), business, "Negocio")
    campaign = CouponCampaign.objects.create(
        benefit_type=BenefitType.objects.get(code="regalo"),
        business=business,
        cost_badges=1,
        expires_at=now() + timedelta(days=30),
        status=CampaignStatus.objects.get(code="activa"),
        stock_total=5,
        title="Regalo",
    )
    period = localdate().replace(day=1)

    for index in range(2):
        Coupon.objects.create(
            benefit_type_id=campaign.benefit_type_id,
            business=business,
            campaign=campaign,
            code=f"ABCDEFG{index + 2}",
            consumed_at=now(),
            consumed_by=owner,
            cost_badges=1,
            expires_at=campaign.expires_at,
            redeemed_at=now() - timedelta(hours=1),
            status=CouponStatus.objects.get(code="consumido"),
            title="Regalo",
            user=make_user(email=f"t{index}@example.com"),
        )

    first = issue_statements(period)
    again = issue_statements(period)
    statement = body(signed_in(owner).get("/billing/statement/"))["results"][0]
    paid = billing.post(
        f"/billing/statement/{statement['id']}/pay/", {"reference": "R1"}
    )

    assert (first, again) == (1, 0)
    assert statement["total"] == 300 + 2 * 10
    assert {line["concept"] for line in statement["lines"]} == {
        "insignia_mensual",
        "cupon_validado",
    }
    assert body(paid)["status"] == "paid"
    assert Statement.objects.count() == 1
