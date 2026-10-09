from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from api_core.schemas.base import DTO
from api_core.schemas.pagination import PageQuery

########################################################################################


class ReviewGet(DTO):
    id: UUID
    booking_id: UUID
    direction: Literal["tourist_to_guide", "guide_to_tourist"]
    rating: int
    comment: str
    created_at: datetime
    hidden: bool


class ReviewPost(DTO):
    rating: Annotated[int, Field(ge=1, le=5)]
    comment: Annotated[str, StringConstraints(max_length=1000)] = ""


class DisputePost(DTO):
    reason: Annotated[str, StringConstraints(max_length=1000, min_length=10)]


class DisputeGet(DTO):
    id: UUID
    review: ReviewGet
    author: str
    subject: str
    raised_by: str
    reason: str
    status: Literal["pending", "upheld", "rejected"]
    created_at: datetime
    resolved_at: datetime | None
    note: str


class DisputeQuery(PageQuery):
    status: Literal["pending", "upheld", "rejected"] | None = None


class ResolvePost(DTO):
    # `true`: el equipo le da la razón a quien impugnó y la reseña se oculta
    upheld: bool
    note: Annotated[str, StringConstraints(max_length=1000)] = ""
