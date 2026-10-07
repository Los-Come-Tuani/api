from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_auth.catalog import FunctionalPermissions as P
from api_auth.schemas.directory import AccountGet, AccountPatch, AccountQuery
from api_auth.services.directory import (
    account_sync,
    accounts_sync,
    update_account_sync,
)
from api_auth.services.roles import ensure_permission, functional_permissions
from api_core.controllers.base import BaseController
from api_core.controllers.components import StrictQuery
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.pagination import Paginated
from api_core.schemas.path import UuidInstancePath

########################################################################################
# El directorio de cuentas ("Todos los usuarios" del portal). Con `users.view` se ven
# todas; con `staff.manage` solo el equipo. Suspender, reactivar, cambiar el rol del
# equipo y mandar un código de contraseña siguen en sus rutas (`docs/roles.md`).

VIEW: tuple[str, ...] = (P.USERS_VIEW, P.STAFF_MANAGE)


class AccountController(BaseController[CustomPydanticFastSerializer]):
    # list, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(
        self, parsed_query: StrictQuery[AccountQuery]
    ) -> Paginated[AccountGet]:
        await ensure_permission(self.request.user, *VIEW)

        held: frozenset[str] = await functional_permissions(self.request.user)

        return await sync_to_async(accounts_sync)(
            parsed_query,
            sees_everyone=P.USERS_VIEW in held,
        )


class AccountDetailController(BaseController[CustomPydanticFastSerializer]):
    # retrieve / update, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[UuidInstancePath]) -> AccountGet:
        await ensure_permission(self.request.user, *VIEW)

        held: frozenset[str] = await functional_permissions(self.request.user)

        return await sync_to_async(account_sync)(
            parsed_path.id,
            sees_everyone=P.USERS_VIEW in held,
        )

    @modify(status_code=HTTPStatus.OK)
    async def patch(
        self,
        parsed_body: Body[AccountPatch],
        parsed_path: Path[UuidInstancePath],
    ) -> AccountGet:
        await ensure_permission(self.request.user, P.USERS_MANAGE, P.STAFF_MANAGE)

        return await sync_to_async(update_account_sync)(
            parsed_path.id,
            parsed_body,
            actor=self.request.user,
            held=await functional_permissions(self.request.user),
        )
