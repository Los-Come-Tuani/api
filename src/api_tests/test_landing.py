from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from asgiref.sync import async_to_sync
from dmr.test import DMRAsyncRequestFactory, assert_async_throttling
from dmr.throttling import Rate

from api_auth.models import ApiUser
from api_landing.controllers import DemoRequestController
from api_landing.models import AppRelease, DemoRequest
from api_notifications.models import Notification
from api_tests.helpers import PASSWORD, body
from api_tests.territory_helpers import signed_in, tourist

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient

########################################################################################

pytestmark = pytest.mark.django_db

DEMO: dict[str, str] = {
    "city": "León",
    "email": "Lucia@Ejemplo.com",
    "kind": "business",
    "message": "Queremos ver cómo se publican los cupones.",
    "name": "Lucía Martínez",
    "organization": "Café Sacuanjoche",
    "phone": "+505 8888 0000",
}

DRIVE: str = "https://drive.google.com/file/d/kplan-{version}/view"


@pytest.fixture
def publisher(make_member: Callable[..., ApiUser]) -> DMRClient:
    return signed_in(make_member("versiones@example.com", "releases.manage"))


def release(
    publisher: DMRClient,
    version: str = "1.0.0",
    platform: str = "android",
) -> dict:
    response = publisher.post(
        "/app-release/",
        {
            "link": DRIVE.format(version=version),
            "notes": "Primera versión del piloto.",
            "platform": platform,
            "version": version,
        },
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


def published(
    publisher: DMRClient,
    version: str = "1.0.0",
    platform: str = "android",
) -> dict:
    created = release(publisher, version, platform)

    return body(publisher.post(f"/app-release/{created['id']}/publish/"))


########################################################################################
# Pedir una demo desde la landing


def test_without_a_release_the_request_waits_for_the_link(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    sent = client.post("/demo-request/", DEMO)
    team = signed_in(make_member("ventas@example.com", "demos.view"))
    queue = body(team.get("/demo-request/"))

    assert sent.status_code == HTTPStatus.OK, sent.content
    assert body(sent) == {"delivered": False, "links": []}
    assert queue["elements"] == 1
    item = queue["results"][0]
    assert item["email"] == "lucia@ejemplo.com"
    assert item["kind"] == "business"
    assert item["organization"] == "Café Sacuanjoche"
    assert item["status"] == "pending"
    assert item["delivered_at"] is None
    assert item["updated_by"] is None


def test_with_a_release_the_request_gets_the_links_right_away(
    client: DMRClient,
    publisher: DMRClient,
) -> None:
    published(publisher, "1.0.0", "android")
    published(publisher, "0.9.0", "windows")

    sent = body(client.post("/demo-request/", DEMO))
    request = DemoRequest.objects.get()

    assert sent == {
        "delivered": True,
        "links": [
            {
                "link": DRIVE.format(version="1.0.0"),
                "platform": "android",
                "version": "1.0.0",
            },
            {
                "link": DRIVE.format(version="0.9.0"),
                "platform": "windows",
                "version": "0.9.0",
            },
        ],
    }
    assert request.status == "entregada"
    assert request.delivered_at is not None
    assert set(AppRelease.objects.values_list("deliveries", flat=True)) == {1}


def test_who_attends_demos_gets_a_notice(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    make_user: Callable[..., ApiUser],
) -> None:
    attends = make_member("atiende@example.com", "demos.manage")
    only_sees = make_member("mira@example.com", "demos.view")
    root = ApiUser.objects.create_superuser(email="raiz@example.com", password=PASSWORD)
    visitor = make_user(email="turista@example.com")
    tourist(visitor)

    client.post("/demo-request/", DEMO)

    notified = set(
        Notification.objects.filter(kind="solicitud_demo").values_list(
            "user_id", flat=True
        )
    )
    request = DemoRequest.objects.get()
    notice = Notification.objects.get(user=attends)

    assert notified == {attends.pk, root.pk}
    assert only_sees.pk not in notified
    assert notice.data == {"demo_request_id": str(request.pk)}
    assert "Café Sacuanjoche" in notice.body
    assert "hay que hacerle llegar el link" in notice.body


def test_a_bot_that_fills_the_trap_is_answered_but_ignored(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    publisher: DMRClient,
) -> None:
    make_member("atiende@example.com", "demos.manage")
    published(publisher)

    response = client.post(
        "/demo-request/", {**DEMO, "website": "https://spam.example"}
    )

    assert response.status_code == HTTPStatus.OK
    assert body(response)["delivered"] is True
    assert not DemoRequest.objects.exists()
    assert not Notification.objects.exists()
    assert AppRelease.objects.get().deliveries == 0


def test_sending_it_again_corrects_the_pending_one(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    attends = make_member("atiende@example.com", "demos.manage")

    client.post("/demo-request/", DEMO)
    client.post("/demo-request/", {**DEMO, "message": "Mejor el jueves."})

    assert DemoRequest.objects.get().message == "Mejor el jueves."
    assert Notification.objects.filter(user=attends).count() == 1


def test_a_pending_request_sent_again_after_publishing_is_delivered(
    client: DMRClient,
    publisher: DMRClient,
) -> None:
    client.post("/demo-request/", DEMO)
    published(publisher)

    client.post("/demo-request/", DEMO)

    assert DemoRequest.objects.get().status == "entregada"


def test_once_delivered_a_new_request_opens_another(
    client: DMRClient,
    publisher: DMRClient,
) -> None:
    published(publisher)
    client.post("/demo-request/", DEMO)

    client.post("/demo-request/", DEMO)

    assert DemoRequest.objects.count() == 2


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"email": "no-es-correo"}, "email"),
        ({"organization": ""}, "organization"),
        ({"kind": "museo"}, "kind"),
        ({"name": "L"}, "name"),
    ],
)
def test_a_demo_request_needs_its_data(
    client: DMRClient,
    change: dict[str, str],
    field: str,
) -> None:
    response = client.post("/demo-request/", {**DEMO, **change})

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert any(field in key for key in body(response)["field_errors"])


def test_asking_for_demos_is_throttled() -> None:
    factory = DMRAsyncRequestFactory()

    async_to_sync(assert_async_throttling)(
        DemoRequestController,
        lambda: factory.post("/demo-request/", {**DEMO, "website": "bot"}),
        max_requests=10,
        rate=Rate.minute,
        success_status=HTTPStatus.OK,
    )


########################################################################################
# La bandeja del equipo


def test_the_queue_filters_by_status_and_search(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    publisher: DMRClient,
) -> None:
    client.post("/demo-request/", DEMO)
    published(publisher)
    client.post(
        "/demo-request/",
        {
            **DEMO,
            "email": "marta@alcaldia.example",
            "kind": "municipality",
            "name": "Marta Ruiz",
            "organization": "Alcaldía de Granada",
        },
    )
    team = signed_in(make_member("ventas@example.com", "demos.view"))

    delivered = body(team.get("/demo-request/", {"status": "delivered"}))
    found = body(team.get("/demo-request/", {"search": "cafe"}))

    assert [item["name"] for item in delivered["results"]] == ["Marta Ruiz"]
    assert [item["name"] for item in found["results"]] == ["Lucía Martínez"]


def test_marking_it_delivered_records_when_notes_and_who(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    client.post("/demo-request/", DEMO)
    request = DemoRequest.objects.get()
    team = signed_in(make_member("ventas@example.com", "demos.manage"))

    response = team.patch(
        f"/demo-request/{request.pk}/",
        {"notes": "Le mandé el link por WhatsApp.", "status": "delivered"},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    updated = body(response)
    assert updated["status"] == "delivered"
    assert updated["delivered_at"] is not None
    assert updated["notes"] == "Le mandé el link por WhatsApp."
    assert updated["updated_by"] is not None
    assert updated["updated_at"] is not None
    assert body(team.get(f"/demo-request/{request.pk}/"))["status"] == "delivered"


def test_back_to_pending_forgets_the_delivery(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    publisher: DMRClient,
) -> None:
    published(publisher)
    client.post("/demo-request/", DEMO)
    request = DemoRequest.objects.get()
    team = signed_in(make_member("ventas@example.com", "demos.manage"))

    notes_only = body(team.patch(f"/demo-request/{request.pk}/", {"notes": "Ok."}))
    pending = body(team.patch(f"/demo-request/{request.pk}/", {"status": "pending"}))

    assert notes_only["delivered_at"] is not None
    assert pending["status"] == "pending"
    assert pending["delivered_at"] is None


def test_only_who_attends_changes_a_request(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    client.post("/demo-request/", DEMO)
    request = DemoRequest.objects.get()
    viewer = signed_in(make_member("mira@example.com", "demos.view"))

    response = viewer.patch(f"/demo-request/{request.pk}/", {"status": "delivered"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert DemoRequest.objects.get().status == "pendiente"


def test_an_unknown_request_is_not_found(make_member: Callable[..., ApiUser]) -> None:
    team = signed_in(make_member("ventas@example.com", "demos.manage"))

    assert team.get(f"/demo-request/{uuid4()}/").status_code == HTTPStatus.NOT_FOUND


def test_the_queue_is_for_the_team(
    client: DMRClient,
    make_user: Callable[..., ApiUser],
) -> None:
    headers = tourist(make_user(email="turista@example.com"))

    assert client.get("/demo-request/").status_code == HTTPStatus.UNAUTHORIZED
    assert (
        client.get("/demo-request/", headers=headers).status_code
        == HTTPStatus.FORBIDDEN
    )


########################################################################################
# Versiones con su link


def test_a_new_release_starts_as_a_draft(publisher: DMRClient) -> None:
    created = release(publisher)

    assert created["status"] == "draft"
    assert created["current"] is False
    assert created["link"] == DRIVE.format(version="1.0.0")
    assert created["deliveries"] == 0
    assert body(publisher.get("/app-release/"))["elements"] == 1


def test_a_version_is_unique_per_platform(publisher: DMRClient) -> None:
    release(publisher, "1.0.0", "android")
    release(publisher, "1.0.0", "windows")

    again = publisher.post(
        "/app-release/",
        {
            "link": DRIVE.format(version="otra"),
            "platform": "android",
            "version": "1.0.0",
        },
    )

    assert again.status_code == HTTPStatus.CONFLICT
    assert "version" in str(body(again)["field_errors"])


@pytest.mark.parametrize("version", ["uno", "1", "1.0.0 beta", "v1.0.0", "1.2.3.4.5"])
def test_a_version_looks_like_one(publisher: DMRClient, version: str) -> None:
    response = publisher.post(
        "/app-release/",
        {"link": DRIVE.format(version="x"), "platform": "android", "version": version},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    "link", ["http://drive.google.com/x", "drive.google.com/x", "https://", ""]
)
def test_the_link_is_https(publisher: DMRClient, link: str) -> None:
    response = publisher.post(
        "/app-release/", {"link": link, "platform": "android", "version": "1.0.0"}
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "link" in str(body(response)["field_errors"])


def test_publishing_makes_it_the_one_that_is_delivered(
    client: DMRClient,
    publisher: DMRClient,
) -> None:
    created = published(publisher)
    latest = body(client.get("/app-release/latest/"))

    assert created["status"] == "published"
    assert created["current"] is True
    # la landing sabe qué hay, pero el link solo llega con la solicitud de demo
    assert latest == [
        {
            "notes": "Primera versión del piloto.",
            "platform": "android",
            "published_at": created["published_at"],
            "version": "1.0.0",
        }
    ]


def test_a_newer_release_replaces_it_and_withdrawing_brings_it_back(
    client: DMRClient,
    publisher: DMRClient,
) -> None:
    first = published(publisher, "1.0.0")
    second = published(publisher, "1.1.0")

    newest = body(client.post("/demo-request/", DEMO))["links"][0]["version"]
    withdrawn = body(publisher.post(f"/app-release/{second['id']}/withdraw/"))
    back = body(client.get("/app-release/latest/"))[0]["version"]
    listed = {
        item["version"]: item["current"]
        for item in body(publisher.get("/app-release/"))["results"]
    }

    assert first["current"] is True
    assert newest == "1.1.0"
    assert withdrawn["status"] == "withdrawn"
    assert back == "1.0.0"
    assert listed == {"1.0.0": True, "1.1.0": False}


def test_a_draft_is_not_delivered(client: DMRClient, publisher: DMRClient) -> None:
    release(publisher)

    sent = body(client.post("/demo-request/", DEMO))

    assert sent == {"delivered": False, "links": []}
    assert body(client.get("/app-release/latest/")) == []


def test_publishing_twice_or_withdrawing_a_draft_conflicts(
    publisher: DMRClient,
) -> None:
    created = release(publisher)

    withdraw_draft = publisher.post(f"/app-release/{created['id']}/withdraw/")
    publisher.post(f"/app-release/{created['id']}/publish/")
    publish_again = publisher.post(f"/app-release/{created['id']}/publish/")

    assert withdraw_draft.status_code == HTTPStatus.CONFLICT
    assert publish_again.status_code == HTTPStatus.CONFLICT


def test_a_withdrawn_release_can_be_published_again(
    client: DMRClient,
    publisher: DMRClient,
) -> None:
    created = published(publisher)
    publisher.post(f"/app-release/{created['id']}/withdraw/")

    again = publisher.post(f"/app-release/{created['id']}/publish/")

    assert again.status_code == HTTPStatus.OK, again.content
    assert body(again)["withdrawn_at"] is None
    assert body(client.get("/app-release/latest/"))[0]["version"] == "1.0.0"


def test_notes_and_link_change_anytime_but_the_version_only_in_a_draft(
    publisher: DMRClient,
) -> None:
    created = release(publisher)
    renamed = publisher.patch(f"/app-release/{created['id']}/", {"version": "1.0.1"})
    publisher.post(f"/app-release/{created['id']}/publish/")

    changed = publisher.patch(
        f"/app-release/{created['id']}/",
        {"link": DRIVE.format(version="nuevo"), "notes": "Corrige el inicio."},
    )
    version = publisher.patch(f"/app-release/{created['id']}/", {"version": "2.0.0"})

    assert body(renamed)["version"] == "1.0.1"
    assert body(changed)["link"] == DRIVE.format(version="nuevo")
    assert body(changed)["notes"] == "Corrige el inicio."
    assert version.status_code == HTTPStatus.CONFLICT


def test_only_a_draft_is_deleted(publisher: DMRClient) -> None:
    draft = release(publisher, "1.0.0")
    live = published(publisher, "1.1.0")

    deleted = publisher.delete(f"/app-release/{draft['id']}/")
    refused = publisher.delete(f"/app-release/{live['id']}/")

    assert deleted.status_code == HTTPStatus.NO_CONTENT, deleted.content
    assert refused.status_code == HTTPStatus.CONFLICT
    assert list(AppRelease.objects.values_list("version", flat=True)) == ["1.1.0"]


########################################################################################
# Quién puede qué

ROUTES: list[tuple[str, str, dict | None, frozenset[str]]] = [
    ("get", "/demo-request/", None, frozenset({"demos.view", "demos.manage"})),
    (
        "patch",
        "/demo-request/{demo_id}/",
        {"status": "delivered"},
        frozenset({"demos.manage"}),
    ),
    ("get", "/app-release/", None, frozenset({"releases.view", "releases.manage"})),
    (
        "post",
        "/app-release/",
        {"link": DRIVE.format(version="9"), "platform": "macos", "version": "9.0.0"},
        frozenset({"releases.manage"}),
    ),
    (
        "post",
        "/app-release/{release_id}/publish/",
        None,
        frozenset({"releases.manage"}),
    ),
    (
        "post",
        "/app-release/{release_id}/withdraw/",
        None,
        frozenset({"releases.manage"}),
    ),
    ("delete", "/app-release/{release_id}/", None, frozenset({"releases.manage"})),
]

HOLDERS: list[str] = [
    "demos.view",
    "demos.manage",
    "releases.view",
    "releases.manage",
    "users.manage",
]


@pytest.mark.parametrize("holder", HOLDERS)
@pytest.mark.parametrize(
    ("method", "path", "payload", "allowed"),
    ROUTES,
    ids=[f"{m.upper()} {p}" for m, p, *_ in ROUTES],
)
def test_each_permission_opens_only_its_module(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
    publisher: DMRClient,
    allowed: frozenset[str],
    holder: str,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    client.post("/demo-request/", DEMO)
    ids = {
        "demo_id": DemoRequest.objects.get().pk,
        "release_id": release(publisher)["id"],
    }
    member = signed_in(make_member("miembro@example.com", holder))
    send = getattr(member, method)
    target = path.format(**ids)

    response = send(target) if payload is None else send(target, payload)

    if holder in allowed:
        assert response.status_code not in {
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        }, response.content
    else:
        assert response.status_code == HTTPStatus.FORBIDDEN, response.content
