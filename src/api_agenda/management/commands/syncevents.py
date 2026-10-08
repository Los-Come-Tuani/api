from typing import override

from django.core.management.base import BaseCommand

from api_agenda.services import sync_states
from api_reports.services import expire_sanctions
from api_rewards.services.coupons import expire_sync
from api_services.services.requests import expire_requests

########################################################################################


# Lo que gobierna el calendario: los eventos que empezaron o terminaron, las campañas y
# cupones que vencieron, las convocatorias cuya fecha pasó y las suspensiones que
# terminaron. Se programa una vez al día; las lecturas también lo aplican.
class Command(BaseCommand):
    help = (
        "Pone al día la agenda, vence campañas, cupones y convocatorias, y levanta las "
        "suspensiones que terminaron."
    )

    @override
    def handle(self, *args: object, **options: object) -> None:
        sync_states()
        expire_sync()
        expire_requests()
        lifted: int = expire_sanctions()

        self.stdout.write(f"Todo al día; suspensiones levantadas: {lifted}.")
