from http import HTTPStatus
from typing import ClassVar

from asgiref.sync import sync_to_async
from django.views.decorators.debug import sensitive_variables
from dmr import Body, Path, modify
from dmr.endpoint import Endpoint

from api_auth.catalog import (
    CATALOG,
    FunctionalPermissions as P,
)
from api_auth.schemas.team import (
    PermissionInfoGet,
    StaffAcceptPost,
    StaffInviteGet,
    StaffInvitePost,
    StaffMemberGet,
    StaffRoleGet,
    StaffRolePost,
    StaffRolePut,
    UserReferencePost,
    UserRolePost,
    UserStatusPost,
)
from api_auth.services.roles import ensure_permission
from api_auth.services.team import (
    accept_invitation,
    create_role_sync,
    delete_role_sync,
    get_role_sync,
    invite_staff,
    list_roles_sync,
    send_password_reset_to,
    set_role_sync,
    set_status_sync,
    staff_members_sync,
    update_role_sync,
)
from api_core.controllers.base import BaseController
from api_core.controllers.endpoints import ModelOperationIdEndpoint
from api_core.controllers.serializers import CustomPydanticFastSerializer
from api_core.schemas.path import IntInstancePath

from .base import AuthController

########################################################################################
# Roles y permisos del equipo


class StaffPermissionController(BaseController[CustomPydanticFastSerializer]):
    # el catálogo de lo que puede dar un rol: el portal no necesita su propia copia
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[PermissionInfoGet]:
        await ensure_permission(self.request.user, P.STAFF_MANAGE)

        return [
            PermissionInfoGet(
                description=info.description,
                id=info.id,
                label=info.label,
                module=info.module,
            )
            for info in CATALOG
        ]


class StaffRoleController(BaseController[CustomPydanticFastSerializer]):
    # list / create, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[StaffRoleGet]:
        await ensure_permission(self.request.user, P.STAFF_MANAGE, P.USERS_VIEW)

        return await sync_to_async(list_roles_sync)()

    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[StaffRolePost]) -> StaffRoleGet:
        await ensure_permission(self.request.user, P.STAFF_MANAGE)

        return await sync_to_async(create_role_sync)(parsed_body)


class StaffRoleDetailController(BaseController[CustomPydanticFastSerializer]):
    # retrieve / update / destroy, como los controladores de modelo
    endpoint_cls: ClassVar[type[Endpoint]] = ModelOperationIdEndpoint

    @modify(status_code=HTTPStatus.OK)
    async def get(self, parsed_path: Path[IntInstancePath]) -> StaffRoleGet:
        await ensure_permission(self.request.user, P.STAFF_MANAGE, P.USERS_VIEW)

        return await sync_to_async(get_role_sync)(parsed_path.id)

    @modify(status_code=HTTPStatus.OK)
    async def put(
        self,
        parsed_body: Body[StaffRolePut],
        parsed_path: Path[IntInstancePath],
    ) -> StaffRoleGet:
        await ensure_permission(self.request.user, P.STAFF_MANAGE)

        return await sync_to_async(update_role_sync)(
            parsed_path.id,
            parsed_body,
            self.request.user,
        )

    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def delete(self, parsed_path: Path[IntInstancePath]) -> None:
        await ensure_permission(self.request.user, P.STAFF_MANAGE)

        await sync_to_async(delete_role_sync)(parsed_path.id)


########################################################################################
# Invitación y personas del equipo


class StaffMemberController(BaseController[CustomPydanticFastSerializer]):
    # las personas del equipo con su rol: lo que lista la pantalla del equipo
    @modify(status_code=HTTPStatus.OK)
    async def get(self) -> list[StaffMemberGet]:
        await ensure_permission(self.request.user, P.STAFF_MANAGE, P.USERS_VIEW)

        return await sync_to_async(staff_members_sync)()


class StaffInviteController(BaseController[CustomPydanticFastSerializer]):
    # invita a alguien al equipo: le llega un código al correo para elegir su contraseña
    @modify(status_code=HTTPStatus.CREATED)
    async def post(self, parsed_body: Body[StaffInvitePost]) -> StaffInviteGet:
        await ensure_permission(self.request.user, P.STAFF_MANAGE)

        return await invite_staff(parsed_body)


class StaffAcceptController(AuthController[CustomPydanticFastSerializer]):
    # quien recibió la invitación activa su cuenta con el código del correo
    @modify(status_code=HTTPStatus.NO_CONTENT)
    @sensitive_variables()
    async def post(self, parsed_body: Body[StaffAcceptPost]) -> None:  # ruff: ignore[no-self-use]
        await accept_invitation(parsed_body)


class UserStatusController(BaseController[CustomPydanticFastSerializer]):
    # suspende o reactiva una cuenta; suspender corta de inmediato sus sesiones
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_body: Body[UserStatusPost]) -> StaffMemberGet:
        await ensure_permission(self.request.user, P.USERS_MANAGE)

        return await sync_to_async(set_status_sync)(
            actor=self.request.user,
            status=parsed_body.status,
            user_id=parsed_body.user_id,
        )


class UserRoleController(BaseController[CustomPydanticFastSerializer]):
    @modify(status_code=HTTPStatus.OK)
    async def post(self, parsed_body: Body[UserRolePost]) -> StaffMemberGet:
        await ensure_permission(self.request.user, P.STAFF_MANAGE)

        return await sync_to_async(set_role_sync)(
            actor=self.request.user,
            role_id=parsed_body.role_id,
            user_id=parsed_body.user_id,
        )


class UserPasswordResetController(BaseController[CustomPydanticFastSerializer]):
    # le manda a la persona un código para que cree otra contraseña
    @modify(status_code=HTTPStatus.NO_CONTENT)
    async def post(self, parsed_body: Body[UserReferencePost]) -> None:
        await ensure_permission(self.request.user, P.USERS_MANAGE)

        await send_password_reset_to(parsed_body.user_id)
