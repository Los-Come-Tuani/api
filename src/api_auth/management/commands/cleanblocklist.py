from datetime import UTC, datetime
from typing import override

from django.core.management.base import BaseCommand
from dmr.security.jwt.blocklist.models import BlocklistedJWToken
from pglock import Skip, advisory

########################################################################################


class Command(BaseCommand):
    @advisory(lock_id="api_auth.cleanblocklist", side_effect=Skip, timeout=0)
    @override
    def handle(self, *args: str, **options: str) -> None:
        deleted, _ = BlocklistedJWToken.objects.filter(  # ty:ignore[unresolved-attribute]
            expires_at__lt=datetime.now(tz=UTC),
        ).delete()

        self.stdout.write(msg=f"Se eliminaron {deleted} tokens expirados.")
