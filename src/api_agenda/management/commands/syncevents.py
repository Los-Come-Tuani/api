from typing import override

from django.core.management.base import BaseCommand

from api_agenda.services import sync_states
from api_rewards.services.coupons import expire_sync

########################################################################################


# Lo que gobierna el calendario: los eventos que empezaron o terminaron, y las campañas
# y cupones que vencieron. Se programa una vez al día; las lecturas también lo aplican.
class Command(BaseCommand):
    help = "Pone al día los eventos de la agenda y vence campañas y cupones."

    @override
    def handle(self, *args: object, **options: object) -> None:
        sync_states()
        expire_sync()

        self.stdout.write("Agenda y cupones al día.")
