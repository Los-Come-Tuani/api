from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.contrib.auth.models import Group
from django.db import DatabaseError
from django.db.transaction import atomic
from django.utils.timezone import localdate
from dmr.test import DMRClient

from api_auth.models import ApiUser, ApiUserGroups
from api_catalogs.models import CredentialType, Language
from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_profiles.enums import ProviderStates
from api_profiles.models import Credential, ProviderProfile, ProviderStatus
from api_territory.models import City
from api_tests.helpers import PASSWORD, body, credentials
from api_tests.provider_helpers import (
    EMAIL,
    GUIDE_DOCUMENTS,
    PHOTO_KEY,
    application_payload,
    apply,
    code_for,
    document,
    documents,
    fill,
    profile_data,
    provider_client,
)

if TYPE_CHECKING:
    from collections.abc import Callable

########################################################################################

pytestmark = pytest.mark.django_db


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    fill(storage)
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


########################################################################################
# Catálogos


def test_the_application_form_lists_are_public(client: DMRClient) -> None:
    languages = body(client.get("/catalog/language/"))
    services = body(client.get("/catalog/service-type/"))
    types = {
        item["code"]: item for item in body(client.get("/catalog/credential-type/"))
    }

    assert {item["code"] for item in languages} >= {"es", "en", "fr"}
    assert {item["code"] for item in services} == {"guia", "traductor"}
    # a todos se les pide la cédula y el récord; el resto depende de lo que ofrece
    assert types["cedula"]["service"] is None
    assert types["cedula"]["requires_expiry"] is True
    assert types["record_policia"]["requires_expiry"] is False
    assert types["licencia_intur"]["service"] == "guia"
    assert types["certificado_idioma"]["service"] == "traductor"
    assert types["certificado_idioma"]["requires_expiry"] is False
    assert types["licencia_conducir"]["requires_vehicle"] is True
    assert types["seguro_vehiculo"]["requires_vehicle"] is True


def test_the_upload_accepts_provider_documents_and_photos(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    for kind, content_type in (
        ("provider-document", "application/pdf"),
        ("provider-photo", "image/webp"),
    ):
        response = client.post(
            "/upload/",
            {"content_type": content_type, "kind": kind, "size": 300_000},
        )

        assert response.status_code == HTTPStatus.CREATED, response.content
        assert body(response)["key"].startswith(f"{kind}/")


########################################################################################
# Postularse


def test_a_guide_applies_from_the_app_and_stays_inside_waiting_for_review(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = apply(client)

    # la cuenta queda dentro, con los tokens en el cuerpo (como el inicio de sesión)
    assert data["access"]
    assert data["refresh"]

    # todavía no es guía: el papel llega con la aprobación
    assert data["user"]["role"] is None
    assert data["user"]["permissions"] == []
    assert data["user"]["provider"] == {
        "id": data["application"]["provider"]["id"],
        "services": ["guia"],
        "status": "in_review",
    }

    application = data["application"]
    assert application["procedure"] == "application"
    assert application["status"] == "submitted"
    assert application["resolution"] is None
    assert application["missing"] == []
    assert [item["type"]["code"] for item in application["documents"]] == list(
        GUIDE_DOCUMENTS
    )
    assert {item["status"] for item in application["documents"]} == {"uploaded"}
    assert all(item["review"] is None for item in application["documents"])
    assert application["profile"]["services"] == ["guia"]
    # por nombre: español, inglés
    assert application["profile"]["languages"] == [
        {"code": "es", "level": "native"},
        {"code": "en", "level": "advanced"},
    ]

    # una cuenta, un papel: no es turista ni de ningún otro grupo
    user = ApiUser.objects.get(email=EMAIL)
    assert not ApiUserGroups.objects.filter(api_user=user).exists()
    assert str(user.birth_date) == "1990-05-01"
    assert user.nationality == "NI"
    assert (
        ProviderProfile.objects.get(user=user).status.code == ProviderStates.IN_REVIEW
    )


def test_a_translator_who_drives_tourists_is_asked_for_the_matching_papers(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code = code_for(client)
    payload = application_payload(
        code,
        carries_tourists=True,
        documents=documents(("cedula", "record_policia")),
        services=["traductor"],
    )

    response = client.post("/provider-application/", payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    message = body(response)["field_errors"]["body.documents"]
    assert "Certificado de idiomas" in message
    assert "Licencia de conducir" in message
    assert "Seguro del vehículo" in message
    assert "INTUR" not in message

    complete = documents((
        "cedula",
        "record_policia",
        "certificado_idioma",
        "licencia_conducir",
        "seguro_vehiculo",
    ))
    response = client.post("/provider-application/", {**payload, "documents": complete})

    assert response.status_code == HTTPStatus.CREATED, response.content
    assert body(response)["user"]["provider"]["services"] == ["traductor"]


def test_a_document_that_is_not_asked_for_is_refused(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    payload = application_payload(
        code_for(client),
        documents=[*documents(GUIDE_DOCUMENTS), document("licencia_conducir")],
    )

    response = client.post("/provider-application/", payload)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert body(response)["field_errors"] == {
        "body.documents.3.type": "Ese documento no se pide."
    }
    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_a_document_that_expires_needs_its_expiry_date(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    listed = documents(GUIDE_DOCUMENTS)
    listed[0] = document("cedula", expires_on=None)

    response = client.post(
        "/provider-application/",
        application_payload(code_for(client), documents=listed),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.documents.0.expires_on" in body(response)["field_errors"]


def test_an_expired_or_future_document_is_refused(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    today = localdate()
    code = code_for(client)

    for changed in (
        document("cedula", expires_on=(today - timedelta(days=1)).isoformat()),
        document("cedula", issued_on=(today + timedelta(days=1)).isoformat()),
    ):
        listed = [changed, *documents(GUIDE_DOCUMENTS[1:])]
        response = client.post(
            "/provider-application/",
            application_payload(code, documents=listed),
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, response.content

    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_a_file_that_was_not_uploaded_is_refused(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    listed = documents(GUIDE_DOCUMENTS)
    listed[1] = document("record_policia", file_key="provider-document/nunca.jpg")

    response = client.post(
        "/provider-application/",
        application_payload(code_for(client), documents=listed),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.documents.1.file_key" in body(response)["field_errors"]


def test_another_kind_of_file_does_not_count_as_a_document(
    client: DMRClient,
    memory: MemoryStorage,
) -> None:
    memory.put("legal-document/acta.pdf", content_type="application/pdf")
    listed = documents(GUIDE_DOCUMENTS)
    listed[0] = document("cedula", file_key="legal-document/acta.pdf")

    response = client.post(
        "/provider-application/",
        application_payload(code_for(client), documents=listed),
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.documents.0.file_key" in body(response)["field_errors"]


def test_a_wrong_code_does_not_create_the_account(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code_for(client)

    response = client.post("/provider-application/", application_payload("000000"))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.code" in body(response)["field_errors"]
    assert not ApiUser.objects.filter(email=EMAIL).exists()


def test_an_email_that_already_has_an_account_gets_no_code(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    # un turista que quiere ser guía usa otro correo: con el suyo, el alta falla igual
    # que con un código equivocado, sin revelar que la cuenta existe
    make_user(email=EMAIL)

    client.post("/auth/register-code/", {"email": EMAIL})
    response = client.post("/provider-application/", application_payload("123456"))

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.code" in body(response)["field_errors"]
    assert not ProviderProfile.objects.exists()


def test_unknown_languages_and_cities_are_refused(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code = code_for(client)

    response = client.post(
        "/provider-application/",
        application_payload(code, languages=[{"code": "xx", "level": "basic"}]),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.languages.0.code" in body(response)["field_errors"]

    response = client.post(
        "/provider-application/",
        application_payload(code, city_id="018f0000-0000-7000-8000-000000000000"),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.city_id" in body(response)["field_errors"]

    response = client.post(
        "/provider-application/",
        application_payload(
            code,
            languages=[
                {"code": "es", "level": "native"},
                {"code": "es", "level": "basic"},
            ],
        ),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_local_guide_operates_in_one_city(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    city = City.objects.get(code="granada")

    data = apply(client, city_id=str(city.pk))

    assert data["application"]["profile"]["city_id"] == str(city.pk)


########################################################################################
# Una cuenta, un papel


def test_the_provider_in_review_enters_through_the_app_but_not_the_portal(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    apply(client)
    user = ApiUser.objects.get(email=EMAIL)

    web = DMRClient().post("/auth/web/login/", credentials(user))
    mobile = DMRClient().post("/auth/mobile/login/", credentials(user))

    assert web.status_code == HTTPStatus.UNAUTHORIZED
    assert mobile.status_code == HTTPStatus.OK, mobile.content
    assert body(mobile)["user"]["provider"]["status"] == "in_review"


def test_an_account_with_another_role_cannot_have_a_provider_profile(
    make_user: Callable[..., ApiUser],
) -> None:
    tourist = make_user()
    ApiUserGroups.objects.create(
        api_user=tourist, group=Group.objects.get(name="Cliente")
    )

    with pytest.raises(DatabaseError), atomic():
        ProviderProfile.objects.create(
            phone="8888-0000",
            status=ProviderStatus.objects.get(code=ProviderStates.IN_REVIEW),
            user=tourist,
        )


def test_a_tourist_session_has_no_provider(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    tourist = make_user()
    ApiUserGroups.objects.create(
        api_user=tourist, group=Group.objects.get(name="Cliente")
    )

    response = client.post("/auth/mobile/login/", credentials(tourist))

    assert response.status_code == HTTPStatus.OK
    assert body(response)["user"]["provider"] is None

    mine = provider_client(body(response)["access"]).get("/provider-application/mine/")
    assert mine.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Lo que ve


def test_mine_shows_the_latest_application(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = apply(client)
    app = provider_client(data["access"])

    response = app.get("/provider-application/mine/")

    assert response.status_code == HTTPStatus.OK
    mine = body(response)
    assert mine["id"] == data["application"]["id"]
    assert mine["provider"]["status"] == "in_review"
    assert all(item["file"]["url"] for item in mine["documents"])


def test_mine_needs_a_session(client: DMRClient) -> None:
    response = client.get("/provider-application/mine/")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_resubmitting_while_in_review_is_a_conflict(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    app = provider_client(apply(client)["access"])

    response = app.post(
        "/provider-application/mine/resubmit/",
        {**profile_data(), "documents": []},
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_renewing_before_being_approved_is_a_conflict(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    app = provider_client(apply(client)["access"])

    response = app.post(
        "/provider-application/mine/renewal/",
        {"documents": [document("licencia_intur", 2)]},
    )

    assert response.status_code == HTTPStatus.CONFLICT


########################################################################################
# Perfil público


def test_the_profile_shows_what_the_tourist_will_see_and_what_is_missing(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    app = provider_client(apply(client)["access"])

    response = app.get("/provider-profile/mine/")

    assert response.status_code == HTTPStatus.OK
    profile = body(response)
    assert profile["status"] == "in_review"
    assert profile["services"] == ["guia"]
    assert profile["city"] is None
    assert profile["photo"] is None
    assert profile["rating"] is None
    assert profile["reviews"] == 0
    assert [item["code"] for item in profile["languages"]] == ["es", "en"]
    # nada está en vigor todavía: falta todo lo que se le pide
    assert [item["code"] for item in profile["missing"]] == list(GUIDE_DOCUMENTS)


def test_the_profile_changes_what_is_descriptive_right_away(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    app = provider_client(apply(client)["access"])

    response = app.patch(
        "/provider-profile/mine/",
        {
            "languages": [{"code": "fr", "level": "intermediate"}],
            "photo_key": PHOTO_KEY,
            "presentation": "Recorridos de leyendas.",
        },
    )

    assert response.status_code == HTTPStatus.OK, response.content
    profile = body(response)
    assert profile["presentation"] == "Recorridos de leyendas."
    assert profile["photo"]["key"] == PHOTO_KEY
    assert profile["languages"] == [
        {"code": "fr", "label": "Francés", "level": "intermediate"}
    ]
    # lo que no se mandó no cambia
    assert profile["phone"] == "+505 8831 4476"

    response = app.patch("/provider-profile/mine/", {"photo_key": None})

    assert body(response)["photo"] is None


def test_the_profile_photo_has_to_be_uploaded_as_a_photo(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    app = provider_client(apply(client)["access"])

    for key in ("provider-photo/nunca.jpg", "provider-document/cedula-1.jpg"):
        response = app.patch("/provider-profile/mine/", {"photo_key": key})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "body.photo_key" in body(response)["field_errors"]


def test_the_services_and_the_city_are_not_edited_from_the_profile(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    app = provider_client(apply(client)["access"])

    response = app.patch("/provider-profile/mine/", {"services": ["traductor"]})

    assert response.status_code == HTTPStatus.BAD_REQUEST


########################################################################################
# La base


def test_a_document_that_expires_needs_its_date_in_the_database(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    apply(client)
    existing = Credential.objects.select_related("provider", "request").first()
    assert existing is not None

    with pytest.raises(DatabaseError), atomic():
        Credential.objects.create(
            credential_type=CredentialType.objects.get(code="licencia_intur"),
            file_key="provider-document/x.jpg",
            issued_on=localdate(),
            number="1",
            provider=existing.provider,
            request=existing.request,
            status=existing.status,
        )


def test_the_seeded_languages_are_active(db: None) -> None:  # ruff: ignore[unused-function-argument]
    assert Language.objects.filter(active=True, code="es").exists()


def test_the_password_is_checked_before_spending_the_code(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    code = code_for(client)

    weak = client.post(
        "/provider-application/", application_payload(code, password="corta")
    )
    strong = client.post("/provider-application/", application_payload(code))

    assert weak.status_code == HTTPStatus.BAD_REQUEST
    assert "body.password" in body(weak)["field_errors"]
    assert strong.status_code == HTTPStatus.CREATED, strong.content
    assert ApiUser.objects.get(email=EMAIL).check_password(PASSWORD)
