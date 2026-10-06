from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING, NamedTuple

import pytest

from django.contrib.auth.models import Group
from django.core import mail
from django.utils.timezone import now
from dmr.test import DMRClient

from api_catalogs.models import BusinessType, Currency, InstitutionType
from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_moderation.enums import VerificationStates
from api_moderation.models import VerificationRequest, VerificationStatus
from api_organizations.models import (
    Business,
    BusinessHours,
    CulturalInstitution,
    Photo,
    SignatureDish,
)
from api_roles.services import grant_role_sync
from api_territory.models import City, Municipality
from api_tests.helpers import body, credentials, web_login

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpResponse

    from api_auth.models import ApiUser

########################################################################################

pytestmark = pytest.mark.django_db

PHOTO_KEY = "signature-dish-photo/vigoron.jpg"
DOCUMENT_KEY = "legal-document/acta.pdf"


class Pending(NamedTuple):
    request: VerificationRequest
    applicant: ApiUser
    organization: Business | CulturalInstitution | Municipality


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    storage.put(PHOTO_KEY, content_type="image/jpeg")
    storage.put(DOCUMENT_KEY, content_type="application/pdf")
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


def state(code: VerificationStates) -> VerificationStatus:
    return VerificationStatus.objects.get(code=code)


def make_pending(
    make_user: Callable[..., ApiUser],
    kind: str = "business",
    *,
    email: str = "luis@example.com",
    name: str = "El Sacuanjoche",
    ruc: str = "J0310000000001",
) -> Pending:
    applicant = make_user(email=email, first_name="Luis", last_name="Pérez")
    city = City.objects.get(code="leon")

    if kind == "business":
        organization = Business.objects.create(
            address="Frente a la catedral",
            business_type=BusinessType.objects.get(code="restaurante"),
            city=city,
            latitude=Decimal("12.437900"),
            longitude=Decimal("-86.878000"),
            name=name,
            phone="2311-0000",
            ruc=ruc,
        )
        BusinessHours.objects.create(
            business=organization,
            closes="17:00",
            opens="08:00",
            weekday=1,
        )
        BusinessHours.objects.create(business=organization, closed=True, weekday=0)
        photo = Photo.objects.create(business=organization, file_key=PHOTO_KEY)
        SignatureDish.objects.create(
            business=organization,
            currency=Currency.objects.get(code="NIO"),
            name="Vigorón",
            photo=photo,
            reference_price=Decimal("120.00"),
        )
        role = "Negocio"
    elif kind == "institution":
        organization = CulturalInstitution.objects.create(
            city=city,
            contact_email="teatro@example.com",
            document_key=DOCUMENT_KEY,
            institution_type=InstitutionType.objects.get(code="teatro"),
            name=name,
            phone="2311-1111",
        )
        role = "Institución"
    else:
        organization = Municipality.objects.create(
            city=city,
            contact_email="alcaldia@example.com",
            document_key=DOCUMENT_KEY,
            name=name,
            phone="2311-2222",
        )
        role = "Alcaldía"

    request = VerificationRequest.objects.create(
        status=state(VerificationStates.SUBMITTED),
        **{kind: organization},
    )
    grant_role_sync(
        granted_by=applicant,
        role=Group.objects.get(name=role),
        scope_object=organization,
        user=applicant,
    )

    return Pending(request, applicant, organization)


def signed_in(
    make_member: Callable[..., ApiUser],
    *permissions: str,
    email: str = "revisora@example.com",
) -> DMRClient:
    client = DMRClient()
    web_login(client, make_member(email, *permissions))

    return client


########################################################################################
# Qué abre cada permiso

HOLDERS = {
    "nobody": (),
    "viewer": ("organizations.view",),
    "reviewer": ("organizations.review",),
    "manager": ("organizations.manage",),
}

CASES = (
    ("get", "/verification-request/", frozenset({"viewer", "reviewer", "manager"})),
    (
        "get",
        "/verification-request/reason/",
        frozenset({"viewer", "reviewer", "manager"}),
    ),
    (
        "get",
        "/verification-request/{id}/",
        frozenset({"viewer", "reviewer", "manager"}),
    ),
    ("post", "/verification-request/{id}/take/", frozenset({"reviewer", "manager"})),
    ("post", "/verification-request/{id}/release/", frozenset({"reviewer", "manager"})),
    ("post", "/verification-request/{id}/approve/", frozenset({"reviewer", "manager"})),
    ("post", "/verification-request/{id}/reject/", frozenset({"reviewer", "manager"})),
)


def call(client: DMRClient, method: str, path: str, **extra: object) -> HttpResponse:
    payload = {"reason": "otro", "note": "x"} if path.endswith("/reject/") else None

    if method == "get":
        return client.get(path, **extra)

    return client.post(path, payload if payload is not None else {}, **extra)


@pytest.mark.parametrize("holder", HOLDERS)
@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    CASES,
    ids=[f"{m.upper()} {p}" for m, p, _ in CASES],
)
def test_each_role_reaches_only_what_its_permissions_open(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    allowed: frozenset[str],
    holder: str,
    method: str,
    path: str,
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, *HOLDERS[holder])

    response = call(client, method, path.format(id=pending.request.pk))

    if holder in allowed:
        assert response.status_code not in {
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        }, response.content
    else:
        assert response.status_code == HTTPStatus.FORBIDDEN, response.content


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    CASES,
    ids=[f"{m.upper()} {p}" for m, p, _ in CASES],
)
def test_the_queue_needs_a_session(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    allowed: frozenset[str],  # ruff: ignore[unused-function-argument]
    method: str,
    path: str,
) -> None:
    pending = make_pending(make_user)

    response = call(client, method, path.format(id=pending.request.pk))

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    CASES,
    ids=[f"{m.upper()} {p}" for m, p, _ in CASES],
)
def test_an_applicant_cannot_use_the_teams_queue(
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    allowed: frozenset[str],  # ruff: ignore[unused-function-argument]
    method: str,
    path: str,
) -> None:
    pending = make_pending(make_user)
    client = DMRClient()
    web_login(client, pending.applicant)

    response = call(client, method, path.format(id=pending.request.pk))

    assert response.status_code == HTTPStatus.FORBIDDEN


########################################################################################
# La bandeja


def test_the_queue_lists_what_is_open_in_order_of_arrival(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    first = make_pending(make_user, name="Primero", ruc="J0310000000001")
    second = make_pending(
        make_user,
        "institution",
        email="teatro@example.com",
        name="Segundo",
    )
    closed = make_pending(
        make_user,
        "municipality",
        email="alcaldia@example.com",
        name="Cerrada",
    )
    VerificationRequest.objects.filter(pk=closed.request.pk).update(
        resolved_at=now(),
        status=state(VerificationStates.REJECTED),
    )
    client = signed_in(make_member, "organizations.view")

    data = body(client.get("/verification-request/"))

    assert [item["id"] for item in data["results"]] == [
        str(first.request.pk),
        str(second.request.pk),
    ]
    assert data["elements"] == 2
    assert data["results"][0] | {"submitted_at": None} == {
        "city": {
            "code": "leon",
            "id": str(City.objects.get(code="leon").pk),
            "name": "León",
        },
        "id": str(first.request.pk),
        "kind": "business",
        "organization_id": str(first.organization.pk),
        "organization_name": "Primero",
        "resolved_at": None,
        "status": "submitted",
        "submitted_at": None,
        "taken_by": None,
    }


def test_the_queue_filters_by_status_and_kind(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    business = make_pending(make_user)
    institution = make_pending(
        make_user,
        "institution",
        email="teatro@example.com",
        name="Teatro",
    )
    VerificationRequest.objects.filter(pk=institution.request.pk).update(
        resolved_at=now(),
        status=state(VerificationStates.APPROVED),
    )
    client = signed_in(make_member, "organizations.view")

    def ids(query: str) -> list[str]:
        return [
            item["id"]
            for item in body(client.get(f"/verification-request/?{query}"))["results"]
        ]

    assert ids("status=approved") == [str(institution.request.pk)]
    assert ids("status=rejected") == []
    assert ids("status=all") == [
        str(business.request.pk),
        str(institution.request.pk),
    ] or set(ids("status=all")) == {
        str(business.request.pk),
        str(institution.request.pk),
    }
    assert ids("kind=institution&status=all") == [str(institution.request.pk)]
    assert ids("kind=business") == [str(business.request.pk)]


def test_the_queue_is_paginated(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    for number in range(3):
        make_pending(
            make_user,
            email=f"persona{number}@example.com",
            name=f"Comercio {number}",
            ruc=f"J031000000000{number}",
        )
    client = signed_in(make_member, "organizations.view")

    page = body(client.get("/verification-request/?page_size=2"))
    last = body(client.get("/verification-request/?page_size=2&page=2"))

    assert (page["pages"], page["next"], page["previous"], len(page["results"])) == (
        2,
        True,
        False,
        2,
    )
    assert (last["next"], last["previous"], len(last["results"])) == (False, True, 1)


def test_the_rejection_reasons_are_offered_for_the_form(
    make_member: Callable[..., ApiUser],
) -> None:
    client = signed_in(make_member, "organizations.review")

    reasons = body(client.get("/verification-request/reason/"))

    assert {reason["code"] for reason in reasons} >= {"documento_ilegible", "otro"}
    assert (
        next(reason for reason in reasons if reason["code"] == "otro")["requires_text"]
        is True
    )
    assert (
        next(reason for reason in reasons if reason["code"] == "ruc_invalido")[
            "requires_text"
        ]
        is False
    )


########################################################################################
# El expediente


def test_a_business_file_has_the_data_the_moderator_checks(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.view")

    detail = body(client.get(f"/verification-request/{pending.request.pk}/"))

    assert detail["kind"] == "business"
    assert detail["applicant"] == {
        "email": "luis@example.com",
        "id": str(pending.applicant.pk),
        "name": "Luis Pérez",
    }
    assert detail["business"]["ruc"] == "J0310000000001"
    assert detail["business"]["business_type"] == {
        "code": "restaurante",
        "label": "Restaurante",
    }
    assert detail["business"]["latitude"] == pytest.approx(12.4379)
    assert [(day["weekday"], day["closed"]) for day in detail["business"]["hours"]] == [
        (0, True),
        (1, False),
    ]
    assert detail["business"]["signature_dish"] == {
        "currency": "NIO",
        "description": "",
        "name": "Vigorón",
        "reference_price": 120.0,
    }
    # el bucket es privado: se le da al equipo una URL de lectura que vence en minutos
    assert detail["documents"] == [
        {
            "kind": "signature_dish_photo",
            "url": f"https://storage.example/bucket/{PHOTO_KEY}?expires=300",
        }
    ]
    assert detail["institution"] is None
    assert detail["municipality"] is None
    assert detail["resolution"] is None
    assert detail["history"] == []


@pytest.mark.parametrize("kind", ["institution", "municipality"])
def test_an_institution_or_municipality_file_carries_its_legal_document(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    kind: str,
) -> None:
    pending = make_pending(make_user, kind, name="Con documento")
    client = signed_in(make_member, "organizations.view")

    detail = body(client.get(f"/verification-request/{pending.request.pk}/"))

    assert detail[kind] is not None
    assert detail["documents"] == [
        {
            "kind": "legal_document",
            "url": f"https://storage.example/bucket/{DOCUMENT_KEY}?expires=300",
        }
    ]


def test_without_a_bucket_the_file_still_opens_without_document_links(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pending = make_pending(make_user, "municipality")
    monkeypatch.setattr(storage_module, "current", storage_module.DisabledStorage())
    client = signed_in(make_member, "organizations.view")

    detail = body(client.get(f"/verification-request/{pending.request.pk}/"))

    assert detail["documents"] == [{"kind": "legal_document", "url": None}]


def test_an_unknown_request_is_not_found(make_member: Callable[..., ApiUser]) -> None:
    client = signed_in(make_member, "organizations.view")

    assert client.get(
        "/verification-request/0194c1a2-0000-7000-8000-000000000001/"
    ).status_code == (HTTPStatus.NOT_FOUND)


########################################################################################
# Tomar y devolver


def test_taking_a_request_puts_it_in_review_under_the_moderators_name(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")

    response = client.post(f"/verification-request/{pending.request.pk}/take/", {})

    assert response.status_code == HTTPStatus.OK, response.content
    data = body(response)
    assert data["status"] == "in_review"
    assert data["taken_by"]["email"] == "revisora@example.com"


def test_two_moderators_do_not_take_the_same_request(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    first = signed_in(make_member, "organizations.review", email="uno@example.com")
    second = signed_in(make_member, "organizations.review", email="dos@example.com")
    path = f"/verification-request/{pending.request.pk}/take/"

    assert first.post(path, {}).status_code == HTTPStatus.OK
    # quien ya la tiene la puede volver a tomar; otra persona no se la quita
    assert first.post(path, {}).status_code == HTTPStatus.OK
    taken = second.post(path, {})

    assert taken.status_code == HTTPStatus.CONFLICT, taken.content
    assert "uno@example.com" not in body(taken)["detail"]


def test_a_request_goes_back_to_the_queue_by_its_holder_or_a_manager(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    holder = signed_in(make_member, "organizations.review", email="uno@example.com")
    other = signed_in(make_member, "organizations.review", email="dos@example.com")
    manager = signed_in(make_member, "organizations.manage", email="jefa@example.com")
    take = f"/verification-request/{pending.request.pk}/take/"
    release = f"/verification-request/{pending.request.pk}/release/"

    # sin tomarla, no hay nada que devolver
    assert holder.post(release, {}).status_code == HTTPStatus.CONFLICT

    holder.post(take, {})
    assert other.post(release, {}).status_code == HTTPStatus.FORBIDDEN

    given_back = holder.post(release, {})
    assert given_back.status_code == HTTPStatus.OK, given_back.content
    assert body(given_back)["status"] == "submitted"
    assert body(given_back)["taken_by"] is None

    # quien administra las organizaciones puede soltar la de otra persona
    other.post(take, {})
    assert manager.post(release, {}).status_code == HTTPStatus.OK


########################################################################################
# Aprobar y rechazar


def test_approving_makes_the_organization_visible_and_tells_the_applicant(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")
    mail.outbox.clear()

    response = client.post(
        f"/verification-request/{pending.request.pk}/approve/",
        {"note": "Todo en orden."},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    data = body(response)
    assert data["status"] == "approved"
    assert data["resolved_at"] is not None
    assert data["resolution"]["approved"] is True
    assert data["resolution"]["reason"] is None

    # la base marcó la ficha como verificada: eso es lo que la hace visible
    business = Business.objects.get(pk=pending.organization.pk)
    assert business.verified_at is not None

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["luis@example.com"]
    assert "aprobamos" in mail.outbox[0].body


def test_the_applicant_sees_the_session_organization_as_verified_after_approval(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    signed_in(make_member, "organizations.review").post(
        f"/verification-request/{pending.request.pk}/approve/",
        {},
    )
    applicant = DMRClient()
    web_login(applicant, pending.applicant)

    profile = body(applicant.get("/auth/profile/"))
    mine = body(applicant.get("/organization-application/mine/"))

    assert profile["organization"]["verified"] is True
    assert mine["status"] == "approved"
    assert mine["resolution"]["approved"] is True


def test_rejecting_needs_a_reason_offered_for_it(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")
    path = f"/verification-request/{pending.request.pk}/reject/"

    unknown = client.post(path, {"reason": "porque-si"})
    missing = client.post(path, {})
    # «otro» se explica con una nota
    unexplained = client.post(path, {"reason": "otro"})

    assert unknown.status_code == HTTPStatus.BAD_REQUEST
    assert "body.reason" in body(unknown)["field_errors"]
    assert missing.status_code == HTTPStatus.BAD_REQUEST
    assert unexplained.status_code == HTTPStatus.BAD_REQUEST
    assert "body.note" in body(unexplained)["field_errors"]
    # nada se cerró
    pending.request.refresh_from_db()
    assert pending.request.resolved_at is None


def test_rejecting_closes_the_file_with_the_reason_and_the_note_for_the_applicant(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")
    mail.outbox.clear()

    response = client.post(
        f"/verification-request/{pending.request.pk}/reject/",
        {"note": "El RUC tiene un dígito de más.", "reason": "ruc_invalido"},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    data = body(response)
    assert data["status"] == "rejected"
    assert data["resolution"]["approved"] is False
    assert data["resolution"]["reason"] == {
        "code": "ruc_invalido",
        "label": "El RUC no es válido",
    }
    assert data["resolution"]["note"] == "El RUC tiene un dígito de más."

    assert Business.objects.get(pk=pending.organization.pk).verified_at is None

    # el correo dice por qué, para no reintentar a ciegas
    assert len(mail.outbox) == 1
    assert "El RUC no es válido" in mail.outbox[0].body
    assert "El RUC tiene un dígito de más." in mail.outbox[0].body

    # y quien se postuló lo ve entrando
    applicant = DMRClient()
    web_login(applicant, pending.applicant)
    mine = body(applicant.get("/organization-application/mine/"))
    assert mine["status"] == "rejected"
    assert mine["resolution"]["reason"]["code"] == "ruc_invalido"


def test_a_closed_request_cannot_be_decided_again(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")
    base = f"/verification-request/{pending.request.pk}"

    client.post(f"{base}/approve/", {})

    assert client.post(f"{base}/approve/", {}).status_code == HTTPStatus.CONFLICT
    assert client.post(
        f"{base}/reject/", {"reason": "otro", "note": "x"}
    ).status_code == (HTTPStatus.CONFLICT)
    assert client.post(f"{base}/take/", {}).status_code == HTTPStatus.CONFLICT
    assert client.post(f"{base}/release/", {}).status_code == HTTPStatus.CONFLICT


def test_only_the_holder_or_a_manager_resolves_a_request_in_someone_elses_hands(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    holder = signed_in(make_member, "organizations.review", email="uno@example.com")
    other = signed_in(make_member, "organizations.review", email="dos@example.com")
    manager = signed_in(make_member, "organizations.manage", email="jefa@example.com")
    base = f"/verification-request/{pending.request.pk}"

    holder.post(f"{base}/take/", {})

    assert other.post(f"{base}/approve/", {}).status_code == HTTPStatus.CONFLICT
    assert manager.post(f"{base}/approve/", {}).status_code == HTTPStatus.OK


def test_an_unclaimed_request_is_taken_by_whoever_decides_it(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")

    data = body(client.post(f"/verification-request/{pending.request.pk}/approve/", {}))

    assert data["taken_by"]["email"] == "revisora@example.com"


def test_a_rejected_file_stays_in_the_history_of_the_next_one(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    first = make_pending(make_user)
    client = signed_in(make_member, "organizations.review")
    client.post(
        f"/verification-request/{first.request.pk}/reject/",
        {"reason": "documento_vencido"},
    )

    # corregir y volver a enviar abre otro expediente; el primero se conserva
    second = VerificationRequest.objects.create(
        business=Business.objects.get(pk=first.organization.pk),
        status=state(VerificationStates.SUBMITTED),
    )

    history = body(client.get(f"/verification-request/{second.pk}/"))["history"]

    assert len(history) == 1
    assert history[0]["id"] == str(first.request.pk)
    assert history[0]["status"] == "rejected"
    assert history[0]["reason"]["code"] == "documento_vencido"
    assert body(client.get("/verification-request/"))["elements"] == 1


def test_the_applicant_account_keeps_working_after_a_rejection(
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    pending = make_pending(make_user)
    signed_in(make_member, "organizations.review").post(
        f"/verification-request/{pending.request.pk}/reject/",
        {"reason": "ubicacion_incorrecta"},
    )

    response = DMRClient().post("/auth/web/login/", credentials(pending.applicant))

    assert response.status_code == HTTPStatus.OK, response.content
