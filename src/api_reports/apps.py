from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiReports(AppConfig):
    name = "api_reports"
    label = "apireports"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_reports.seeder")
