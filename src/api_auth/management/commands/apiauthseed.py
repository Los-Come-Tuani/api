from typing import override

from django.core.management.base import BaseCommand

import api_auth.seeder

from api_core.config import CONFIG

########################################################################################


class Command(BaseCommand):
    help = "Popular la base de datos con datos iniciales de grupos y permisos."

    @override
    def handle(self, *args, **options) -> None:  # ruff: ignore[missing-type-args, missing-type-kwargs]
        if CONFIG.SKIP_SEEDERS:
            return

        self.stdout.write(msg="Configurando grupos y permisos...")

        api_auth.seeder.execute()

        self.stdout.write(
            msg=self.style.SUCCESS("Grupos y permisos configurados con éxito.")
        )
