from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import StringConstraints, model_validator

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery
from api_moderation.schemas import (
    CityRef,
    PersonRef,
    QueueStatus,
    RejectionReasonGet,
)
from api_organizations.schemas.application import ReasonGet, ResolutionGet
from api_profiles.schemas.application import (
    CredentialGet,
    FileGet,
    OptionRef,
    ProcedureName,
    ProviderStatusName,
    Reference,
    RequestStatus,
    ServiceCode,
)
from api_profiles.schemas.profile import LanguageGet

########################################################################################


class ProviderQueueQuery(PageQuery):
    # `open` es la bandeja del equipo (enviadas y en revisión); `all` trae todo
    status: QueueStatus = "open"
    service: ServiceCode | None = None
    procedure: ProcedureName | None = None


########################################################################################


class DocumentCountsGet(DTO):
    total: int
    accepted: int
    rejected: int
    # sin revisar
    pending: int


class ProviderRequestInlineGet(DTO):
    id: UUID
    procedure: ProcedureName
    status: RequestStatus
    # en qué paso está lo abierto: revisar documentos o decidir; nulo si se resolvió
    stage: Literal["documents", "decision"] | None
    applicant: PersonRef
    services: list[str]
    # nula es todo el país
    city: CityRef | None
    # se atiende por orden de llegada
    submitted_at: datetime
    resolved_at: datetime | None
    # quién la tiene en revisión
    taken_by: PersonRef | None
    counts: DocumentCountsGet


class RequestCredentialGet(CredentialGet):
    # se pide por los servicios que ofrece (o porque lleva turistas)
    required: bool
    # se subió en este expediente; si no, viene de uno anterior o está en vigor
    in_this_request: bool


class ProviderDetailGet(DTO):
    id: UUID
    status: ProviderStatusName
    phone: str
    presentation: str
    photo: FileGet | None
    languages: list[LanguageGet]
    carries_tourists: bool
    created_at: datetime
    approved_at: datetime | None


class ProviderHistoryItem(DTO):
    id: UUID
    procedure: ProcedureName
    status: RequestStatus
    submitted_at: datetime
    resolved_at: datetime | None
    reason: ReasonGet | None
    note: str


class ProviderRequestGet(ProviderRequestInlineGet):
    profile: ProviderDetailGet
    documents: list[RequestCredentialGet]
    # los tipos que se le piden y no tienen un documento utilizable
    missing: list[OptionRef]
    resolution: ResolutionGet | None
    # los expedientes anteriores del mismo prestador
    history: list[ProviderHistoryItem]


class ProviderReasonsGet(DTO):
    # al rechazar un documento
    document: list[RejectionReasonGet]
    # al rechazar al prestador en la decisión
    decision: list[RejectionReasonGet]


########################################################################################


class DocumentReviewPost(DTO):
    document_id: Reference
    accepted: bool
    # al rechazar: el código de un motivo de la lista `document`
    reason: Annotated[str, StringConstraints(max_length=60, min_length=1)] | None = None
    # lo que se le comunica al prestador; obligatoria con el motivo «otro»
    note: Annotated[str, StringConstraints(max_length=1000)] = ""

    @model_validator(mode="after")
    def check_reason(self) -> Self:
        if not self.accepted and self.reason is None:
            raise ValueError("Al rechazar un documento hay que decir por qué.")

        if self.accepted and self.reason is not None:
            raise ValueError("Un documento aceptado no lleva motivo.")

        return self


class RequestChangesPost(DTO):
    note: Annotated[str, StringConstraints(max_length=1000)] = ""
