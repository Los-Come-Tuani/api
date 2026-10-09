from datetime import timedelta
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Count, Sum
from django.db.transaction import atomic
from django.utils.timezone import now

from api_auth.enums import AccountRoles
from api_auth.models import ApiUser
from api_auth.services.roles import role_of_sync
from api_catalogs.models import CulturalPillar
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_rewards.models import Badge, BadgeMovement, Visit
from api_rewards.schemas import (
    BalanceGet,
    MovementGet,
    PillarCountGet,
    QrGet,
    VisitGet,
    VisitPointRef,
)
from api_territory.schemas.common import PillarRef
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from api_rewards.schemas import VisitPost
    from api_territory.models import PointOfInterest

########################################################################################

QR_PREFIX: Final[str] = "kplan://visit/"
# - a cuántos metros del lugar se acredita la visita (RF-S-15)
MAX_DISTANCE_METERS: Final[int] = 50
EARTH_RADIUS_METERS: Final[float] = 6_371_000
RECENT_MOVEMENTS: Final[int] = 20
# - un mismo lugar acredita una visita del mismo turista cada 24 horas
VISIT_WINDOW: Final[timedelta] = timedelta(hours=24)

########################################################################################
# La insignia de un lugar


# La insignia sigue a `has_badge` del lugar: activarla la crea (con su QR) o la
# reactiva; apagarla deja de darla sin tocar lo ya acreditado.
def sync_badge(point: PointOfInterest) -> Badge | None:
    found: Any = point
    badge: Badge | None = Badge.objects.filter(point=point).first()

    if badge is None and not found.has_badge:
        return None

    if badge is None:
        return Badge.objects.create(
            name=str(found.name)[:120],
            point=point,
            qr_token=token_urlsafe(18),
        )

    if bool(badge.active) != bool(found.has_badge):
        Badge.objects.filter(pk=badge.pk).update(active=found.has_badge)
        badge.refresh_from_db()

    return badge


def qr_payload(point: PointOfInterest) -> QrGet:
    badge: Any = sync_badge(point)

    if badge is None or not badge.active:
        raise NotFoundError(detail="Ese lugar no da insignia.")

    return QrGet(
        active=bool(badge.active),
        payload=f"{QR_PREFIX}{badge.qr_token}",
        point_id=badge.point_id,
        token=str(badge.qr_token),
        value=int(badge.value),
    )


########################################################################################
# Visitas


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    # fórmula del semiverseno: basta para unos metros
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi, dlambda = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2

    return round(2 * EARTH_RADIUS_METERS * asin(sqrt(a)))


def ensure_tourist(user: ApiUser) -> None:
    # las insignias y los cupones son del turista: ni el negocio ni el equipo se
    # acreditan visitas
    if role_of_sync(user) != AccountRoles.TURISTA:
        raise ForbiddenError(detail="Las insignias son para las cuentas de turista.")


def balance_of(user: ApiUser) -> int:
    total: Any = BadgeMovement.objects.filter(user=user).aggregate(total=Sum("amount"))

    return int(total["total"] or 0)


def lock_user(user: ApiUser) -> None:
    # dos operaciones del mismo turista se ponen en fila: el saldo se lee una por vez
    ApiUser.objects.select_for_update().filter(pk=user.pk).first()


def window_open(user: ApiUser, badge: Badge, window: timedelta) -> bool:
    return not Visit.objects.filter(
        accredited_at__gt=now() - window,
        badge=badge,
        user=user,
    ).exists()


def accredit_visit_sync(user: ApiUser, data: VisitPost) -> VisitGet:
    ensure_tourist(user)

    token: str = data.qr.strip().removeprefix(QR_PREFIX)
    badge: Any = (
        Badge.objects
        .select_related("point__pillar")
        .filter(
            active=True,
            point__active=True,
            point__has_badge=True,
            qr_token=token,
        )
        .first()
    )

    if badge is None:
        raise NotFoundError(detail="Ese QR no es de un lugar con insignia.")

    point: Any = badge.point
    distance: int = distance_meters(
        data.latitude,
        data.longitude,
        float(point.latitude),
        float(point.longitude),
    )

    if distance > MAX_DISTANCE_METERS:
        raise invalid(
            "latitude",
            f"Tienes que estar a menos de {MAX_DISTANCE_METERS} m del lugar "
            f"(estás a {distance} m).",
        )

    with atomic():
        lock_user(user)

        if not window_open(user, badge, VISIT_WINDOW):
            raise ConflictError(
                detail="Ya ganaste la insignia de este lugar hoy. Vuelve mañana."
            )

        visit: Visit = Visit.objects.create(
            badge=badge,
            distance_meters=distance,
            latitude=Decimal(str(round(data.latitude, 6))),
            longitude=Decimal(str(round(data.longitude, 6))),
            user=user,
        )
        BadgeMovement.objects.create(amount=badge.value, user=user, visit=visit)

        balance: int = balance_of(user)

    return VisitGet(
        accredited_at=visit.accredited_at,  # ty: ignore[invalid-argument-type]
        amount=int(badge.value),
        balance=balance,
        distance_meters=distance,
        id=visit.pk,
        point=VisitPointRef(
            id=point.pk,
            name=str(point.name),
            pillar=PillarRef(
                code=str(point.pillar.code), label=str(point.pillar.label)
            ),
        ),
    )


########################################################################################
# Saldo


def balance_sync(user: ApiUser) -> BalanceGet:
    movements = BadgeMovement.objects.filter(user=user)
    totals: Any = movements.aggregate(total=Sum("amount"))
    earned: Any = movements.filter(amount__gt=0).aggregate(total=Sum("amount"))

    by_pillar: dict[str, int] = {
        str(row["visit__badge__point__pillar__code"]): int(row["total"] or 0)
        for row in movements
        .filter(visit__isnull=False)
        .values("visit__badge__point__pillar__code")
        .annotate(total=Sum("amount"))
    }

    visited = (
        Visit.objects
        .filter(user=user)
        .values("badge__point_id")
        .annotate(times=Count("id"))
        .order_by("badge__point_id")
    )

    recent = movements.select_related("visit__badge__point", "coupon").order_by(
        "-recorded_at"
    )[:RECENT_MOVEMENTS]

    earned_total: int = int(earned["total"] or 0)
    balance: int = int(totals["total"] or 0)

    return BalanceGet(
        balance=balance,
        by_pillar=[
            PillarCountGet(
                code=str(pillar.code),
                count=by_pillar.get(str(pillar.code), 0),
                label=str(pillar.label),
            )
            for pillar in CulturalPillar.objects.filter(active=True).order_by("order")
        ],
        earned=earned_total,
        recent=[movement_payload(item) for item in recent],
        spent=earned_total - balance,
        visited_point_ids=[row["badge__point_id"] for row in visited],
    )


def movement_payload(movement: BadgeMovement) -> MovementGet:
    found: Any = movement

    if found.visit is not None:
        return MovementGet(
            amount=int(found.amount),
            kind="visit",
            label=str(found.visit.badge.point.name),
            recorded_at=found.recorded_at,
        )

    return MovementGet(
        amount=int(found.amount),
        kind="coupon",
        label=str(found.coupon.title),
        recorded_at=found.recorded_at,
    )
