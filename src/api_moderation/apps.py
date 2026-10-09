from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiModeration(AppConfig):
    name = "api_moderation"
    label = "apimoderation"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_moderation.seeder")
