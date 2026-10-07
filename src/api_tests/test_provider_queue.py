from datetime import timedelta
from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from django.core import mail
from django.utils.timezone import localdate
from dmr.test import DMRClient

from api_auth.models import ApiUser, ApiUserGroups
from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_profiles.enums import CredentialStates, ProviderStates
from api_profiles.models import Credential, ProviderProfile
from api_profiles.services.expiry import expire_credentials_sync
from api_roles.models import RoleAssignment
from api_tests.helpers import body, credentials
from api_tests.provider_helpers import (
    EMAIL,
    GUIDE_DOCUMENTS,
    accept_all,
    apply,
    approve,
    document,
    documents,
    fill,
    profile_data,
    provider_client,
    team,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpResponse

########################################################################################

pytestmark = pytest.mark.django_db

REVIEW = ("guides.review",)
DECIDE = ("guides.review", "guides.decide")


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    fill(storage)
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


def reviewer(
    make_member: Callable[..., ApiUser], email: str = "revisora@example.com"
) -> DMRClient:
    return team(make_member, *REVIEW, email=email)


def decider(
    make_member: Callable[..., ApiUser], email: str = "aprobadora@example.com"
) -> DMRClient:
    return team(make_member, *DECIDE, email=email)


def documents_by_type(detail: dict) -> dict[str, dict]:
    return {item["type"]["code"]: item for item in detail["documents"]}


def review(
    client: DMRClient, request_id: str, document_id: str, **verdict: object
) -> HttpResponse:
    return client.post(
        f"/provider-request/{request_id}/document-review/",
        {"accepted": True, "document_id": document_id, **verdict},
    )


def reject_document(
    client: DMRClient, request_id: str, document_id: str
) -> HttpResponse:
    return review(
        client,
        request_id,
        document_id,
        accepted=False,
        note="Se ve borrosa.",
        reason="documento_ilegible",
    )


def approved_guide(
    client: DMRClient, make_member: Callable[..., ApiUser], **override: object
) -> dict:
    data = apply(client, EMAIL, **override)
    approve(decider(make_member), data["application"]["id"])

    return data


########################################################################################
# Qué abre cada permiso

HOLDERS = {
    "nobody": (),
    "viewer": ("guides.view",),
    "reviewer": REVIEW,
    "decider": ("guides.decide",),
}

ALL = frozenset({"viewer", "reviewer", "decider"})
WORKERS = frozenset({"reviewer", "decider"})

CASES = (
    ("get", "/provider-request/", ALL),
    ("get", "/provider-request/reason/", ALL),
    ("get", "/provider-request/{id}/", ALL),
    ("post", "/provider-request/{id}/take/", WORKERS),
    ("post", "/provider-request/{id}/release/", WORKERS),
    ("post", "/provider-request/{id}/document-review/", WORKERS),
    ("post", "/provider-request/{id}/request-changes/", WORKERS),
    ("post", "/provider-request/{id}/approve/", frozenset({"decider"})),
    ("post", "/provider-request/{id}/reject/", frozenset({"decider"})),
)


def call(client: DMRClient, method: str, path: str) -> HttpResponse:
    if method == "get":
        return client.get(path)

    payload: dict = {}

    if path.endswith("/reject/"):
        payload = {"note": "x", "reason": "otro"}
    elif path.endswith("/document-review/"):
        payload = {
            "accepted": True,
            "document_id": "018f0000-0000-7000-8000-000000000000",
        }

    return client.post(path, payload)


@pytest.mark.parametrize("holder", HOLDERS)
@pytest.mark.parametrize(
    ("method", "path", "allowed"),
    CASES,
    ids=[f"{m.upper()} {p}" for m, p, _ in CASES],
)
def test_each_role_reaches_only_what_its_permissions_open(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    allowed: frozenset[str],
    holder: str,
    method: str,
    path: str,
) -> None:
    request_id = apply(client)["application"]["id"]
    member = team(make_member, *HOLDERS[holder])

    response = call(member, method, path.format(id=request_id))

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
def test_the_queue_needs_a_session_and_is_not_for_the_provider(
    client: DMRClient,
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    allowed: frozenset[str],  # ruff: ignore[unused-function-argument]
    method: str,
    path: str,
) -> None:
    data = apply(client)
    request_id = data["application"]["id"]

    anonymous = call(DMRClient(), method, path.format(id=request_id))
    provider = call(provider_client(data["access"]), method, path.format(id=request_id))

    assert anonymous.status_code == HTTPStatus.UNAUTHORIZED
    assert provider.status_code == HTTPStatus.FORBIDDEN


def test_the_organizations_queue_does_not_see_providers(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    organizations = team(make_member, "organizations.manage")

    listed = body(organizations.get("/verification-request/?status=all"))
    detail = organizations.get(f"/verification-request/{request_id}/")

    assert listed["results"] == []
    assert detail.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# La bandeja


def test_the_queue_lists_what_is_open_in_order_of_arrival(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    first = apply(client)["application"]["id"]
    second = apply(
        client,
        "tomas@example.com",
        documents=documents(("cedula", "record_policia", "certificado_idioma")),
        services=["traductor"],
    )["application"]["id"]

    viewer = team(make_member, "guides.view")
    page = body(viewer.get("/provider-request/"))

    assert [item["id"] for item in page["results"]] == [first, second]
    item = page["results"][0]
    assert item["procedure"] == "application"
    assert item["status"] == "submitted"
    assert item["stage"] == "documents"
    assert item["applicant"]["email"] == EMAIL
    assert item["services"] == ["guia"]
    assert item["city"] is None
    assert item["taken_by"] is None
    assert item["counts"] == {"accepted": 0, "pending": 3, "rejected": 0, "total": 3}

    translators = body(viewer.get("/provider-request/?service=traductor"))
    renewals = body(viewer.get("/provider-request/?procedure=renewal"))

    assert [item["id"] for item in translators["results"]] == [second]
    assert renewals["results"] == []


def test_the_reasons_are_offered_for_documents_and_for_the_decision(
    make_member: Callable[..., ApiUser],
) -> None:
    reasons = body(team(make_member, "guides.view").get("/provider-request/reason/"))

    document_codes = [item["code"] for item in reasons["document"]]
    decision_codes = [item["code"] for item in reasons["decision"]]

    assert "documento_ilegible" in document_codes
    assert "antecedentes_no_favorables" in decision_codes
    assert reasons["document"][-1] == {
        "code": "otro",
        "label": "Otro motivo",
        "requires_text": True,
    }


def test_the_file_shows_the_profile_and_each_document_with_its_link(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]

    detail = body(
        team(make_member, "guides.view").get(f"/provider-request/{request_id}/")
    )

    assert detail["profile"]["phone"] == "+505 8831 4476"
    assert detail["profile"]["status"] == "in_review"
    assert [item["code"] for item in detail["profile"]["languages"]] == ["es", "en"]
    assert detail["missing"] == []
    assert detail["history"] == []
    assert detail["resolution"] is None
    for item in detail["documents"]:
        assert item["required"] is True
        assert item["in_this_request"] is True
        assert item["file"]["url"]


def test_an_unknown_request_is_not_found(make_member: Callable[..., ApiUser]) -> None:
    response = team(make_member, "guides.view").get(
        "/provider-request/018f0000-0000-7000-8000-000000000000/"
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


########################################################################################
# Primer paso: revisar los documentos


def test_reviewing_a_document_takes_the_request(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    member = reviewer(make_member)
    detail = body(member.get(f"/provider-request/{request_id}/"))
    cedula = documents_by_type(detail)["cedula"]

    response = review(member, request_id, cedula["id"])

    assert response.status_code == HTTPStatus.OK, response.content
    detail = body(response)
    assert detail["status"] == "in_review"
    assert detail["taken_by"]["email"] == "revisora@example.com"
    assert detail["counts"] == {"accepted": 1, "pending": 2, "rejected": 0, "total": 3}
    accepted = documents_by_type(detail)["cedula"]
    assert accepted["status"] == "in_review"
    assert accepted["review"]["accepted"] is True

    # otra persona no revisa lo que alguien ya tiene
    other = reviewer(make_member, "otra@example.com")
    response = review(
        other, request_id, documents_by_type(detail)["licencia_intur"]["id"]
    )
    assert response.status_code == HTTPStatus.CONFLICT


def test_rejecting_a_document_needs_a_reason_offered_for_documents(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    member = reviewer(make_member)
    cedula = documents_by_type(body(member.get(f"/provider-request/{request_id}/")))[
        "cedula"
    ]

    missing = review(member, request_id, cedula["id"], accepted=False)
    not_offered = review(
        member, request_id, cedula["id"], accepted=False, reason="ruc_invalido"
    )
    without_note = review(
        member, request_id, cedula["id"], accepted=False, reason="otro"
    )

    assert missing.status_code == HTTPStatus.BAD_REQUEST
    assert not_offered.status_code == HTTPStatus.BAD_REQUEST
    assert "body.reason" in body(not_offered)["field_errors"]
    assert without_note.status_code == HTTPStatus.BAD_REQUEST
    assert "body.note" in body(without_note)["field_errors"]


def test_a_document_of_another_request_is_not_found(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    first = apply(client)["application"]
    second = apply(client, "tomas@example.com")["application"]

    response = review(reviewer(make_member), second["id"], first["documents"][0]["id"])

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_verdict_can_change_while_the_request_is_open(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    member = reviewer(make_member)
    cedula = documents_by_type(body(member.get(f"/provider-request/{request_id}/")))[
        "cedula"
    ]

    reject_document(member, request_id, cedula["id"])
    detail = body(review(member, request_id, cedula["id"]))

    changed = documents_by_type(detail)["cedula"]
    assert changed["review"] == {
        "accepted": True,
        "note": "",
        "reason": None,
        "reviewed_at": changed["review"]["reviewed_at"],
    }


def test_all_documents_accepted_moves_the_request_to_the_decision(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]

    detail = accept_all(reviewer(make_member), request_id)

    assert detail["stage"] == "decision"
    assert detail["counts"]["accepted"] == 3


def test_a_request_goes_back_to_the_queue_by_its_holder_or_a_decider(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    holder = reviewer(make_member)
    holder.post(f"/provider-request/{request_id}/take/", {})

    other = reviewer(make_member, "otra@example.com")
    forbidden = other.post(f"/provider-request/{request_id}/release/", {})
    released = decider(make_member).post(f"/provider-request/{request_id}/release/", {})

    assert forbidden.status_code == HTTPStatus.FORBIDDEN
    assert released.status_code == HTTPStatus.OK, released.content
    detail = body(released)
    assert detail["status"] == "submitted"
    assert detail["taken_by"] is None
    assert {item["status"] for item in detail["documents"]} == {"uploaded"}


########################################################################################
# Pedir correcciones y corregir


def test_asking_for_changes_needs_a_rejected_document(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]

    response = reviewer(make_member).post(
        f"/provider-request/{request_id}/request-changes/", {}
    )

    assert response.status_code == HTTPStatus.CONFLICT


def test_asking_for_changes_closes_the_request_and_tells_the_provider_what_to_fix(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = apply(client)
    request_id = data["application"]["id"]
    member = reviewer(make_member)
    by_type = documents_by_type(body(member.get(f"/provider-request/{request_id}/")))
    review(member, request_id, by_type["cedula"]["id"])
    reject_document(member, request_id, by_type["licencia_intur"]["id"])
    mail.outbox.clear()

    response = member.post(
        f"/provider-request/{request_id}/request-changes/",
        {"note": "Toma la foto con buena luz."},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    detail = body(response)
    assert detail["status"] == "rejected"
    assert detail["stage"] is None
    assert detail["resolution"]["reason"]["code"] == "documentos_por_corregir"
    assert detail["resolution"]["note"] == "Toma la foto con buena luz."

    profile = ProviderProfile.objects.get(user__email=EMAIL)
    assert profile.status.code == ProviderStates.UNACCREDITED

    # el correo dice qué corregir y por qué
    message = mail.outbox[-1]
    assert message.to == [EMAIL]
    assert "Licencia o carné del INTUR: El documento no se lee." in message.body
    assert "Se ve borrosa." in message.body
    assert "Toma la foto con buena luz." in message.body

    # y la app lo ve: el rechazado con su motivo, y lo que falta
    mine = body(provider_client(data["access"]).get("/provider-application/mine/"))
    assert mine["status"] == "rejected"
    assert mine["provider"]["status"] == "unaccredited"
    rejected = documents_by_type(mine)["licencia_intur"]
    assert rejected["status"] == "rejected"
    assert rejected["review"]["reason"]["code"] == "documento_ilegible"
    assert [item["code"] for item in mine["missing"]] == ["licencia_intur"]
    # lo aceptado se queda aceptado, esperando
    assert documents_by_type(mine)["cedula"]["status"] == "uploaded"
    assert documents_by_type(mine)["cedula"]["review"]["accepted"] is True


def test_correcting_uploads_only_what_was_rejected_and_keeps_what_was_accepted(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = apply(client)
    first_id = data["application"]["id"]
    member = reviewer(make_member)
    by_type = documents_by_type(body(member.get(f"/provider-request/{first_id}/")))
    review(member, first_id, by_type["cedula"]["id"])
    review(member, first_id, by_type["record_policia"]["id"])
    reject_document(member, first_id, by_type["licencia_intur"]["id"])
    member.post(f"/provider-request/{first_id}/request-changes/", {})
    app = provider_client(data["access"])

    # sin el documento rechazado no se puede reenviar
    lacking = app.post(
        "/provider-application/mine/resubmit/",
        {**profile_data(), "documents": []},
    )
    assert lacking.status_code == HTTPStatus.BAD_REQUEST
    assert (
        "Licencia o carné del INTUR" in body(lacking)["field_errors"]["body.documents"]
    )

    response = app.post(
        "/provider-application/mine/resubmit/",
        {
            **profile_data(presentation="Ahora con la licencia legible."),
            "documents": [document("licencia_intur", 2)],
        },
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    mine = body(response)
    assert mine["id"] != first_id
    assert mine["status"] == "submitted"
    assert mine["provider"]["status"] == "in_review"
    assert mine["profile"]["presentation"] == "Ahora con la licencia legible."

    # en el expediente nuevo solo falta revisar lo que se subió otra vez
    detail = body(member.get(f"/provider-request/{mine['id']}/"))
    by_type = documents_by_type(detail)
    assert detail["counts"] == {"accepted": 2, "pending": 1, "rejected": 0, "total": 3}
    assert by_type["licencia_intur"]["in_this_request"] is True
    assert by_type["cedula"]["in_this_request"] is False
    assert [item["status"] for item in detail["history"]] == ["rejected"]

    # lo aceptado antes no se vuelve a revisar
    response = review(
        member,
        mine["id"],
        by_type["cedula"]["id"],
        accepted=False,
        reason="otro",
        note="x",
    )
    assert response.status_code == HTTPStatus.CONFLICT


########################################################################################
# Segundo paso: decidir


def test_approving_needs_every_document_accepted(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]

    response = decider(make_member).post(f"/provider-request/{request_id}/approve/", {})

    assert response.status_code == HTTPStatus.CONFLICT


def test_the_decider_approves_and_the_account_becomes_a_guide(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    # revisa una persona y decide otra, aunque la primera todavía la tenga
    accept_all(reviewer(make_member), request_id)
    mail.outbox.clear()

    response = decider(make_member).post(
        f"/provider-request/{request_id}/approve/",
        {"note": "Bienvenida."},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    detail = body(response)
    assert detail["status"] == "approved"
    assert detail["resolution"]["approved"] is True
    assert detail["profile"]["status"] == "active"
    assert detail["profile"]["approved_at"] is not None
    assert {item["status"] for item in detail["documents"]} == {"approved"}

    user = ApiUser.objects.get(email=EMAIL)
    assert RoleAssignment.objects.filter(
        revoked_at__isnull=True, role__name="Guía", user=user
    ).exists()
    assert "aprobamos tu perfil" in mail.outbox[-1].body

    # la app entra con el rol de guía y el perfil activo
    login = body(DMRClient().post("/auth/mobile/login/", credentials(user)))
    assert login["user"]["role"] == "guia"
    assert login["user"]["provider"]["status"] == "active"

    # y el perfil público ya no echa nada de menos
    profile = body(provider_client(login["access"]).get("/provider-profile/mine/"))
    assert profile["missing"] == []


def test_a_reviewer_without_the_decision_permission_cannot_approve(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    request_id = apply(client)["application"]["id"]
    member = reviewer(make_member)
    accept_all(member, request_id)

    response = member.post(f"/provider-request/{request_id}/approve/", {})

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_a_guide_and_translator_gets_both_roles(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    approved_guide(
        client,
        make_member,
        documents=documents((*GUIDE_DOCUMENTS, "certificado_idioma")),
        services=["guia", "traductor"],
    )

    user = ApiUser.objects.get(email=EMAIL)
    groups = set(
        ApiUserGroups.objects.filter(api_user=user).values_list(
            "group__name", flat=True
        )
    )
    assert groups == {"Guía", "Traductor"}

    login = body(DMRClient().post("/auth/mobile/login/", credentials(user)))
    assert login["user"]["role"] == "guia"
    assert login["user"]["provider"]["services"] == ["guia", "traductor"]


def test_rejecting_the_provider_needs_a_decision_reason_and_allows_a_new_try(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = apply(client)
    request_id = data["application"]["id"]
    member = decider(make_member)
    accept_all(member, request_id)

    not_offered = member.post(
        f"/provider-request/{request_id}/reject/",
        {"reason": "documento_ilegible"},
    )
    assert not_offered.status_code == HTTPStatus.BAD_REQUEST

    response = member.post(
        f"/provider-request/{request_id}/reject/",
        {
            "note": "El récord tiene una anotación.",
            "reason": "antecedentes_no_favorables",
        },
    )

    assert response.status_code == HTTPStatus.OK, response.content
    assert (
        body(response)["resolution"]["reason"]["code"] == "antecedentes_no_favorables"
    )
    assert ProviderProfile.objects.get(user__email=EMAIL).status.code == (
        ProviderStates.UNACCREDITED
    )
    assert not RoleAssignment.objects.filter(user__email=EMAIL).exists()

    # los documentos ya estaban aceptados: puede volver a enviarla sin subir nada
    resubmitted = provider_client(data["access"]).post(
        "/provider-application/mine/resubmit/",
        {**profile_data(), "documents": []},
    )
    assert resubmitted.status_code == HTTPStatus.CREATED, resubmitted.content


def test_a_closed_request_is_not_reviewed_again(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = approved_guide(client, make_member)
    request_id = data["application"]["id"]
    member = decider(make_member, "otra@example.com")

    take = member.post(f"/provider-request/{request_id}/take/", {})
    again = member.post(f"/provider-request/{request_id}/approve/", {})

    assert take.status_code == HTTPStatus.CONFLICT
    assert again.status_code == HTTPStatus.CONFLICT


########################################################################################
# Renovar


def test_an_approved_guide_renews_without_stopping_work(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = approved_guide(client, make_member)
    app = provider_client(data["access"])

    response = app.post(
        "/provider-application/mine/renewal/",
        {"documents": [document("licencia_intur", 2)]},
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    mine = body(response)
    assert mine["procedure"] == "renewal"
    assert mine["status"] == "submitted"
    # mientras se revisa, sigue activo con la licencia anterior en vigor
    assert mine["provider"]["status"] == "active"
    statuses = sorted(
        item["status"]
        for item in mine["documents"]
        if item["type"]["code"] == "licencia_intur"
    )
    assert statuses == ["approved", "uploaded"]

    # con otra abierta no se renueva otra vez
    again = app.post(
        "/provider-application/mine/renewal/",
        {"documents": [document("cedula", 2)]},
    )
    assert again.status_code == HTTPStatus.CONFLICT


def test_a_renewal_is_settled_by_reviewing_its_documents(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = approved_guide(client, make_member)
    app = provider_client(data["access"])
    renewal = body(
        app.post(
            "/provider-application/mine/renewal/",
            {"documents": [document("licencia_intur", 2)]},
        )
    )
    member = reviewer(make_member)
    detail = body(member.get(f"/provider-request/{renewal['id']}/"))
    assert detail["procedure"] == "renewal"
    assert detail["stage"] == "documents"
    new = next(item for item in detail["documents"] if item["in_this_request"])

    # una renovación no pasa por la decisión
    decision = decider(make_member, "otra@example.com").post(
        f"/provider-request/{renewal['id']}/approve/", {}
    )
    assert decision.status_code == HTTPStatus.CONFLICT

    mail.outbox.clear()
    response = review(member, renewal["id"], new["id"])

    assert response.status_code == HTTPStatus.OK, response.content
    detail = body(response)
    assert detail["status"] == "approved"
    assert "aprobamos la renovación" in mail.outbox[-1].body

    licences = Credential.objects.filter(
        credential_type__code="licencia_intur", provider__user__email=EMAIL
    ).order_by("uploaded_at")
    assert [item.status.code for item in licences] == [
        CredentialStates.REPLACED,
        CredentialStates.APPROVED,
    ]


def test_a_rejected_renewal_keeps_the_previous_document_in_force(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = approved_guide(client, make_member)
    app = provider_client(data["access"])
    renewal = body(
        app.post(
            "/provider-application/mine/renewal/",
            {"documents": [document("licencia_intur", 2)]},
        )
    )
    member = reviewer(make_member)
    new = next(
        item
        for item in body(member.get(f"/provider-request/{renewal['id']}/"))["documents"]
        if item["in_this_request"]
    )

    detail = body(reject_document(member, renewal["id"], new["id"]))

    assert detail["status"] == "rejected"
    assert detail["resolution"]["reason"]["code"] == "documentos_por_corregir"
    profile = body(app.get("/provider-profile/mine/"))
    assert profile["status"] == "active"
    licence = next(
        item
        for item in profile["documents"]
        if item["type"]["code"] == "licencia_intur"
    )
    assert licence["status"] == "approved"


def test_a_renewal_only_takes_documents_that_are_asked_for(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = approved_guide(client, make_member)

    response = provider_client(data["access"]).post(
        "/provider-application/mine/renewal/",
        {"documents": [document("certificado_idioma")]},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "body.documents.0.type" in body(response)["field_errors"]


########################################################################################
# Vencer


def test_an_expired_document_suspends_the_guide_until_it_is_renewed(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    data = approved_guide(client, make_member)
    mail.outbox.clear()

    # el barrido de dentro de seis años: la cédula y la licencia ya vencieron
    report = expire_credentials_sync(localdate() + timedelta(days=6 * 365))

    assert report.expired == 2
    assert [email for email, _, _ in report.suspended] == [EMAIL]
    assert ProviderProfile.objects.get(user__email=EMAIL).status.code == (
        ProviderStates.SUSPENDED
    )
    assert "Cédula de identidad" in mail.outbox[-1].body
    assert "Licencia o carné del INTUR" in mail.outbox[-1].body

    # suspendido conserva su cuenta y su rol: entra para renovar
    app = provider_client(data["access"])
    profile = body(app.get("/provider-profile/mine/"))
    assert profile["status"] == "suspended"
    assert [item["code"] for item in profile["missing"]] == ["cedula", "licencia_intur"]

    renewal = body(
        app.post(
            "/provider-application/mine/renewal/",
            {"documents": [document("cedula", 2), document("licencia_intur", 2)]},
        )
    )
    accept_all(reviewer(make_member), renewal["id"])

    assert ProviderProfile.objects.get(user__email=EMAIL).status.code == (
        ProviderStates.ACTIVE
    )


def test_the_sweep_leaves_alone_what_is_still_in_force(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
) -> None:
    approved_guide(client, make_member)

    report = expire_credentials_sync(localdate())

    assert report.expired == 0
    assert report.suspended == []
    assert ProviderProfile.objects.get(user__email=EMAIL).status.code == (
        ProviderStates.ACTIVE
    )
