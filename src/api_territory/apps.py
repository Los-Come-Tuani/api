from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiTerritory(AppConfig):
    name = "api_territory"
    label = "apiterritory"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_territory.seeder")
