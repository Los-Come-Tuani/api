from http import HTTPStatus
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from asgiref.sync import async_to_sync
from dmr.test import DMRAsyncRequestFactory, assert_async_throttling
from dmr.throttling import Rate

from api_auth.models import ApiUser
from api_core.services import storage as storage_module
from api_core.services.storage import MemoryStorage
from api_landing.controllers import DemoRequestController
from api_landing.models import AppRelease, DemoRequest
from api_landing.services import INSTALLER_MAX_BYTES, NO_RELEASE_DETAIL
from api_notifications.models import Notification
from api_tests.helpers import PASSWORD, body
from api_tests.territory_helpers import signed_in, tourist

if TYPE_CHECKING:
    from collections.abc import Callable

    from dmr.test import DMRClient
    from pytest_django import DjangoCaptureOnCommitCallbacks

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

APK: str = "application/vnd.android.package-archive"


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    storage = MemoryStorage()
    monkeypatch.setattr(storage_module, "current", storage)

    return storage


@pytest.fixture
def publisher(make_member: Callable[..., ApiUser]) -> DMRClient:
    return signed_in(make_member("versiones@example.com", "releases.manage"))


def uploaded(
    publisher: DMRClient,
    memory: MemoryStorage,
    platform: str = "android",
    size: int = 40_000_000,
) -> str:
    signed = body(
        publisher.post("/app-release/upload/", {"platform": platform, "size": size})
    )
    memory.put(signed["key"], content_type=signed["headers"]["Content-Type"], size=size)

    return signed["key"]


def release(
    publisher: DMRClient,
    memory: MemoryStorage,
    version: str = "1.0.0",
    platform: str = "android",
) -> dict:
    response = publisher.post(
        "/app-release/",
        {
            "file": uploaded(publisher, memory, platform),
            "notes": "Primera versión del piloto.",
            "platform": platform,
            "version": version,
        },
    )

    assert response.status_code == HTTPStatus.CREATED, response.content

    return body(response)


########################################################################################
# Pedir una demo desde la landing


def test_anyone_asks_for_a_demo_and_the_team_sees_it(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    sent = client.post("/demo-request/", DEMO)
    team = signed_in(make_member("ventas@example.com", "demos.view"))
    queue = body(team.get("/demo-request/"))

    assert sent.status_code == HTTPStatus.NO_CONTENT, sent.content
    assert queue["elements"] == 1
    item = queue["results"][0]
    assert item["email"] == "lucia@ejemplo.com"
    assert item["kind"] == "business"
    assert item["organization"] == "Café Sacuanjoche"
    assert item["status"] == "new"
    assert item["updated_by"] is None


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


def test_a_bot_that_fills_the_trap_is_answered_but_ignored(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    make_member("atiende@example.com", "demos.manage")

    response = client.post(
        "/demo-request/", {**DEMO, "website": "https://spam.example"}
    )

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert not DemoRequest.objects.exists()
    assert not Notification.objects.exists()


def test_sending_it_again_corrects_the_pending_one(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    attends = make_member("atiende@example.com", "demos.manage")

    client.post("/demo-request/", DEMO)
    client.post("/demo-request/", {**DEMO, "message": "Mejor el jueves."})

    assert DemoRequest.objects.get().message == "Mejor el jueves."
    assert Notification.objects.filter(user=attends).count() == 1


def test_once_attended_a_new_request_opens_another(client: DMRClient) -> None:
    client.post("/demo-request/", DEMO)
    DemoRequest.objects.update(status="realizada")

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
        success_status=HTTPStatus.NO_CONTENT,
    )


########################################################################################
# La bandeja del equipo


def test_the_queue_filters_by_status_and_search(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    client.post("/demo-request/", DEMO)
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
    DemoRequest.objects.filter(email="marta@alcaldia.example").update(status="agendada")
    team = signed_in(make_member("ventas@example.com", "demos.view"))

    scheduled = body(team.get("/demo-request/", {"status": "scheduled"}))
    found = body(team.get("/demo-request/", {"search": "cafe"}))

    assert [item["name"] for item in scheduled["results"]] == ["Marta Ruiz"]
    assert [item["name"] for item in found["results"]] == ["Lucía Martínez"]


def test_attending_a_request_records_status_notes_and_who(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    client.post("/demo-request/", DEMO)
    request = DemoRequest.objects.get()
    team = signed_in(make_member("ventas@example.com", "demos.manage"))

    response = team.patch(
        f"/demo-request/{request.pk}/",
        {"notes": "Llamada el lunes a las 10.", "status": "scheduled"},
    )

    assert response.status_code == HTTPStatus.OK, response.content
    updated = body(response)
    assert updated["status"] == "scheduled"
    assert updated["notes"] == "Llamada el lunes a las 10."
    assert updated["updated_by"] is not None
    assert updated["updated_at"] is not None
    assert body(team.get(f"/demo-request/{request.pk}/"))["status"] == "scheduled"


def test_only_who_attends_changes_a_request(
    client: DMRClient,
    make_member: Callable[..., ApiUser],
) -> None:
    client.post("/demo-request/", DEMO)
    request = DemoRequest.objects.get()
    viewer = signed_in(make_member("mira@example.com", "demos.view"))

    response = viewer.patch(f"/demo-request/{request.pk}/", {"status": "dismissed"})

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert DemoRequest.objects.get().status == "nueva"


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
# Subir y publicar versiones


def test_a_publisher_gets_a_signed_upload_for_the_installer(
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    publisher: DMRClient,
) -> None:
    response = publisher.post(
        "/app-release/upload/", {"platform": "android", "size": 40_000_000}
    )

    assert response.status_code == HTTPStatus.CREATED, response.content
    signed = body(response)
    assert signed["key"].startswith("app-installer/android/")
    assert signed["key"].endswith(".apk")
    assert signed["headers"] == {"Content-Type": APK}
    assert signed["max_bytes"] == INSTALLER_MAX_BYTES


def test_an_installer_has_a_size_limit(
    memory: MemoryStorage,  # ruff: ignore[unused-function-argument]
    publisher: DMRClient,
) -> None:
    response = publisher.post(
        "/app-release/upload/",
        {"platform": "windows", "size": INSTALLER_MAX_BYTES + 1},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "size" in str(body(response)["field_errors"])


def test_without_a_bucket_there_is_nothing_to_upload(publisher: DMRClient) -> None:
    response = publisher.post(
        "/app-release/upload/", {"platform": "android", "size": 1000}
    )

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


def test_a_new_release_starts_as_a_draft(
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)

    assert created["status"] == "draft"
    assert created["current"] is False
    assert created["file_name"] == "kplan-1.0.0.apk"
    assert created["size"] == 40_000_000
    assert body(publisher.get("/app-release/"))["elements"] == 1


def test_a_version_is_unique_per_platform(
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    release(publisher, memory, "1.0.0", "android")
    release(publisher, memory, "1.0.0", "windows")

    again = publisher.post(
        "/app-release/",
        {
            "file": uploaded(publisher, memory),
            "platform": "android",
            "version": "1.0.0",
        },
    )

    assert again.status_code == HTTPStatus.CONFLICT
    assert "version" in str(body(again)["field_errors"])


@pytest.mark.parametrize("version", ["uno", "1", "1.0.0 beta", "v1.0.0", "1.2.3.4.5"])
def test_a_version_looks_like_one(
    memory: MemoryStorage,
    publisher: DMRClient,
    version: str,
) -> None:
    response = publisher.post(
        "/app-release/",
        {
            "file": uploaded(publisher, memory),
            "platform": "android",
            "version": version,
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_release_only_points_to_its_own_installer(
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    windows = uploaded(publisher, memory, "windows")
    memory.put("place-photo/foto.jpg", content_type="image/jpeg")
    fake = "app-installer/android/inventado.apk"
    wrong_type = "app-installer/android/otro.apk"
    memory.put(wrong_type, content_type="application/zip")

    responses = [
        publisher.post(
            "/app-release/",
            {"file": key, "platform": "android", "version": "1.0.0"},
        )
        for key in (windows, "place-photo/foto.jpg", fake, wrong_type)
    ]

    assert [r.status_code for r in responses] == [HTTPStatus.BAD_REQUEST] * 4


def test_publishing_makes_it_the_download_of_the_landing(
    client: DMRClient,
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)

    published = body(publisher.post(f"/app-release/{created['id']}/publish/"))
    latest = body(client.get("/app-release/latest/"))
    download = client.get("/app-release/latest/android/download/")

    assert published["status"] == "published"
    assert published["current"] is True
    assert latest == [
        {
            "file_name": "kplan-1.0.0.apk",
            "notes": "Primera versión del piloto.",
            "platform": "android",
            "published_at": published["published_at"],
            "size": 40_000_000,
            "version": "1.0.0",
        }
    ]
    assert download.status_code == HTTPStatus.FOUND, download.content
    assert download["Location"].startswith("https://storage.example/bucket/")
    assert download["Location"].endswith("filename=kplan-1.0.0.apk")
    assert AppRelease.objects.get().downloads == 1


def test_a_newer_release_replaces_it_and_withdrawing_brings_it_back(
    client: DMRClient,
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    first = release(publisher, memory, "1.0.0")
    second = release(publisher, memory, "1.1.0")
    publisher.post(f"/app-release/{first['id']}/publish/")
    publisher.post(f"/app-release/{second['id']}/publish/")

    newest = body(client.get("/app-release/latest/"))[0]["version"]
    withdrawn = body(publisher.post(f"/app-release/{second['id']}/withdraw/"))
    back = body(client.get("/app-release/latest/"))[0]["version"]
    listed = {
        item["version"]: item["current"]
        for item in body(publisher.get("/app-release/"))["results"]
    }

    assert newest == "1.1.0"
    assert withdrawn["status"] == "withdrawn"
    assert back == "1.0.0"
    assert listed == {"1.0.0": True, "1.1.0": False}


def test_each_platform_has_its_own_download(
    client: DMRClient,
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    android = release(publisher, memory, "1.0.0", "android")
    windows = release(publisher, memory, "0.9.0", "windows")
    publisher.post(f"/app-release/{android['id']}/publish/")
    publisher.post(f"/app-release/{windows['id']}/publish/")

    latest = body(client.get("/app-release/latest/"))
    download = client.get("/app-release/latest/windows/download/")

    assert [item["platform"] for item in latest] == ["android", "windows"]
    assert download["Location"].endswith("filename=kplan-0.9.0.exe")


def test_without_a_release_there_is_nothing_to_download(client: DMRClient) -> None:
    response = client.get("/app-release/latest/macos/download/")

    assert body(client.get("/app-release/latest/")) == []
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert body(response)["detail"] == NO_RELEASE_DETAIL


def test_an_unknown_platform_is_rejected(client: DMRClient) -> None:
    response = client.get("/app-release/latest/ios/download/")

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_a_draft_is_not_downloaded_from_the_landing(
    client: DMRClient,
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    release(publisher, memory)

    response = client.get("/app-release/latest/android/download/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_the_team_downloads_a_draft_without_counting_it(
    memory: MemoryStorage,
    make_member: Callable[..., ApiUser],
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)
    viewer = signed_in(make_member("mira@example.com", "releases.view"))

    response = viewer.get(f"/app-release/{created['id']}/download/")

    assert response.status_code == HTTPStatus.OK, response.content
    assert body(response)["url"].endswith("filename=kplan-1.0.0.apk")
    assert AppRelease.objects.get().downloads == 0


def test_publishing_twice_or_withdrawing_a_draft_conflicts(
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)

    withdraw_draft = publisher.post(f"/app-release/{created['id']}/withdraw/")
    publisher.post(f"/app-release/{created['id']}/publish/")
    publish_again = publisher.post(f"/app-release/{created['id']}/publish/")

    assert withdraw_draft.status_code == HTTPStatus.CONFLICT
    assert publish_again.status_code == HTTPStatus.CONFLICT


def test_a_missing_installer_is_not_published(
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)
    memory.objects.clear()

    response = publisher.post(f"/app-release/{created['id']}/publish/")

    assert response.status_code == HTTPStatus.CONFLICT
    assert AppRelease.objects.get().status == "borrador"


def test_a_withdrawn_release_can_be_published_again(
    client: DMRClient,
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)
    publisher.post(f"/app-release/{created['id']}/publish/")
    publisher.post(f"/app-release/{created['id']}/withdraw/")

    again = publisher.post(f"/app-release/{created['id']}/publish/")

    assert again.status_code == HTTPStatus.OK, again.content
    assert body(again)["withdrawn_at"] is None
    assert body(client.get("/app-release/latest/"))[0]["version"] == "1.0.0"


def test_notes_change_anytime_but_the_version_only_in_a_draft(
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    created = release(publisher, memory)
    renamed = publisher.patch(f"/app-release/{created['id']}/", {"version": "1.0.1"})
    publisher.post(f"/app-release/{created['id']}/publish/")

    notes = publisher.patch(
        f"/app-release/{created['id']}/", {"notes": "Corrige el inicio de sesión."}
    )
    version = publisher.patch(f"/app-release/{created['id']}/", {"version": "2.0.0"})

    assert body(renamed)["file_name"] == "kplan-1.0.1.apk"
    assert body(notes)["notes"] == "Corrige el inicio de sesión."
    assert version.status_code == HTTPStatus.CONFLICT


def test_only_a_draft_is_deleted_with_its_installer(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    memory: MemoryStorage,
    publisher: DMRClient,
) -> None:
    draft = release(publisher, memory, "1.0.0")
    live = release(publisher, memory, "1.1.0")
    publisher.post(f"/app-release/{live['id']}/publish/")
    key = AppRelease.objects.get(pk=draft["id"]).file_key

    with django_capture_on_commit_callbacks(execute=True):
        deleted = publisher.delete(f"/app-release/{draft['id']}/")

    refused = publisher.delete(f"/app-release/{live['id']}/")

    assert deleted.status_code == HTTPStatus.NO_CONTENT, deleted.content
    assert key not in memory.objects
    assert refused.status_code == HTTPStatus.CONFLICT
    assert list(AppRelease.objects.values_list("version", flat=True)) == ["1.1.0"]


########################################################################################
# Quién puede qué

ROUTES: list[tuple[str, str, dict | None, frozenset[str]]] = [
    ("get", "/demo-request/", None, frozenset({"demos.view", "demos.manage"})),
    (
        "patch",
        "/demo-request/{demo_id}/",
        {"status": "contacted"},
        frozenset({"demos.manage"}),
    ),
    ("get", "/app-release/", None, frozenset({"releases.view", "releases.manage"})),
    (
        "post",
        "/app-release/upload/",
        {"platform": "android", "size": 1000},
        frozenset({"releases.manage"}),
    ),
    (
        "get",
        "/app-release/{release_id}/download/",
        None,
        frozenset({"releases.view", "releases.manage"}),
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
    memory: MemoryStorage,
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
        "release_id": release(publisher, memory)["id"],
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
