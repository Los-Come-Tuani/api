from datetime import datetime, time
from typing import Annotated, Literal
from uuid import UUID

from pydantic import StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_organizations.schemas.application import (
    OrganizationKind,
    ReasonGet,
    ResolutionGet,
)

########################################################################################

type QueueStatus = Literal[
    "open",
    "submitted",
    "in_review",
    "approved",
    "rejected",
    "all",
]

type RequestStatus = Literal["submitted", "in_review", "approved", "rejected"]


class VerificationQuery(PageQuery):
    # `open` es la bandeja del equipo (enviadas y en revisión); `all` trae todo
    status: QueueStatus = "open"
    kind: OrganizationKind | None = None


########################################################################################


class PersonRef(DTO):
    id: UUID
    name: str
    email: str


class CityRef(DTO):
    id: UUID
    code: str
    name: str


class OptionRef(DTO):
    code: str
    label: str


class VerificationRequestInlineGet(DTO):
    id: UUID
    kind: OrganizationKind
    organization_id: UUID
    organization_name: str
    city: CityRef
    status: RequestStatus
    # se atiende por orden de llegada
    submitted_at: datetime
    resolved_at: datetime | None
    # quién la tiene en revisión
    taken_by: PersonRef | None


########################################################################################


class HoursGet(DTO):
    weekday: int
    closed: bool
    opens: time | None
    closes: time | None


class SignatureDishGet(DTO):
    name: str
    description: str
    reference_price: float
    currency: str


class BusinessDetailGet(DTO):
    business_type: OptionRef
    ruc: str
    address: str
    phone: str
    alternate_phone: str
    latitude: float
    longitude: float
    hours: list[HoursGet]
    signature_dish: SignatureDishGet | None


class InstitutionDetailGet(DTO):
    institution_type: OptionRef
    contact_email: str
    phone: str


class MunicipalityDetailGet(DTO):
    contact_email: str
    phone: str


class DocumentGet(DTO):
    kind: Literal["legal_document", "signature_dish_photo"]
    # una URL de lectura que vence en minutos; nula si el almacenamiento no está
    # configurado
    url: str | None


class HistoryItem(DTO):
    id: UUID
    status: RequestStatus
    submitted_at: datetime
    resolved_at: datetime | None
    reason: ReasonGet | None
    note: str


class VerificationRequestGet(VerificationRequestInlineGet):
    # quien se postuló (el primer operador de la organización)
    applicant: PersonRef | None
    # cuál de estos viene según `kind`
    business: BusinessDetailGet | None
    institution: InstitutionDetailGet | None
    municipality: MunicipalityDetailGet | None
    documents: list[DocumentGet]
    resolution: ResolutionGet | None
    # los expedientes anteriores de la misma organización: cuántas veces se intentó y
    # por qué se rechazó cada vez
    history: list[HistoryItem]


########################################################################################


class ApprovePost(DTO):
    note: Annotated[str, StringConstraints(max_length=1000)] = ""


class RejectPost(DTO):
    # el código de un motivo ofrecido para rechazar (`rechazo_verificacion`)
    reason: Annotated[str, StringConstraints(max_length=60, min_length=1)]
    # lo que se le comunica a quien se postuló; obligatoria con el motivo «otro»
    note: Annotated[str, StringConstraints(max_length=1000)] = ""


class RejectionReasonGet(DTO):
    code: str
    label: str
    requires_text: bool
