from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiCatalogs(AppConfig):
    name = "api_catalogs"
    label = "apicatalogs"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_catalogs.seeder")
