from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiServices(AppConfig):
    name = "api_services"
    label = "apiservices"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_services.seeder")
