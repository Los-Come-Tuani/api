from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Avg, Count
from django.db.transaction import atomic
from django.db.utils import IntegrityError
from django.utils.timezone import now

from api_auth.catalog import FunctionalPermissions as P
from api_core.services.pages import paginate
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_profiles.models import ProviderProfile
from api_reputation.models import Review, ReviewDispute
from api_reputation.schemas import DisputeGet, ReviewGet
from api_services.services.bookings import is_guide_of, own_booking
from api_territory.models import Circuit

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_auth.models import ApiUser
    from api_core.schemas.pagination import Paginated
    from api_reputation.schemas import DisputeQuery, ResolvePost, ReviewPost
    from api_territory.services.access import Actor

########################################################################################

# - una reseña se deja cuando el servicio ya se prestó
REVIEWABLE: Final[tuple[str, ...]] = ("prestada", "cerrada")

DISPUTE_API: Final[dict[str, str]] = {
    "aceptada": "upheld",
    "pendiente": "pending",
    "rechazada": "rejected",
}
DISPUTE_BY_API: Final[dict[str, str]] = {
    name: code for code, name in DISPUTE_API.items()
}

########################################################################################


def review_payload(review: Review) -> ReviewGet:
    found: Any = review

    return ReviewGet(
        booking_id=found.booking_id,
        comment=str(found.comment),
        created_at=found.created_at,
        direction=found.direction,
        hidden=found.hidden_at is not None,
        id=found.pk,
        rating=int(found.rating),
    )


# El resumen del circuito sale de lo que los turistas dicen de los servicios hechos
# sobre él.
def refresh_circuit_rating(circuit_id: UUID | None) -> None:
    if circuit_id is None:
        return

    summary: Any = Review.objects.filter(
        booking__circuit_id=circuit_id,
        direction="tourist_to_guide",
        hidden_at__isnull=True,
    ).aggregate(average=Avg("rating"), total=Count("id"))

    Circuit.objects.filter(pk=circuit_id).update(
        rating=Decimal(str(round(float(summary["average"] or 0), 1))),
        reviews_count=int(summary["total"] or 0),
    )


# El promedio y el total del guía (`perfil_prestador`): lo que dicen los turistas.
def refresh_provider_rating(subject_id: UUID) -> None:
    summary: Any = Review.objects.filter(
        direction="tourist_to_guide",
        hidden_at__isnull=True,
        subject_id=subject_id,
    ).aggregate(average=Avg("rating"), total=Count("id"))

    total: int = int(summary["total"] or 0)

    ProviderProfile.objects.filter(user_id=subject_id).update(
        rating_average=(
            None if total == 0 else Decimal(str(round(float(summary["average"]), 2)))
        ),
        reviews_count=total,
    )


def review_sync(user: ApiUser, booking_id: UUID, data: ReviewPost) -> ReviewGet:
    booking: Any = own_booking(user, booking_id)

    if booking.status.code not in REVIEWABLE:
        raise ConflictError(detail="La reseña se deja cuando termina el recorrido.")

    guide: bool = is_guide_of(user, booking)

    with atomic():
        try:
            review: Review = Review.objects.create(
                author=user,
                booking=booking,
                comment=data.comment,
                direction="guide_to_tourist" if guide else "tourist_to_guide",
                rating=data.rating,
                subject_id=booking.user_id if guide else booking.provider.user_id,
            )
        except IntegrityError as i:
            raise ConflictError(detail="Ya dejaste tu reseña de este recorrido.") from i

        if not guide:
            refresh_circuit_rating(booking.circuit_id)
            refresh_provider_rating(booking.provider.user_id)

    return review_payload(review)


# El reseñado pide que el equipo la revise.
def dispute_sync(user: ApiUser, review_id: UUID, reason: str) -> DisputeGet:
    review: Any = Review.objects.filter(pk=review_id, subject=user).first()

    if review is None:
        raise NotFoundError(detail="No encontramos esa reseña.")

    if review.hidden_at is not None:
        raise ConflictError(detail="Esa reseña ya está oculta.")

    try:
        dispute: ReviewDispute = ReviewDispute.objects.create(
            raised_by=user,
            reason=reason.strip(),
            review=review,
        )
    except IntegrityError as i:
        raise ConflictError(detail="Ya pediste que revisen esa reseña.") from i

    return dispute_payload(disputes().get(pk=dispute.pk))


########################################################################################
# El equipo resuelve


def disputes() -> QuerySet:
    return ReviewDispute.objects.select_related(
        "raised_by",
        "review__author",
        "review__subject",
    )


def dispute_payload(dispute: ReviewDispute) -> DisputeGet:
    found: Any = dispute

    return DisputeGet(
        author=found.review.author.display_name,
        created_at=found.created_at,
        id=found.pk,
        note=str(found.note),
        raised_by=found.raised_by.display_name,
        reason=str(found.reason),
        resolved_at=found.resolved_at,
        review=review_payload(found.review),
        status=DISPUTE_API[str(found.status)],  # ty: ignore[invalid-argument-type]
        subject=found.review.subject.display_name,
    )


def ensure_moderator(actor: Actor) -> None:
    if not actor.can(P.CONTENT_MODERATE):
        raise ForbiddenError


def disputes_sync(actor: Actor, query: DisputeQuery) -> Paginated[DisputeGet]:
    ensure_moderator(actor)

    found = disputes()

    if query.status is not None:
        found = found.filter(status=DISPUTE_BY_API[query.status])

    return paginate(
        found.order_by("created_at", "id"),
        query,
        dispute_payload,
        DisputeGet,
    )


def resolve_sync(actor: Actor, dispute_id: UUID, data: ResolvePost) -> DisputeGet:
    ensure_moderator(actor)

    with atomic():
        dispute: Any = (
            disputes().select_for_update(of=("self",)).filter(pk=dispute_id).first()
        )

        if dispute is None:
            raise NotFoundError(detail="No encontramos esa impugnación.")

        if dispute.status != "pendiente":
            raise ConflictError(detail="Esa impugnación ya se resolvió.")

        ReviewDispute.objects.filter(pk=dispute.pk).update(
            note=data.note.strip(),
            resolved_at=now(),
            resolved_by=actor.user,
            status="aceptada" if data.upheld else "rechazada",
        )

        if data.upheld:
            Review.objects.filter(pk=dispute.review_id).update(hidden_at=now())
            refresh_circuit_rating(dispute.review.booking.circuit_id)
            refresh_provider_rating(dispute.review.subject_id)

    return dispute_payload(disputes().get(pk=dispute_id))
