from typing import override

from django.apps import AppConfig
from django.db.models import CharField, TextField
from django.db.models.functions import Length

from api_utils.db import ImmutableUnaccent

########################################################################################


class ApiCore(AppConfig):
    name = "api_core"
    label = "apicore"

    @override
    def ready(self) -> None:
        import api_core.checks  # ruff: ignore[import-outside-top-level, unused-import]

        CharField.register_lookup(lookup=ImmutableUnaccent)
        CharField.register_lookup(lookup=Length, lookup_name="len")
        TextField.register_lookup(lookup=ImmutableUnaccent)
        TextField.register_lookup(lookup=Length, lookup_name="len")
