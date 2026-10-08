from typing import override

from django.apps import AppConfig

from api_utils.seeding import connect_seeder

########################################################################################


class ApiRewards(AppConfig):
    name = "api_rewards"
    label = "apirewards"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_rewards.seeder")
