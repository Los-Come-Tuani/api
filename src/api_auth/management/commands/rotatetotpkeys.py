from typing import override

from django.core.management.base import BaseCommand
from django.db.transaction import atomic
from pglock import Skip, advisory
from pgtrigger import ignore

from api_auth.models import ApiUserTotpDevice
from api_auth.services.crypto import rotate_secret, uses_primary_key

########################################################################################


class Command(BaseCommand):
    help = (
        "Vuelve a cifrar los secretos TOTP con la llave primaria de "
        "`TOTP_ENCRYPTION_KEYS` (la primera de la lista) para poder retirar las viejas."
    )

    @advisory(lock_id="api_auth.rotatetotpkeys", side_effect=Skip, timeout=0)
    @override
    def handle(self, *args: str, **options: str) -> None:
        rotated = 0

        # un secreto confirmado no se puede reescribir (`trg_..._protect_secret`);
        # aquí cambia solo el cifrado, nunca el valor del secreto
        with (
            atomic(),
            ignore("apiauth.ApiUserTotpDevice:trg_apiusertotpdevice_protect_secret"),
        ):
            for device in ApiUserTotpDevice.objects.select_for_update().iterator():
                if uses_primary_key(device.secret):
                    continue

                ApiUserTotpDevice.objects.filter(pk=device.pk).update(
                    secret=rotate_secret(device.secret),
                )

                rotated += 1

        self.stdout.write(msg=f"Se volvieron a cifrar {rotated} secretos.")
