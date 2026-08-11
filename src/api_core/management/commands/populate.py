from typing import override

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.transaction import atomic

from api_core.config import CONFIG

########################################################################################


class Command(BaseCommand):
    help = "Popular la base de datos local con datos de prueba."

    @override
    def handle(self, *args: str, **options: str) -> None:
        if not CONFIG.DEBUG:
            raise CommandError(
                "Este comando solo se puede ejecutar en ambientes de desarrollo.",
            )

        if CONFIG.SKIP_SEEDERS:
            return

        self.stdout.write(msg="Verificando estado de migraciones...")

        executor = MigrationExecutor(connection)

        nodes: set = executor.loader.graph.leaf_nodes()

        if executor.migration_plan(targets=nodes):
            raise CommandError("Hay migraciones sin aplicar.")

        self.stdout.write(msg=self.style.SUCCESS("Migraciones al día."))

        self.populate()

        self.stdout.write(msg=self.style.SUCCESS("Base de datos populada."))

    @atomic
    def populate(self) -> None:
        pass
