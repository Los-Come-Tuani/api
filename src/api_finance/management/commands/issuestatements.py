from datetime import date, datetime
from typing import TYPE_CHECKING, Any, override

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import localdate

from api_finance.services.statements import issue_statements, previous_month

if TYPE_CHECKING:
    from argparse import ArgumentParser

########################################################################################


# Emite los estados de cuenta de un mes (por defecto, el que acaba de terminar). Se
# programa una vez al mes; correrlo dos veces no duplica nada.
class Command(BaseCommand):
    help = "Emite los estados de cuenta mensuales de los comercios."

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--period", help="El mes que se cobra, como 2026-10.")

    @override
    def handle(self, *args: object, **options: Any) -> None:
        if options["period"]:
            try:
                period: date = datetime.strptime(options["period"], "%Y-%m").date()  # ruff: ignore[call-datetime-strptime-without-zone]
            except ValueError as v:
                raise CommandError("El periodo va como AAAA-MM.") from v
        else:
            period = previous_month(localdate())

        issued: int = issue_statements(period)

        self.stdout.write(f"Estados de cuenta emitidos para {period:%Y-%m}: {issued}")
