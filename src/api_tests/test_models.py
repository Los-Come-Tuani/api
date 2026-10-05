from typing import TYPE_CHECKING

import pytest

from django.core.management import call_command
from django.db import IntegrityError, ProgrammingError, transaction

from api_auth.models import ApiUser
from api_tests.helpers import PASSWORD

if TYPE_CHECKING:
    from collections.abc import Callable

########################################################################################

pytestmark = pytest.mark.django_db

########################################################################################


def test_create_user_normalizes_the_email_and_verifies_an_active_account() -> None:
    user = ApiUser.objects.create_user(email="  Ana@Example.COM ", password=PASSWORD)

    assert user.email == "ana@example.com"
    assert user.status == "active"
    assert user.is_active
    assert user.verified_at is not None
    assert user.username is None
    assert user.check_password(PASSWORD)


def test_a_pending_account_is_inactive_and_unverified() -> None:
    user = ApiUser.objects.create_user(
        email="pendiente@example.com",
        password=PASSWORD,
        status="pending",
    )

    assert not user.is_active
    assert user.verified_at is None


def test_a_user_without_password_has_an_unusable_one() -> None:
    user = ApiUser.objects.create_user(email="google@example.com", password=None)

    assert not user.has_usable_password()


def test_creating_a_user_without_email_fails() -> None:
    with pytest.raises(ValueError, match="email"):
        ApiUser.objects.create_user(email="", password=PASSWORD)


def test_display_name_falls_back_to_the_local_part_of_the_email(
    make_user: Callable[..., ApiUser],
) -> None:
    anonymous = make_user(email="sin.nombre@example.com")
    named = make_user(email="ana@example.com", first_name="Ana", last_name="Gómez")

    assert anonymous.display_name == "sin.nombre"
    assert named.display_name == "Ana Gómez"


def test_users_can_only_be_inserted_through_the_manager() -> None:
    # el trigger `trg_apiuser_protect_insert` guarda que la contraseña llegue con hash
    with pytest.raises(ProgrammingError, match="Cannot insert"), transaction.atomic():
        ApiUser.objects.create(email="directo@example.com", password="en-claro")


def test_the_database_rejects_a_duplicated_email(
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(email="ana@example.com")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_user(email="ana@example.com")


def test_the_database_rejects_an_email_that_is_not_lowercase(
    user: ApiUser,
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ApiUser.objects.filter(pk=user.pk).update(email="ANA@EXAMPLE.COM")


def test_many_users_can_have_no_username_but_not_a_blank_or_repeated_one(
    make_user: Callable[..., ApiUser],
) -> None:
    make_user(email="a@example.com")
    make_user(email="b@example.com")
    taken = make_user(email="c@example.com", username="ana")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_user(email="d@example.com", username="ana")

    with pytest.raises(IntegrityError), transaction.atomic():
        ApiUser.objects.filter(pk=taken.pk).update(username="")


def test_is_active_cannot_disagree_with_the_status(user: ApiUser) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ApiUser.objects.filter(pk=user.pk).update(is_active=False)

    with pytest.raises(IntegrityError), transaction.atomic():
        ApiUser.objects.filter(pk=user.pk).update(status="suspended")

    with pytest.raises(IntegrityError), transaction.atomic():
        ApiUser.objects.filter(pk=user.pk).update(status="inexistente", is_active=False)


def test_createsuperuser_uses_the_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", PASSWORD)

    call_command("createsuperuser", email="root@example.com", interactive=False)

    root = ApiUser.objects.get(email="root@example.com")
    assert root.is_superuser
    assert root.is_staff
    assert root.is_active
    assert root.check_password(PASSWORD)
