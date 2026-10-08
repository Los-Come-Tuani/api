from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_territory.schemas.common import Reference

########################################################################################

type TargetKind = Literal["user", "review", "place", "event"]
type ReportStatusName = Literal["pending", "handled", "dismissed"]
type SanctionKind = Literal["warning", "suspension", "expulsion"]
type Note = Annotated[str, StringConstraints(max_length=1000)]

########################################################################################


class ReportReasonGet(DTO):
    code: str
    label: str
    # con este motivo hay que explicar qué pasó
    requires_text: bool


class ReportPost(DTO):
    target_kind: TargetKind
    target_id: Reference
    reason: Annotated[str, StringConstraints(max_length=60, min_length=1)]
    note: Note = ""


class ReportTargetGet(DTO):
    kind: TargetKind
    id: UUID | None
    # el nombre de la persona, del lugar o del evento; un extracto de la reseña
    label: str


class ReportGet(DTO):
    id: UUID
    target: ReportTargetGet
    reason: ReportReasonGet
    note: str
    reporter: str
    status: ReportStatusName
    created_at: datetime
    resolved_at: datetime | None
    resolution_note: str


class ReportQuery(PageQuery):
    status: ReportStatusName | None = None
    target_kind: TargetKind | None = None


class ResolveReportPost(DTO):
    # `handled`: se actuó (por ejemplo, con una sanción); `dismissed`: no procede
    status: Literal["handled", "dismissed"]
    note: Note = ""


class SanctionGet(DTO):
    id: UUID
    user_id: UUID
    user_name: str
    kind: SanctionKind
    reason: str
    starts_at: datetime
    ends_at: datetime | None
    created_by: str
    report_id: UUID | None
    lifted_at: datetime | None
    # sigue vigente
    active: bool


class SanctionPost(DTO):
    user_id: Reference
    kind: SanctionKind
    reason: Annotated[str, StringConstraints(max_length=1000, min_length=5)]
    # solo la suspensión: cuántos días dura; sin días, hasta que se levante
    days: Annotated[int, Field(ge=1, le=365)] | None = None
    report_id: Reference | None = None


class SanctionQuery(PageQuery):
    user_id: Reference | None = None
    active: bool | None = None
