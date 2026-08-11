from typing import Annotated

from pydantic import create_model

from api_core.schemas.get import DTO

########################################################################################


def build_patch_schema[Put: type[DTO]](dto: Put) -> Put:
    kwargs: dict = {"__base__": dto} | {
        name: (
            (
                field.annotation
                if not field.metadata
                else Annotated[field.annotation, *field.metadata]
            ),
            None,
        )
        for name, field in dto.model_fields.items()
    }

    return create_model(
        dto.__name__.replace("Put", "Patch"),
        **kwargs,
    )


########################################################################################


def build_put_schema[Post: type[DTO]](dto: Post) -> Post:
    kwargs: dict = {"__base__": dto}

    return create_model(
        dto.__name__.replace("Post", "Put").replace("Write", "Put"),
        **kwargs,
    )
