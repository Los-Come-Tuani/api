from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.core import mail
from dmr.test import DMRClient

from api_auth.enums import ApiUserStatus
from api_auth.models import ApiUser, ApiUserGroups
from api_catalogs.models import BusinessType, InstitutionType
from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_moderation.models import VerificationRequest
from api_organizations.models import (
    Business,
    BusinessHours,
    CulturalInstitution,
    SignatureDish,
)
from api_roles.models import RoleAssignment
from api_territory.models import City, Municipality
from api_tests.helpers import PASSWORD, body, credentials, extract_code, web_login

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpResponse

########################################################################################

pytestmark = pytest.mark.django_db

EMAIL = "luis@example.com"
PHOTO_KEY = "signature-dish-photo/vigoron.jpg"
DOCUMENT_KEY = "legal-document/acta.pdf"


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    storage.put(PHOTO_KEY, content_type="image/jpeg", size=300_000)
    storage.put(DOCUMENT_KEY, content_type="application/pdf", size=900_000)
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


def csrf(client: DMRClient) -> dict[str, str]:
    response = client.get("/auth/csrf/")

    assert response.status_code == HTTPStatus.NO_CONTENT

    return {"X-CSRFToken": response.headers["x-csrftoken"]}


def code_for(client: DMRClient, email: str = EMAIL) -> str:
    # el mismo código del correo que usa el registro de la app
    mail.outbox.clear()
    response = client.post("/auth/register-code/", {"email": email})

    assert response.status_code == HTTPStatus.NO_CONTENT, response.content

    return extract_code(mail.outbox[-1])


def applicant(code: str, email: str = EMAIL) -> dict:
    return {
        "code": code,
        "email": email,
        "first_name": "Luis",
        "last_name": "Pérez",
        "password": PASSWORD,
    }


def business_payload(code: str, **override: object) -> dict:
    return {
        **applicant(code),
        "address": "Frente a la catedral",
        "business_type_id": str(BusinessType.objects.get(code="restaurante").pk),
        "city_id": str(City.objects.get(code="leon").pk),
        "hours": [
            {"closes": "17:00", "opens": "08:00", "weekday": 1},
            {"closed": True, "weekday": 0},
        ],
        "latitude": 12.4379,
        "longitude": -86.878,
        "name": "El Sacuanjoche",
        "phone": "2311-0000",
        "ruc": "J0310000000001",
        "signature_dish": {
            "currency": "NIO",
            "name": "Vigorón",
            "photo_key": PHOTO_KEY,
            "reference_price": "120.00",
        },
        **override,
    }


def institution_payload(code: str, **override: object) -> dict:
    return {
        **applicant(code),
        "city_id": str(City.objects.get(code="leon").pk),
        "contact_email": "teatro@example.com",
        "document_key": DOCUMENT_KEY,
        "institution_type_id": str(InstitutionType.objects.get(code="teatro").pk),
        "name": "Teatro Municipal",
        "phone": "2311-1111",
        **override,
    }


def municipality_payload(code: str, **override: object) -> dict:
    return {
        **applicant(code),
        "city_id": str(City.objects.get(code="leon").pk),
        "contact_email": "alcaldia@example.com",
        "document_key": DOCUMENT_KEY,
        "name": "Alcaldía de León",
        "phone": "2311-2222",
        **override,
    }


def post(client: DMRClient, kind: str, payload: dict) -> HttpResponse:
    return client.post(
        f"/organization-application/{kind}/",
        payload,
        headers=csrf(client),
    )


########################################################################################
# Alta de un comercio


def test_a_business_applies_and_is_left_inside_with_limited_access(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    response = post(csrf_client, "business", business_payload(code_for(csrf_client)))

    assert response.status_code == HTTPStatus.CREATED, response.content
    data = body(response)

    # la sesión queda abierta en cookies, igual que el inicio de sesión del portal
    assert response.cookies["access"]["httponly"]
    assert response.cookies["refresh"]["httponly"]
    assert "access" not in data

    # y lo que ve: su cuenta, su organización sin verificar y su solicitud en la bandeja
    assert data["user"]["email"] == EMAIL
    assert data["user"]["role"] == "negocio"
    assert data["user"]["permissions"] == []
    assert data["user"]["organization"] == {
        "id": data["application"]["organization_id"],
        "kind": "business",
        "name": "El Sacuanjoche",
        "verified": False,
    }
    assert data["user"]["organization_id"] == data["application"]["organization_id"]
    assert data["application"]["kind"] == "business"
    assert data["application"]["status"] == "submitted"
    assert data["application"]["resolved_at"] is None
    assert data["application"]["resolution"] is None


def test_applying_creates_the_business_its_files_and_the_scoped_role(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "business", business_payload(code_for(csrf_client)))

    user = ApiUser.objects.get(email=EMAIL)
    business = Business.objects.get(ruc="J0310000000001")

    assert user.status == ApiUserStatus.ACTIVE
    assert user.verified_at is not None
    assert business.verified_at is None
    assert BusinessHours.objects.filter(business=business).count() == 2

    dish = SignatureDish.objects.get(business=business)
    assert dish.withdrawn_at is None
    assert dish.photo is not None
    assert dish.photo.file_key == PHOTO_KEY

    request = VerificationRequest.objects.get(business=business)
    assert request.status.code == "enviada"
    assert request.resolved_at is None

    # la persona opera solo sobre su comercio: el rol de operador con ese ámbito
    assignment = RoleAssignment.objects.get(user=user)
    assert (assignment.role.name, assignment.business_id, assignment.revoked_at) == (
        "Negocio",
        business.pk,
        None,
    )
    assert ApiUserGroups.objects.filter(api_user=user, group__name="Negocio").exists()


def test_the_new_session_reaches_the_application_and_the_profile(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "business", business_payload(code_for(csrf_client)))

    mine = csrf_client.get("/organization-application/mine/")
    profile = csrf_client.get("/auth/profile/")

    assert mine.status_code == HTTPStatus.OK, mine.content
    assert body(mine)["status"] == "submitted"
    assert body(mine)["organization_name"] == "El Sacuanjoche"
    assert body(profile)["organization"]["kind"] == "business"


def test_the_code_works_only_once(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code = code_for(csrf_client)

    first = post(csrf_client, "business", business_payload(code))
    again = post(
        csrf_client,
        "business",
        business_payload(code, ruc="K0310000000002", name="Otro"),
    )

    assert first.status_code == HTTPStatus.CREATED
    assert again.status_code == HTTPStatus.BAD_REQUEST
    assert Business.objects.count() == 1


def test_a_wrong_code_creates_nothing(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    real = code_for(csrf_client)
    wrong = "000000" if real != "000000" else "111111"

    response = post(csrf_client, "business", business_payload(wrong))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not ApiUser.objects.filter(email=EMAIL).exists()
    assert not Business.objects.exists()


def test_a_weak_password_does_not_spend_the_code(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code = code_for(csrf_client)

    weak = post(
        csrf_client, "business", {**business_payload(code), "password": "12345678"}
    )
    ok = post(csrf_client, "business", business_payload(code))

    assert weak.status_code == HTTPStatus.BAD_REQUEST
    assert ok.status_code == HTTPStatus.CREATED, ok.content


def test_it_needs_the_csrf_header_like_every_web_session(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code = code_for(csrf_client)

    response = csrf_client.post(
        "/organization-application/business/", business_payload(code)
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert not Business.objects.exists()


def test_an_email_that_already_has_an_account_gets_no_code_and_cannot_apply(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(email=EMAIL)

    mail.outbox.clear()
    asked = csrf_client.post("/auth/register-code/", {"email": EMAIL})
    response = post(csrf_client, "business", business_payload("123456"))

    # se responde igual que si no existiera (no se revela quién tiene cuenta)
    assert asked.status_code == HTTPStatus.NO_CONTENT
    assert mail.outbox == []
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Business.objects.exists()


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"city_id": "0194c1a2-0000-7000-8000-000000000001"}, "body.city_id"),
        (
            {"business_type_id": "0194c1a2-0000-7000-8000-000000000001"},
            "body.business_type_id",
        ),
        ({"ruc": "corto"}, "body.ruc"),
        ({"phone": "abc"}, "body.phone"),
        ({"latitude": 9.0}, "body.latitude"),
        ({"longitude": -90.0}, "body.longitude"),
        ({"hours": [{"closed": True, "opens": "08:00", "weekday": 0}]}, "body.hours"),
        (
            {"hours": [{"closes": "08:00", "opens": "08:00", "weekday": 0}]},
            "body.hours",
        ),
        (
            {
                "hours": [
                    {"closed": True, "weekday": 3},
                    {"closed": True, "weekday": 3},
                ]
            },
            "body.hours",
        ),
    ],
)
def test_a_badly_filled_form_says_which_field_is_wrong(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    field: str,
    override: dict,
) -> None:
    response = post(
        csrf_client, "business", business_payload(code_for(csrf_client), **override)
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
    assert any(key.startswith(field) for key in body(response)["field_errors"]), body(
        response
    )
    assert not Business.objects.exists()


def test_the_dish_currency_and_photo_must_exist(
    csrf_client: DMRClient,
    memory: MemoryStorage,
) -> None:
    code = code_for(csrf_client)
    dish = business_payload(code)["signature_dish"]

    bad_currency = post(
        csrf_client,
        "business",
        business_payload(code, signature_dish={**dish, "currency": "XXX"}),
    )
    missing_photo = post(
        csrf_client,
        "business",
        business_payload(
            code, signature_dish={**dish, "photo_key": "signature-dish-photo/no.jpg"}
        ),
    )
    other_kind = post(
        csrf_client,
        "business",
        business_payload(code, signature_dish={**dish, "photo_key": DOCUMENT_KEY}),
    )

    assert "body.signature_dish.currency" in body(bad_currency)["field_errors"]
    assert "body.signature_dish.photo_key" in body(missing_photo)["field_errors"]
    assert "body.signature_dish.photo_key" in body(other_kind)["field_errors"]
    assert not Business.objects.exists()
    assert (
        memory.objects
    )  # lo subido sigue ahí: nadie lo borra por un formulario fallido


def test_a_ruc_already_registered_is_a_conflict(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "business", business_payload(code_for(csrf_client)))

    other = DMRClient(enforce_csrf_checks=True)
    response = post(
        other,
        "business",
        business_payload(
            code_for(other, "otra@example.com"),
            email="otra@example.com",
            name="Copia",
        ),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert "body.ruc" in body(response)["field_errors"]
    assert not ApiUser.objects.filter(email="otra@example.com").exists()


########################################################################################
# Alta de una institución cultural y de una alcaldía


def test_an_institution_applies_with_its_legal_document(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    response = post(
        csrf_client, "institution", institution_payload(code_for(csrf_client))
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    data = body(response)
    assert data["user"]["role"] == "institucion"
    assert data["user"]["organization"]["kind"] == "institution"
    assert data["application"]["status"] == "submitted"

    institution = CulturalInstitution.objects.get(name="Teatro Municipal")
    assert institution.verified_at is None
    assert institution.document_key == DOCUMENT_KEY
    assert (
        RoleAssignment.objects.get(user__email=EMAIL).institution_id == institution.pk
    )


def test_an_institution_name_is_unique_per_city_ignoring_case(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "institution", institution_payload(code_for(csrf_client)))

    other = DMRClient(enforce_csrf_checks=True)
    response = post(
        other,
        "institution",
        institution_payload(
            code_for(other, "otro@example.com"),
            email="otro@example.com",
            name="TEATRO MUNICIPAL",
        ),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert "body.name" in body(response)["field_errors"]


def test_an_institution_needs_its_document_uploaded(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    response = post(
        csrf_client,
        "institution",
        institution_payload(
            code_for(csrf_client), document_key="legal-document/falta.pdf"
        ),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.document_key" in body(response)["field_errors"]


def test_a_municipality_applies_with_the_proof_of_representation(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    response = post(
        csrf_client, "municipality", municipality_payload(code_for(csrf_client))
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    data = body(response)
    assert data["user"]["role"] == "alcaldia"
    assert data["user"]["organization"]["kind"] == "municipality"

    municipality = Municipality.objects.get(name="Alcaldía de León")
    assert municipality.verified_at is None
    assert (
        RoleAssignment.objects.get(user__email=EMAIL).municipality_id == municipality.pk
    )


def test_a_city_has_one_municipality(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "municipality", municipality_payload(code_for(csrf_client)))

    other = DMRClient(enforce_csrf_checks=True)
    response = post(
        other,
        "municipality",
        municipality_payload(
            code_for(other, "otra@example.com"), email="otra@example.com"
        ),
    )

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert "body.city_id" in body(response)["field_errors"]


########################################################################################
# Sesión y acceso


def test_an_operator_cannot_sign_in_through_the_app(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "business", business_payload(code_for(csrf_client)))

    response = DMRClient().post(
        "/auth/mobile/login/",
        credentials(ApiUser.objects.get(email=EMAIL)),
    )

    # los operadores entran por el portal; por la app es como una contraseña mala
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_the_applicant_comes_back_to_the_same_application(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "business", business_payload(code_for(csrf_client)))

    again = DMRClient(enforce_csrf_checks=True)
    login = again.post(
        "/auth/web/login/",
        credentials(ApiUser.objects.get(email=EMAIL)),
        headers=csrf(again),
    )
    mine = again.get("/organization-application/mine/")

    assert login.status_code == HTTPStatus.OK, login.content
    assert body(login)["user"]["organization"]["name"] == "El Sacuanjoche"
    assert body(mine)["organization_name"] == "El Sacuanjoche"


def test_the_application_endpoint_needs_a_session_and_an_organization(
    client: DMRClient,
    user: ApiUser,
) -> None:
    assert (
        client.get("/organization-application/mine/").status_code
        == HTTPStatus.UNAUTHORIZED
    )

    tokens = body(client.post("/auth/mobile/login/", credentials(user)))
    nobody = client.get(
        "/organization-application/mine/",
        headers={"Authorization": f"Bearer {tokens['access']}"},
    )

    # una cuenta sin organización no tiene solicitud
    assert nobody.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Listas públicas para los formularios


def test_the_form_lists_are_public(client: DMRClient) -> None:
    cities = body(client.get("/catalog/city/"))
    types = body(client.get("/catalog/business-type/"))
    institutions = body(client.get("/catalog/institution-type/"))

    assert len(cities) == 10
    assert {city["code"] for city in cities} >= {"leon", "granada", "bluefields"}
    assert all(set(city) == {"active", "code", "id", "name"} for city in cities)
    assert {item["code"] for item in types} >= {"restaurante", "cafeteria"}
    assert {item["code"] for item in institutions} == {
        "casa_cultura",
        "fundacion",
        "teatro",
        "ticketera",
    }


def test_an_inactive_type_is_not_offered(client: DMRClient) -> None:
    BusinessType.objects.filter(code="panaderia").update(active=False)

    codes = {item["code"] for item in body(client.get("/catalog/business-type/"))}

    assert "panaderia" not in codes
    assert "restaurante" in codes


########################################################################################
# Corregir y volver a enviar


def apply_and_get_rejected(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    reason: str = "ruc_invalido",
) -> str:
    # se postula, y el equipo rechaza con un motivo; devuelve el id del expediente
    registered = post(csrf_client, "business", business_payload(code_for(csrf_client)))
    request_id: str = body(registered)["application"]["id"]

    reviewer = DMRClient()
    web_login(reviewer, make_member("revisora@example.com", "organizations.review"))
    rejected = reviewer.post(
        f"/verification-request/{request_id}/reject/",
        {"note": "Revisa el número.", "reason": reason},
    )
    assert rejected.status_code == HTTPStatus.OK, rejected.content

    return request_id


def resubmit(client: DMRClient, payload: dict) -> HttpResponse:
    return client.post(
        "/organization-application/mine/resubmit/",
        payload,
        headers=csrf(client),
    )


def corrected_business(**override: object) -> dict:
    data = business_payload("000000", ruc="J0310000000009", name="El Sacuanjoche")
    # lo mismo del alta, sin la cuenta y con `kind`
    for field in ("code", "email", "first_name", "last_name", "password"):
        data.pop(field)

    return {**data, "kind": "business", **override}


def test_a_rejected_business_corrects_and_goes_back_to_the_queue(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,
) -> None:
    rejected_id = apply_and_get_rejected(csrf_client, make_member)
    memory.put("signature-dish-photo/nueva.jpg", content_type="image/jpeg")
    dish = business_payload("000000")["signature_dish"]

    response = resubmit(
        csrf_client,
        corrected_business(
            hours=[{"closed": True, "weekday": 3}],
            signature_dish={
                **dish,
                "name": "Nacatamal",
                "photo_key": "signature-dish-photo/nueva.jpg",
            },
        ),
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    data = body(response)
    assert data["status"] == "submitted"
    assert data["id"] != rejected_id
    assert data["resolution"] is None

    # los datos se corrigieron en la misma ficha, que sigue sin verificar
    business = Business.objects.get()
    assert business.ruc == "J0310000000009"
    assert business.verified_at is None
    assert list(
        BusinessHours.objects.filter(business=business).values_list(
            "weekday", flat=True
        )
    ) == [3]

    # el platillo se reemplazó: el anterior se retiró y queda el nuevo
    dishes = SignatureDish.objects.filter(business=business)
    assert dishes.count() == 2
    assert dishes.get(withdrawn_at__isnull=True).name == "Nacatamal"

    # el expediente rechazado se conserva y hay otro abierto
    requests = VerificationRequest.objects.filter(business=business).order_by(
        "submitted_at"
    )
    assert [item.status.code for item in requests] == ["rechazada", "enviada"]
    assert body(csrf_client.get("/organization-application/mine/"))["id"] == data["id"]


def test_the_corrected_request_shows_the_earlier_rejection_to_the_moderator(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    rejected_id = apply_and_get_rejected(
        csrf_client, make_member, "ubicacion_incorrecta"
    )
    new_id = body(resubmit(csrf_client, corrected_business()))["id"]

    reviewer = DMRClient()
    web_login(reviewer, ApiUser.objects.get(email="revisora@example.com"))
    queue = body(reviewer.get("/verification-request/"))
    detail = body(reviewer.get(f"/verification-request/{new_id}/"))

    assert [item["id"] for item in queue["results"]] == [new_id]
    assert [item["id"] for item in detail["history"]] == [rejected_id]
    assert detail["history"][0]["reason"]["code"] == "ubicacion_incorrecta"
    assert detail["history"][0]["note"] == "Revisa el número."


def test_a_request_still_under_review_cannot_be_resubmitted(
    csrf_client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    post(csrf_client, "business", business_payload(code_for(csrf_client)))

    response = resubmit(csrf_client, corrected_business())

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert VerificationRequest.objects.count() == 1


def test_an_approved_organization_is_not_edited_through_a_resubmission(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    registered = post(csrf_client, "business", business_payload(code_for(csrf_client)))
    reviewer = DMRClient()
    web_login(reviewer, make_member("revisora@example.com", "organizations.review"))
    reviewer.post(
        f"/verification-request/{body(registered)['application']['id']}/approve/", {}
    )

    response = resubmit(csrf_client, corrected_business())

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert Business.objects.get().ruc == "J0310000000001"


def test_the_corrected_data_must_be_of_the_applicants_own_kind(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    apply_and_get_rejected(csrf_client, make_member)
    wrong = institution_payload("000000")
    for field in ("code", "email", "first_name", "last_name", "password"):
        wrong.pop(field)

    response = resubmit(csrf_client, {**wrong, "kind": "institution"})

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
    assert "body.kind" in body(response)["field_errors"]


def test_a_corrected_ruc_cannot_be_one_already_taken_by_another_business(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,
) -> None:

    apply_and_get_rejected(csrf_client, make_member)
    first = Business.objects.get()
    Business.objects.create(
        address="Otra calle",
        business_type=first.business_type,
        city=first.city,
        latitude=first.latitude,
        longitude=first.longitude,
        name="Otro comercio",
        phone="2222-2222",
        ruc="J0310000000009",
    )

    response = resubmit(csrf_client, corrected_business())

    assert response.status_code == HTTPStatus.CONFLICT, response.content
    assert "body.ruc" in body(response)["field_errors"]
    assert memory.objects


def test_a_corrected_dish_photo_must_be_uploaded(
    csrf_client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    apply_and_get_rejected(csrf_client, make_member)
    dish = business_payload("000000")["signature_dish"]

    response = resubmit(
        csrf_client,
        corrected_business(
            signature_dish={**dish, "photo_key": "signature-dish-photo/falta.jpg"}
        ),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, response.content
    assert "body.signature_dish.photo_key" in body(response)["field_errors"]


def test_a_rejected_institution_and_municipality_replace_their_document(
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,
) -> None:
    memory.put("legal-document/nuevo.pdf", content_type="application/pdf")

    for kind, payload in (
        ("institution", institution_payload),
        ("municipality", municipality_payload),
    ):
        client = DMRClient(enforce_csrf_checks=True)
        email = f"{kind}@example.com"
        registered = post(
            client, kind, {**payload(code_for(client, email)), "email": email}
        )
        request_id = body(registered)["application"]["id"]

        reviewer = DMRClient()
        web_login(
            reviewer, make_member(f"rev-{kind}@example.com", "organizations.review")
        )
        reviewer.post(
            f"/verification-request/{request_id}/reject/",
            {"reason": "documento_ilegible"},
        )

        data = payload("000000")
        for field in ("code", "email", "first_name", "last_name", "password"):
            data.pop(field)
        response = resubmit(
            client,
            {**data, "document_key": "legal-document/nuevo.pdf", "kind": kind},
        )

        assert response.status_code == HTTPStatus.CREATED, response.content
        assert body(response)["status"] == "submitted"
        assert body(response)["id"] != request_id

    assert CulturalInstitution.objects.get().document_key == "legal-document/nuevo.pdf"
    assert Municipality.objects.get().document_key == "legal-document/nuevo.pdf"


def test_resubmitting_needs_a_session_and_an_organization(
    client: DMRClient,
    user: ApiUser,
) -> None:
    anonymous = client.post(
        "/organization-application/mine/resubmit/", corrected_business()
    )

    tokens = body(client.post("/auth/mobile/login/", credentials(user)))
    nobody = client.post(
        "/organization-application/mine/resubmit/",
        corrected_business(),
        headers={"Authorization": f"Bearer {tokens['access']}"},
    )

    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert nobody.status_code == HTTPStatus.NOT_FOUND
