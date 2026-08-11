from http import HTTPMethod
from typing import TYPE_CHECKING

from api_exceptions.errors import ForbiddenError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Final

    from api_core.controllers.models import ModelController
    from api_utils.types import UsableHttpRequest

########################################################################################

T_ADD_PERM: Final[str] = "{app}.add_{model}"
T_CHANGE_PERM: Final[str] = "{app}.change_{model}"
T_DELETE_PERM: Final[str] = "{app}.delete_{model}"
T_VIEW_PERM: Final[str] = "{app}.view_{model}"

DEFAULT_PERMISSIONS: Final[dict[HTTPMethod, Sequence[str]]] = {
    HTTPMethod.GET: (T_VIEW_PERM,),
    HTTPMethod.POST: (T_ADD_PERM,),
    HTTPMethod.PUT: (T_CHANGE_PERM,),
    HTTPMethod.PATCH: (T_CHANGE_PERM,),
    HTTPMethod.DELETE: (T_DELETE_PERM,),
}

########################################################################################


async def ensure_model_permissions(
    controller: ModelController,
    request: UsableHttpRequest,
) -> None:
    if not hasattr(controller, "model"):
        return
    if not hasattr(request, "user"):
        return

    if request.user.is_active and request.user.is_superuser:
        return

    perms: dict[str, Sequence[str]] = getattr(
        controller, "permissions", DEFAULT_PERMISSIONS
    )

    templates: Sequence[str] | None = perms.get(request.method)

    if templates is None:
        # `request.method` does not have associated permissions.
        # this could suggest that an unacceptable method for the endpoint was sent;
        # `HandleMethodNotAllowedMixin` should have returned an error by now.
        # it could also suggest misconfigured permissions on a controller.
        # it's safer to fail fast than to fall through an empty iterator,
        # not raise anything, and continue processing a request
        # that could view/modify a protected resource.
        raise ForbiddenError(
            detail=(
                "No se pudieron determinar los permisos "
                f"asociados a una petición {request.method}."
            ),
        )

    for template in templates:
        perm = template.format_map({
            "app": controller.model._meta.app_label,  # ruff: ignore[private-member-access]
            "model": controller.model._meta.model_name,  # ruff: ignore[private-member-access]
        })

        if not await request.user.ahas_perm(perm):
            raise ForbiddenError
