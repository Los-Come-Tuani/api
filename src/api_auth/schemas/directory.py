from datetime import datetime
from typing import Annotated, get_args

from pydantic import AfterValidator, StringConstraints
from pydantic_core import PydanticCustomError

from api_core.schemas.base import DTO
from api_core.schemas.get import BaseGet
from api_core.schemas.pagination import PageQuery
from api_moderation.schemas import CityRef

from .account import FirstName, LastName
from .session import OrganizationRefGet, ProviderRefGet, Role
from .team import StaffRoleInlineGet
from .types import UserStatus

########################################################################################


ROLES: frozenset[str] = frozenset(get_args(Role.__value__))


def known_roles(value: str | None) -> str | None:
    if value is None:
        return None

    unknown = {item.strip() for item in value.split(",")} - ROLES

    if unknown:
        raise PydanticCustomError(
            "api_custom",
            "",
            {"msg": f"Papel desconocido: {', '.join(sorted(unknown))}."},
        )

    return value


class AccountQuery(PageQuery):
    # uno o varios papeles separados por comas (`guia,traductor`)
    role: Annotated[
        str | None,
        StringConstraints(max_length=100),
        AfterValidator(known_roles),
    ] = None
    status: UserStatus | None = None
    # por nombre o correo
    search: Annotated[str, StringConstraints(max_length=100)] | None = None

    @property
    def roles(self) -> list[str]:
        return (
            [] if self.role is None else [item.strip() for item in self.role.split(",")]
        )


########################################################################################


class AccountGet(BaseGet):
    """Una cuenta del directorio, con el papel y la organización que se le ven."""

    created_at: datetime
    email: str
    first_name: str
    last_name: str
    # nombre listo para mostrar
    name: str
    status: UserStatus
    verified: bool
    # el papel de más rango entre sus grupos; nulo si no tiene ninguno todavía
    role: Role | None
    superuser: bool
    # el rol del equipo, solo para el equipo de K'Plan
    staff_role: StaffRoleInlineGet | None
    organization: OrganizationRefGet | None
    provider: ProviderRefGet | None
    # la ciudad de su organización o de su perfil de prestador; nula si no aplica o si
    # el prestador trabaja en todo el país
    city: CityRef | None


# Solo se aplican los campos que llegan. El correo y la contraseña tienen sus propios
# procedimientos; el estado y el rol, sus rutas (`user-status/` y `user-role/`).
class AccountPatch(DTO):
    first_name: FirstName = ""
    last_name: LastName = ""
