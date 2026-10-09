from importlib import import_module
from typing import TYPE_CHECKING

from django.db.models.signals import post_migrate
from pglock import advisory

from api_core.config import CONFIG

if TYPE_CHECKING:
    from django.apps import AppConfig

########################################################################################


def connect_seeder(config: AppConfig, module: str) -> None:
    """
    Siembra los datos iniciales de una app después de cada `migrate`.

    `module` es el módulo con una función `execute()`; se importa al sembrar, porque al
    arrancar la app sus modelos todavía no están cargados. Con `SKIP_SEEDERS` no hace
    nada. Un candado asesor evita que dos procesos que migran a la vez siembren al mismo
    tiempo; quien no lo consigue simplemente sigue.
    """

    def receiver(*args, **kwargs) -> None:  # ruff: ignore[missing-type-args, missing-type-kwargs, unused-function-argument]
        if CONFIG.SKIP_SEEDERS:
            return

        with advisory(lock_id=f"{config.name}.seedcaller", timeout=0) as acquired:
            if acquired:
                import_module(module).execute()

    # `weak=False`: el receptor es una función local y se recogería como basura
    post_migrate.connect(
        dispatch_uid=f"{config.name}.seedcaller",
        receiver=receiver,
        sender=config,
        weak=False,
    )
