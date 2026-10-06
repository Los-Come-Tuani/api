from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, PositiveInt, StringConstraints

from api_auth.enums import ApiUserStatus
from api_core.schemas.base import DTO
from api_core.schemas.get import BaseGet

from .account import FirstName, LastName
from .types import Email, OneTimeCode, Password, UserStatus

########################################################################################


class PermissionInfoGet(DTO):
    id: str
    module: str
    label: str
    description: str


########################################################################################


class StaffRoleInlineGet(BaseGet[PositiveInt]):
    name: str


class StaffRoleGet(StaffRoleInlineGet):
    created_at: datetime
    description: str
    # cuántas personas tienen este rol
    members: int
    permissions: tuple[str, ...]
    requires_two_factor: bool
    # los roles de sistema no se editan ni se borran
    system: bool


type RoleName = Annotated[str, StringConstraints(max_length=150, min_length=1)]

type PermissionId = Annotated[str, StringConstraints(max_length=64, min_length=1)]


class StaffRolePost(DTO):
    name: RoleName
    description: Annotated[str, StringConstraints(max_length=300)] = ""
    # el DTO estricto recibe del JSON listas, no tuplas
    permissions: Annotated[list[PermissionId], Field(max_length=64)] = Field(
        default_factory=list
    )
    requires_two_factor: bool = True


StaffRolePut = StaffRolePost

########################################################################################

# - un UUID llega como texto en el JSON, y el DTO estricto no lo convertiría solo
type UserReference = Annotated[UUID, Field(strict=False)]


class StaffMemberGet(BaseGet):
    created_at: datetime
    email: str
    name: str
    role: StaffRoleInlineGet | None
    status: UserStatus


class StaffInviteGet(StaffMemberGet):
    # `False` si todavía rige la espera entre correos: la persona ya tiene un código
    # vigente (el del último correo) y no se le mandó otro
    sent: bool


class StaffInvitePost(DTO):
    email: Email
    first_name: FirstName
    last_name: LastName = ""
    role_id: PositiveInt


class StaffAcceptPost(DTO):
    email: Email
    code: OneTimeCode
    password: Password


class UserStatusPost(DTO):
    # solo se activa y se suspende desde aquí: la expulsión es otro procedimiento
    status: Literal[ApiUserStatus.ACTIVE, ApiUserStatus.SUSPENDED]
    user_id: UserReference


class UserRolePost(DTO):
    role_id: PositiveInt
    user_id: UserReference


class UserReferencePost(DTO):
    user_id: UserReference
