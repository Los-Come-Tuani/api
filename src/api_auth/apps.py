from typing import override

from django.apps import AppConfig
from django.core.management import call_command
from django.db.models.signals import post_migrate
from pglock import advisory

########################################################################################


def apiauth_seedcaller(*args, **kwargs) -> None:  # ruff: ignore[missing-type-args, missing-type-kwargs, unused-function-argument]
    with advisory(lock_id="api_auth.seedcaller", timeout=0) as acquired:
        if not acquired:
            return

        call_command(command_name="apiauthseed")


########################################################################################


class ApiAuth(AppConfig):
    name = "api_auth"
    label = "apiauth"

    @override
    def ready(self) -> None:
        post_migrate.connect(receiver=apiauth_seedcaller, sender=self)
