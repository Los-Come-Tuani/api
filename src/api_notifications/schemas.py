from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery

########################################################################################


class NotificationGet(DTO):
    id: UUID
    # `mensaje`, `reserva`, `convocatoria`, `resena`, `pago` o `cuenta`
    kind: str
    title: str
    body: str
    # a qué apunta (`booking_id`, `request_id`...): la app abre esa pantalla
    data: dict[str, str]
    read: bool
    created_at: datetime


class UnreadCountGet(DTO):
    count: int


class NotificationQuery(PageQuery):
    # solo los que no se han leído
    unread: bool = False


class DeviceTokenPost(DTO):
    token: Annotated[str, StringConstraints(max_length=500, min_length=10)]
    platform: Literal["android", "ios", "web"]


class DeviceTokenRemovePost(DTO):
    token: Annotated[str, StringConstraints(max_length=500, min_length=10)]


class PreferenceGet(DTO):
    kind: str
    label: str
    push_enabled: bool


class PreferenceItem(DTO):
    kind: Annotated[str, StringConstraints(max_length=40, min_length=1)]
    push_enabled: bool


class PreferencePut(DTO):
    preferences: Annotated[list[PreferenceItem], Field(max_length=20)]
