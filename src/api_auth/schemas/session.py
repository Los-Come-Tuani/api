from datetime import date, datetime
from typing import Literal
from uuid import UUID

from api_core.schemas.base import DTO
from api_core.schemas.get import BaseGet

from .group import GroupInlineGet
from .types import UserStatus

########################################################################################

# - el papel visible para los clientes. Se deriva de los grupos de la cuenta.
type Role = Literal[
    "admin",
    "alcaldia",
    "guia",
    "institucion",
    "negocio",
    "traductor",
    "turista",
]

########################################################################################


class TwoFactorState(DTO):
    enabled: bool
    required: bool


class OrganizationRefGet(DTO):
    id: UUID
    kind: Literal["business", "institution", "municipality"]
    name: str
    # la verificó el equipo; hasta entonces solo ve su solicitud
    verified: bool


class SessionUserGet(BaseGet):
    """La persona de la sesión, con todo lo que un cliente necesita para arrancar."""

    created_at: datetime
    email: str
    first_name: str
    last_name: str
    # nombre listo para mostrar
    name: str
    username: str | None
    birth_date: date | None
    nationality: str
    status: UserStatus
    verified: bool
    role: Role | None
    groups: tuple[GroupInlineGet, ...]
    permissions: tuple[str, ...]
    # el negocio, la alcaldía o la institución sobre la que actúa (su asignación de rol
    # vigente); nulo para quien no es de una organización
    organization_id: UUID | None
    organization: OrganizationRefGet | None
    two_factor: TwoFactorState
