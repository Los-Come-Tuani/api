from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiProfiles(AppConfig):
    name = "api_profiles"
    label = "apiprofiles"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_profiles.seeder")
