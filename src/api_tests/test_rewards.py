from datetime import timedelta
from decimal import Decimal
from http import HTTPStatus
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any

import pytest

from django.db import DatabaseError
from django.db.transaction import atomic
from django.utils.timezone import now

from api_rewards.models import (
    Badge,
    BadgeMovement,
    Coupon,
    CouponCampaign,
    CouponStatus,
    Visit,
)
from api_rewards.services.coupons import expire_sync
from api_territory.models import PointOfInterest
from api_territory.services.places import ensure_business_place_sync
from api_tests.helpers import body
from api_tests.territory_helpers import (
    make_point,
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
    from api_organizations.models import Business

########################################################################################

pytestmark = pytest.mark.django_db

CAMPAIGNS = "/coupon-campaign/"


@pytest.fixture
def point() -> PointOfInterest:
    return make_point(has_badge=True)


@pytest.fixture
def badge(point: PointOfInterest) -> Badge:
    return Badge.objects.create(
        name=point.name, point=point, qr_token=token_urlsafe(18)
    )


@pytest.fixture
def ana(make_user: Callable[..., ApiUser]) -> ApiUser:
    return make_user(email="turista@example.com", first_name="Ana")


@pytest.fixture
def headers(ana: ApiUser) -> dict[str, str]:
    return tourist(ana)


@pytest.fixture
def business() -> Business:
    business = verified_business()
    ensure_business_place_sync(business)

    return business


@pytest.fixture
def owner(make_user: Callable[..., ApiUser], business: Business) -> ApiUser:
    return operator(make_user(email="negocio@example.com"), business, "Negocio")


def near(place: PointOfInterest, meters_north: float = 10) -> dict[str, float]:
    point: Any = place

    # un grado de latitud son unos 111 km
    return {
        "latitude": float(point.latitude) + meters_north / 111_000,
        "longitude": float(point.longitude),
    }


def give_badges(user: ApiUser, amount: int) -> None:
    # una visita de otro lugar que vale lo necesario
    other = make_point(name=f"Regalo {token_urlsafe(4)}", has_badge=True)
    badge = Badge.objects.create(
        name="Regalo", point=other, qr_token=token_urlsafe(18), value=amount
    )
    visit = Visit.objects.create(
        badge=badge,
        distance_meters=0,
        latitude=other.latitude,
        longitude=other.longitude,
        user=user,
    )
    BadgeMovement.objects.create(amount=amount, user=user, visit=visit)


def campaign_body(**override: object) -> dict:
    return {
        "benefit_amount": 10,
        "benefit_type": "descuento_porcentaje",
        "cost_badges": 3,
        "description": "En cualquier platillo de la carta.",
        "expires_at": (now() + timedelta(days=30)).isoformat(),
        "stock_total": 2,
        "title": "10% en tu almuerzo",
        **override,
    }


########################################################################################
# La insignia de un lugar y su QR


def test_turning_on_the_badge_gives_the_place_a_qr(
    make_member: Callable[..., ApiUser],
) -> None:
    place = make_point()
    team = signed_in(make_member("equipo@example.com", "places.manage"))

    before = team.get(f"/place/{place.pk}/qr/")
    team.patch(f"/place/{place.pk}/", {"has_badge": True})
    after = team.get(f"/place/{place.pk}/qr/")

    assert before.status_code == HTTPStatus.NOT_FOUND
    assert after.status_code == HTTPStatus.OK, after.content
    assert body(after)["payload"].startswith("kplan://visit/")


def test_the_owner_downloads_the_qr_of_its_place(
    make_member: Callable[..., ApiUser],
    owner: ApiUser,
    business: Business,
) -> None:
    place = PointOfInterest.objects.get(business=business)
    team = signed_in(make_member("equipo@example.com", "places.manage"))
    team.patch(f"/place/{place.pk}/", {"has_badge": True})

    response = signed_in(owner).get(f"/place/{place.pk}/qr/")

    assert response.status_code == HTTPStatus.OK, response.content


########################################################################################
# La visita (QR + menos de 50 m, una cada 24 horas)


def test_a_tourist_near_the_place_earns_its_badge(
    client: DMRClient,
    badge: Badge,
    headers: dict[str, str],
    point: PointOfInterest,
) -> None:
    response = client.post(
        "/visit/",
        {"qr": f"kplan://visit/{badge.qr_token}", **near(point)},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["amount"] == 1
    assert body(response)["balance"] == 1
    assert body(response)["point"]["pillar"]["code"] == "historia"


def test_a_tourist_far_from_the_place_does_not(
    client: DMRClient,
    badge: Badge,
    headers: dict[str, str],
    point: PointOfInterest,
) -> None:
    response = client.post(
        "/visit/",
        {"qr": badge.qr_token, **near(point, meters_north=200)},
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.latitude" in body(response)["field_errors"]


def test_the_same_place_gives_one_badge_a_day(
    client: DMRClient,
    badge: Badge,
    headers: dict[str, str],
    point: PointOfInterest,
) -> None:
    payload = {"qr": badge.qr_token, **near(point)}

    first = client.post("/visit/", payload, headers=headers)
    second = client.post("/visit/", payload, headers=headers)

    assert first.status_code == HTTPStatus.CREATED
    assert second.status_code == HTTPStatus.CONFLICT


def test_an_unknown_or_turned_off_qr_gives_nothing(
    client: DMRClient,
    badge: Badge,
    headers: dict[str, str],
    point: PointOfInterest,
) -> None:
    unknown = client.post(
        "/visit/", {"qr": "no-existe-este-qr", **near(point)}, headers=headers
    )
    Badge.objects.filter(pk=badge.pk).update(active=False)
    off = client.post("/visit/", {"qr": badge.qr_token, **near(point)}, headers=headers)

    assert unknown.status_code == HTTPStatus.NOT_FOUND
    assert off.status_code == HTTPStatus.NOT_FOUND


def test_only_a_tourist_earns_badges(
    badge: Badge,
    owner: ApiUser,
    point: PointOfInterest,
) -> None:
    response = signed_in(owner).post("/visit/", {"qr": badge.qr_token, **near(point)})

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_the_base_keeps_the_24_hour_window(ana: ApiUser, badge: Badge) -> None:
    def visit() -> Visit:
        return Visit.objects.create(
            badge=badge,
            distance_meters=5,
            latitude=Decimal("12.4"),
            longitude=Decimal("-86.8"),
            user=ana,
        )

    visit()

    with pytest.raises(DatabaseError), atomic():
        visit()


def test_the_balance_says_what_was_earned_and_where(
    client: DMRClient,
    badge: Badge,
    headers: dict[str, str],
    point: PointOfInterest,
) -> None:
    client.post("/visit/", {"qr": badge.qr_token, **near(point)}, headers=headers)

    balance = body(client.get("/badge/mine/", headers=headers))

    assert balance["balance"] == 1
    assert balance["earned"] == 1
    assert balance["visited_point_ids"] == [str(point.pk)]
    assert {item["code"]: item["count"] for item in balance["by_pillar"]}[
        "historia"
    ] == 1
    assert balance["recent"][0]["kind"] == "visit"


########################################################################################
# Campañas del comercio


def test_a_business_publishes_a_campaign_and_it_goes_to_the_store(
    client: DMRClient,
    owner: ApiUser,
) -> None:
    response = signed_in(owner).post(CAMPAIGNS, campaign_body())

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["benefit"]["label"] == "10% de descuento"
    assert body(response)["status"] == "active"

    store = body(client.get("/reward/"))
    assert [item["title"] for item in store["results"]] == ["10% en tu almuerzo"]
    assert store["results"][0]["remaining"] == 2


def test_a_business_keeps_at_most_three_active_campaigns(owner: ApiUser) -> None:
    portal = signed_in(owner)

    for index in range(3):
        created = portal.post(CAMPAIGNS, campaign_body(title=f"Campaña {index}"))
        assert created.status_code == HTTPStatus.CREATED, created.content

    fourth = portal.post(CAMPAIGNS, campaign_body(title="Una más"))

    assert fourth.status_code == HTTPStatus.CONFLICT


@pytest.mark.parametrize(
    "override",
    [
        {"benefit_amount": 150},
        {"benefit_amount": None},
        {"benefit_type": "inventado"},
        {"expires_at": (now() - timedelta(days=1)).isoformat()},
    ],
)
def test_the_benefit_has_to_make_sense(owner: ApiUser, override: dict) -> None:
    response = signed_in(owner).post(CAMPAIGNS, campaign_body(**override))

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content


def test_a_free_product_has_no_amount(owner: ApiUser) -> None:
    response = signed_in(owner).post(
        CAMPAIGNS,
        campaign_body(benefit_amount=None, benefit_type="producto_gratis"),
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["benefit"]["label"] == "Producto gratis"


def test_only_a_business_publishes_coupons(make_user: Callable[..., ApiUser]) -> None:
    mayor = operator(
        make_user(email="alcaldia@example.com"),
        verified_municipality(),
        "Alcaldía",
    )

    response = signed_in(mayor).post(CAMPAIGNS, campaign_body())

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_a_moderator_withdraws_any_campaign(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    owner: ApiUser,
) -> None:
    created = body(signed_in(owner).post(CAMPAIGNS, campaign_body()))
    team = signed_in(make_member("equipo@example.com", "content.moderate"))

    listed = body(team.get(CAMPAIGNS))
    withdrawn = team.post(
        f"{CAMPAIGNS}{created['id']}/withdraw/", {"reason": "Engañosa"}
    )

    assert listed["elements"] == 1
    assert body(withdrawn)["status"] == "withdrawn"
    assert body(client.get("/reward/"))["elements"] == 0


########################################################################################
# Canje y validación en el mostrador


def test_a_tourist_redeems_badges_for_a_coupon(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    owner: ApiUser,
) -> None:
    campaign = body(signed_in(owner).post(CAMPAIGNS, campaign_body()))
    give_badges(ana, 5)

    response = client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)

    assert response.status_code == HTTPStatus.CREATED, response.content
    coupon = body(response)
    assert len(coupon["code"]) == 8
    assert coupon["status"] == "valid"
    assert body(client.get("/badge/mine/", headers=headers))["balance"] == 2
    assert [
        item["code"] for item in body(client.get("/coupon/mine/", headers=headers))
    ] == [coupon["code"]]


def test_without_enough_badges_there_is_no_coupon(
    client: DMRClient,
    headers: dict[str, str],
    owner: ApiUser,
) -> None:
    campaign = body(signed_in(owner).post(CAMPAIGNS, campaign_body()))

    response = client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)

    assert response.status_code == HTTPStatus.CONFLICT
    assert not Coupon.objects.exists()


def test_the_last_coupon_sells_the_campaign_out(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    owner: ApiUser,
) -> None:
    campaign = body(signed_in(owner).post(CAMPAIGNS, campaign_body(stock_total=1)))
    give_badges(ana, 5)

    client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)

    assert CouponCampaign.objects.get(pk=campaign["id"]).status.code == "agotada"
    assert body(client.get("/reward/"))["elements"] == 0


def test_a_withdrawn_campaign_keeps_its_coupons_valid(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    owner: ApiUser,
) -> None:
    portal = signed_in(owner)
    campaign = body(portal.post(CAMPAIGNS, campaign_body()))
    give_badges(ana, 5)
    client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)

    portal.post(f"{CAMPAIGNS}{campaign['id']}/withdraw/", {})

    wallet = body(client.get("/coupon/mine/", headers=headers))
    assert wallet[0]["status"] == "valid"
    assert wallet[0]["benefit"]["label"] == "10% de descuento"


def test_the_business_validates_the_coupon_once(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    owner: ApiUser,
) -> None:
    portal = signed_in(owner)
    campaign = body(portal.post(CAMPAIGNS, campaign_body()))
    give_badges(ana, 5)
    coupon = body(
        client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)
    )
    dictated = f"{coupon['code'][:4].lower()}-{coupon['code'][4:]}"

    first = portal.post("/coupon-redemption/validate/", {"code": dictated})
    again = portal.post("/coupon-redemption/validate/", {"code": coupon["code"]})

    assert first.status_code == HTTPStatus.OK, first.content
    assert body(first)["status"] == "consumed"
    assert body(first)["tourist_name"] == "Ana"
    assert again.status_code == HTTPStatus.CONFLICT


def test_the_business_looks_up_a_coupon_without_spending_it(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    owner: ApiUser,
) -> None:
    portal = signed_in(owner)
    campaign = body(portal.post(CAMPAIGNS, campaign_body()))
    give_badges(ana, 5)
    coupon = body(
        client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)
    )
    dictated = f"{coupon['code'][:4].lower()} {coupon['code'][4:]}"

    found = body(portal.get("/coupon-redemption/", {"code": dictated}))

    assert [item["status"] for item in found["results"]] == ["valid"]
    assert (
        body(portal.get("/coupon-redemption/", {"code": "ZZZZZZZZ"}))["elements"] == 0
    )


def test_a_coupon_of_another_business_does_not_exist_for_this_one(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    make_user: Callable[..., ApiUser],
    owner: ApiUser,
) -> None:
    campaign = body(signed_in(owner).post(CAMPAIGNS, campaign_body()))
    give_badges(ana, 5)
    coupon = body(
        client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)
    )
    rival = operator(
        make_user(email="rival@example.com"),
        verified_business(name="La Competencia", ruc="J0310000000002"),
        "Negocio",
    )

    response = signed_in(rival).post(
        "/coupon-redemption/validate/", {"code": coupon["code"]}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_an_expired_coupon_is_not_validated(
    client: DMRClient,
    ana: ApiUser,
    headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    owner: ApiUser,
) -> None:
    portal = signed_in(owner)
    campaign = body(portal.post(CAMPAIGNS, campaign_body()))
    give_badges(ana, 5)
    coupon = body(
        client.post("/coupon/", {"campaign_id": campaign["id"]}, headers=headers)
    )
    # la fecha límite se copia y no se reescribe: se adelanta el reloj del barrido
    later = now() + timedelta(days=31)
    monkeypatch.setattr("api_rewards.services.coupons.now", lambda: later)

    expire_sync()
    response = portal.post("/coupon-redemption/validate/", {"code": coupon["code"]})

    assert response.status_code == HTTPStatus.CONFLICT
    assert Coupon.objects.get(pk=coupon["id"]).status.code == "expirado"


def test_the_base_does_not_let_the_balance_go_negative(
    ana: ApiUser,
    owner: ApiUser,
) -> None:
    created = body(signed_in(owner).post(CAMPAIGNS, campaign_body()))
    campaign = CouponCampaign.objects.get(pk=created["id"])
    coupon = Coupon.objects.create(
        benefit_type_id=campaign.benefit_type_id,
        business_id=campaign.business_id,
        campaign=campaign,
        code="ABCD2345",
        cost_badges=3,
        expires_at=campaign.expires_at,
        status=CouponStatus.objects.get(code="vigente"),
        title="Sin saldo",
        user=ana,
    )

    with pytest.raises(DatabaseError), atomic():
        BadgeMovement.objects.create(amount=-3, coupon=coupon, user=ana)
