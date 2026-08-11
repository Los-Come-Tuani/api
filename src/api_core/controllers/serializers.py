from typing import override

from dmr.plugins.pydantic import PydanticFastSerializer, PydanticSerializer
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import ErrorDetails

########################################################################################


class CustomPydanticSerializer(PydanticSerializer):
    @classmethod
    @override
    def serialize_validation_error(
        cls,
        exc: Exception,
    ) -> list[ErrorDetails]:  # ty:ignore[invalid-method-override]
        if isinstance(exc, PydanticValidationError):
            return exc.errors(include_url=False)

        raise RuntimeError(
            f"Cannot serialize exception {exc!r} of type {type(exc)} safely.",
        )


########################################################################################


class CustomPydanticFastSerializer(
    CustomPydanticSerializer,
    PydanticFastSerializer,
):
    pass
