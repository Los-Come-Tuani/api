from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiAgenda(AppConfig):
    name = "api_agenda"
    label = "apiagenda"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_agenda.seeder")
