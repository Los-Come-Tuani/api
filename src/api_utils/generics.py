from typing import TYPE_CHECKING, TypeVar, get_args, get_origin

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

    from api_core.controllers.models import ModelController

########################################################################################

DERIVED_ATTRS: Final[dict[str, str]] = {
    "Get": "schema",
    "Model": "model",
    "ModelFilter": "filterset",
}

########################################################################################


def resolve_type_args(
    cls: type[ModelController],
    root: type[ModelController],
) -> tuple[dict[str, type], set[str]]:
    resolved: dict[str, type] = {}

    expected: set[str] = set()

    for base in cls.__dict__.get("__orig_bases__", ()):
        origin: type | None = get_origin(tp=base)

        if (
            origin is None
            or not isinstance(origin, type)
            or not issubclass(origin, root)
        ):
            continue

        params: Sequence[TypeVar] = getattr(origin, "__type_params__", ())

        for param, arg in zip(params, get_args(tp=base), strict=False):
            attr: str | None = DERIVED_ATTRS.get(param.__name__)

            if attr is None:
                continue

            expected.add(attr)

            if not isinstance(arg, TypeVar) and isinstance(arg, type):
                resolved[attr] = arg

    return resolved, expected
