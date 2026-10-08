from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiFinance(AppConfig):
    name = "api_finance"
    label = "apifinance"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_finance.seeder")
