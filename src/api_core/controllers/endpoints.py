from collections.abc import Sequence
from http import HTTPMethod
from typing import Final, override

from dmr.endpoint import Endpoint
from dmr.openapi import OpenAPIContext
from dmr.serializer import BaseSerializer

########################################################################################

COLLECTION_ACTIONS: Final[dict[str, str]] = {
    HTTPMethod.DELETE: "clear",
    HTTPMethod.GET: "list",
    HTTPMethod.PATCH: "merge",
    HTTPMethod.POST: "create",
    HTTPMethod.PUT: "replace",
}

INSTANCE_ACTIONS: Final[dict[str, str]] = {
    HTTPMethod.DELETE: "destroy",
    HTTPMethod.GET: "retrieve",
    HTTPMethod.PATCH: "modify",
    HTTPMethod.POST: "append",
    HTTPMethod.PUT: "update",
}

########################################################################################


class PathOperationIdEndpoint(Endpoint):
    __slots__ = ()

    def is_instance_path(self, path: str) -> bool:  # ruff: ignore[no-self-use]
        parts: Sequence[str] = tuple(part for part in path.split(sep="/") if part)

        return bool(parts) and parts[-1].startswith("{")

    def get_action(self, path: str) -> str:  # ruff: ignore[unused-method-argument]
        return self.metadata.method.lower()

    def get_segments(self, path: str) -> Sequence[str]:  # ruff: ignore[no-self-use]
        return tuple(
            part for part in path.split(sep="/") if part and not part.startswith("{")
        )

    @override
    def get_operation_id(
        self,
        path: str,
        controller_name: str,
        serializer: type[BaseSerializer],
        context: OpenAPIContext,
    ) -> str:
        if self.metadata.operation_id is not None:
            return context.generators.operation_id(
                path,
                controller_name,
                self.metadata,
                serializer,
            )

        operation_id: str = "-".join((
            *self.get_segments(path),
            self.get_action(path),
        ))

        try:
            context.registries.operation_id.register(operation_id)
        except ValueError as v:
            raise ValueError(
                f"{controller_name} genera el operation id duplicado "
                f"'{operation_id}' para {self.metadata.method} {path}.",
            ) from v

        return operation_id


class ModelOperationIdEndpoint(PathOperationIdEndpoint):
    __slots__ = ()

    @override
    def get_action(self, path: str) -> str:
        method: str = self.metadata.method.upper()

        actions: dict[str, str] = (
            INSTANCE_ACTIONS if self.is_instance_path(path) else COLLECTION_ACTIONS
        )

        return actions.get(method, method.lower())
