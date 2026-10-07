from typing import override

from django.core.management.base import BaseCommand
from django.utils.timezone import localdate
from pglock import Skip, advisory

from api_profiles.services.expiry import expire_credentials_sync

########################################################################################


class Command(BaseCommand):
    help = (
        "Vence los documentos de guías y traductores cuya fecha ya pasó y suspende a "
        "quien se queda sin alguno de los que se le piden. Se corre una vez al día."
    )

    @advisory(lock_id="api_profiles.expirecredentials", side_effect=Skip, timeout=0)
    @override
    def handle(self, *args: str, **options: str) -> None:
        report = expire_credentials_sync(localdate())

        self.stdout.write(
            msg=(
                f"Vencieron {report.expired} documentos; se suspendió a "
                f"{len(report.suspended)} prestadores."
            )
        )
