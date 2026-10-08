from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints

from api_core.schemas.base import DTO, LaxDTO

########################################################################################


class MessageGet(DTO):
    id: UUID
    sender_id: UUID
    # lo escribió quien pregunta
    mine: bool
    body: str
    sent_at: datetime


class MessagePost(DTO):
    body: Annotated[str, StringConstraints(max_length=2000, min_length=1)]


class MessageQuery(LaxDTO):
    # solo lo posterior: la app pregunta cada pocos segundos con el último que tiene
    after: Annotated[datetime, Field(strict=False)] | None = None
