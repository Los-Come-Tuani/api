from typing import TYPE_CHECKING

from django.apps import apps
from django.core.checks import (
    Error as CheckError,
    Tags,
    register,
)

from api_core.models.base import ApiModel

if TYPE_CHECKING:
    from pgtrigger import Trigger

########################################################################################


@register(check=Tags.models)
def check_api_model_triggers(
    *args,  # ruff: ignore[missing-type-args, unused-function-argument]
    **kwargs,  # ruff: ignore[missing-type-kwargs, unused-function-argument]
) -> list[CheckError]:
    base_triggers: set[Trigger] = set(getattr(ApiModel.Meta, "triggers", ()))

    errors = []

    for model in apps.get_models():
        if issubclass(model, ApiModel) and not model._meta.abstract:
            subcls_triggers: set[Trigger] = set(
                model._meta.original_attrs.get("triggers", ())
            )

            if not base_triggers.issubset(subcls_triggers):
                errors.append(
                    CheckError(
                        id="api_core.E001",
                        hint=(
                            "Añade `*ApiModel.Meta.triggers,` "
                            "al definir nuevos triggers en `Meta`."
                        ),
                        msg=(
                            "Modelos concretos con custom triggers "
                            "deben heredar `ApiModel.Meta.triggers`."
                        ),
                        obj=model,
                    )
                )

    return errors
