from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiItineraries(AppConfig):
    name = "api_itineraries"
    label = "apiitineraries"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_itineraries.seeder")
