from typing import override

from django.apps import AppConfig, apps
from django.core.management import call_command
from django.db.models.signals import post_migrate

from api_core.config import CONFIG
from api_utils.seeding import connect_seeder

########################################################################################


# Al desplegar, `migrate` termina con el contenido de ejemplo (`--on-deploy` decide si
# le toca a este despliegue): así no depende del comando previo que tenga Railway.
def seed_content(*_: object, **__: object) -> None:
    if CONFIG.DEPLOY and not CONFIG.SKIP_SEEDERS:
        call_command("seedcontent", "--on-deploy")


class ApiTerritory(AppConfig):
    name = "api_territory"
    label = "apiterritory"

    @override
    def ready(self) -> None:
        connect_seeder(self, "api_territory.seeder")

        # tras la última app con modelos: para entonces todas sembraron sus catálogos
        last: AppConfig = [
            config for config in apps.get_app_configs() if config.models_module
        ][-1]
        post_migrate.connect(
            dispatch_uid=f"{self.name}.seedcontent",
            receiver=seed_content,
            sender=last,
            weak=False,
        )
