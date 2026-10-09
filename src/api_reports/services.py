from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final

from django.db.models import Q
from django.db.transaction import atomic
from django.utils.timezone import now

from api_agenda.models import Event
from api_auth.catalog import FunctionalPermissions as P
from api_auth.enums import ApiUserStatus
from api_auth.models import ApiUser
from api_auth.services.account import change_status_sync
from api_catalogs.models import Reason
from api_core.services.pages import paginate
from api_exceptions.errors import ConflictError, ForbiddenError, NotFoundError
from api_notifications.services import notify
from api_reports.models import Report, Sanction
from api_reports.schemas import (
    ReportGet,
    ReportReasonGet,
    ReportTargetGet,
    SanctionGet,
)
from api_reports.seeder import CONTEXT_REPORT
from api_reputation.models import Review
from api_territory.models import PointOfInterest
from api_territory.services.access import invalid

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models.query import QuerySet

    from api_core.schemas.pagination import Paginated
    from api_reports.schemas import (
        ReportPost,
        ReportQuery,
        ResolveReportPost,
        SanctionPost,
        SanctionQuery,
    )
    from api_territory.services.access import Actor

########################################################################################

REPORT_API: Final[dict[str, str]] = {
    "atendido": "handled",
    "descartado": "dismissed",
    "pendiente": "pending",
}
REPORT_BY_API: Final[dict[str, str]] = {name: code for code, name in REPORT_API.items()}

SANCTION_API: Final[dict[str, str]] = {
    "advertencia": "warning",
    "expulsion": "expulsion",
    "suspension": "suspension",
}
SANCTION_BY_API: Final[dict[str, str]] = {
    name: code for code, name in SANCTION_API.items()
}

# - de qué campo es cada clase de objeto reportado
TARGET_FIELDS: Final[dict[str, str]] = {
    "event": "target_event",
    "place": "target_point",
    "review": "target_review",
    "user": "target_user",
}
TARGET_MODELS: Final[dict[str, Any]] = {
    "event": Event,
    "place": PointOfInterest,
    "review": Review,
    "user": ApiUser,
}

########################################################################################
# Reportar (cualquiera con sesión)


def reasons_sync() -> list[ReportReasonGet]:
    return [
        ReportReasonGet(
            code=str(item.code),
            label=str(item.label),
            requires_text=bool(item.requires_text),
        )
        for item in Reason.objects.filter(
            active=True, contexts__context=CONTEXT_REPORT
        ).order_by("contexts__order")
    ]


def report_sync(user: ApiUser, data: ReportPost) -> None:
    reason: Any = Reason.objects.filter(
        active=True, code=data.reason, contexts__context=CONTEXT_REPORT
    ).first()

    if reason is None:
        raise invalid("reason", "Ese motivo no existe.")

    if reason.requires_text and not data.note.strip():
        raise invalid("note", "Con ese motivo cuéntanos qué pasó.")

    target: Any = (
        TARGET_MODELS[data.target_kind].objects.filter(pk=data.target_id).first()
    )

    if target is None:
        raise invalid("target_id", "No encontramos lo que quieres reportar.")

    if data.target_kind == "user" and target.pk == user.pk:
        raise invalid("target_id", "No puedes reportarte a ti.")

    Report.objects.create(
        note=data.note.strip(),
        reason=reason,
        reporter=user,
        **{TARGET_FIELDS[data.target_kind]: target},
    )


########################################################################################
# La bandeja del equipo


def ensure_moderator(actor: Actor) -> None:
    if not actor.can(P.CONTENT_MODERATE, P.USERS_MANAGE):
        raise ForbiddenError


def target_of(report: Report) -> ReportTargetGet:
    found: Any = report

    if found.target_user_id is not None:
        return ReportTargetGet(
            id=found.target_user_id, kind="user", label=found.target_user.display_name
        )

    if found.target_review_id is not None:
        return ReportTargetGet(
            id=found.target_review_id,
            kind="review",
            label=str(found.target_review.comment)[:120],
        )

    if found.target_point_id is not None:
        return ReportTargetGet(
            id=found.target_point_id, kind="place", label=str(found.target_point.name)
        )

    if found.target_event_id is not None:
        return ReportTargetGet(
            id=found.target_event_id, kind="event", label=str(found.target_event.name)
        )

    # lo reportado ya no existe
    return ReportTargetGet(id=None, kind="user", label="(ya no existe)")


def report_payload(report: Report) -> ReportGet:
    found: Any = report

    return ReportGet(
        created_at=found.created_at,
        id=found.pk,
        note=str(found.note),
        reason=ReportReasonGet(
            code=str(found.reason.code),
            label=str(found.reason.label),
            requires_text=bool(found.reason.requires_text),
        ),
        reporter=found.reporter.display_name,
        resolution_note=str(found.resolution_note),
        resolved_at=found.resolved_at,
        status=REPORT_API[str(found.status)],  # ty: ignore[invalid-argument-type]
        target=target_of(report),
    )


def reports() -> QuerySet:
    return Report.objects.select_related(
        "reason",
        "reporter",
        "target_event",
        "target_point",
        "target_review",
        "target_user",
    )


def reports_sync(actor: Actor, query: ReportQuery) -> Paginated[ReportGet]:
    ensure_moderator(actor)

    found = reports()

    if query.status is not None:
        found = found.filter(status=REPORT_BY_API[query.status])

    if query.target_kind is not None:
        found = found.filter(**{f"{TARGET_FIELDS[query.target_kind]}__isnull": False})

    return paginate(
        found.order_by("created_at", "id"), query, report_payload, ReportGet
    )


def resolve_report_sync(
    actor: Actor,
    report_id: UUID,
    data: ResolveReportPost,
) -> ReportGet:
    ensure_moderator(actor)

    with atomic():
        report: Any = Report.objects.select_for_update().filter(pk=report_id).first()

        if report is None:
            raise NotFoundError(detail="No encontramos ese reporte.")

        if report.status != "pendiente":
            raise ConflictError(detail="Ese reporte ya se resolvió.")

        Report.objects.filter(pk=report.pk).update(
            resolution_note=data.note.strip(),
            resolved_at=now(),
            resolved_by=actor.user,
            status=REPORT_BY_API[data.status],
        )

    return report_payload(reports().get(pk=report_id))


########################################################################################
# Sanciones (`users.manage`)


def sanction_active(sanction: Sanction) -> bool:
    found: Any = sanction

    if found.kind == "advertencia" or found.lifted_at is not None:
        return False

    return found.ends_at is None or found.ends_at > now()


def sanction_payload(sanction: Sanction) -> SanctionGet:
    found: Any = sanction

    return SanctionGet(
        active=sanction_active(sanction),
        created_by=found.created_by.display_name,
        ends_at=found.ends_at,
        id=found.pk,
        kind=SANCTION_API[str(found.kind)],  # ty: ignore[invalid-argument-type]
        lifted_at=found.lifted_at,
        reason=str(found.reason),
        report_id=found.report_id,
        starts_at=found.starts_at,
        user_id=found.user_id,
        user_name=found.user.display_name,
    )


def sanctions() -> QuerySet:
    return Sanction.objects.select_related("created_by", "user")


def ensure_sanctioner(actor: Actor) -> None:
    if not actor.can(P.USERS_MANAGE):
        raise ForbiddenError


def sanctions_sync(actor: Actor, query: SanctionQuery) -> Paginated[SanctionGet]:
    if not actor.can(P.USERS_VIEW, P.USERS_MANAGE):
        raise ForbiddenError

    found = sanctions()

    if query.user_id is not None:
        found = found.filter(user_id=query.user_id)

    if query.active is True:
        found = found.exclude(kind="advertencia").filter(
            Q(ends_at__isnull=True) | Q(ends_at__gt=now()), lifted_at__isnull=True
        )

    return paginate(
        found.order_by("-starts_at", "id"),
        query,
        sanction_payload,
        SanctionGet,
    )


def create_sanction_sync(actor: Actor, data: SanctionPost) -> SanctionGet:
    ensure_sanctioner(actor)

    user: Any = ApiUser.objects.filter(pk=data.user_id).first()

    if user is None:
        raise invalid("user_id", "No encontramos a esa persona.")

    if user.pk == actor.user.pk:
        raise ForbiddenError(detail="No puedes sancionarte a ti.")

    if user.is_superuser and not actor.user.is_superuser:
        raise ForbiddenError(detail="Esa cuenta solo la administra un superusuario.")

    kind: str = SANCTION_BY_API[data.kind]
    moment = now()

    with atomic():
        sanction: Sanction = Sanction.objects.create(
            created_by=actor.user,
            ends_at=(
                moment + timedelta(days=data.days)
                if kind == "suspension" and data.days is not None
                else None
            ),
            kind=kind,
            reason=data.reason.strip(),
            report_id=data.report_id,
            starts_at=moment,
            user=user,
        )

        # suspender o expulsar corta de inmediato sus sesiones
        if kind == "suspension":
            change_status_sync(user, ApiUserStatus.SUSPENDED)
        elif kind == "expulsion":
            change_status_sync(user, ApiUserStatus.EXPELLED)

        notify(
            user.pk,
            "cuenta",
            {
                "advertencia": "Recibiste una advertencia",
                "expulsion": "Tu cuenta fue cerrada",
                "suspension": "Tu cuenta está suspendida",
            }[kind],
            data.reason.strip(),
        )

    return sanction_payload(sanctions().get(pk=sanction.pk))


def lift(record: Sanction, actor_user: ApiUser | None) -> None:
    sanction: Any = record

    Sanction.objects.filter(pk=sanction.pk).update(
        lifted_at=now(), lifted_by=actor_user
    )

    user: Any = ApiUser.objects.get(pk=sanction.user_id)

    still: bool = (
        Sanction.objects
        .exclude(kind="advertencia")
        .exclude(pk=sanction.pk)
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now()), lifted_at__isnull=True)
        .filter(user=user)
        .exists()
    )

    if not still and user.status in {ApiUserStatus.SUSPENDED, ApiUserStatus.EXPELLED}:
        change_status_sync(user, ApiUserStatus.ACTIVE)


def lift_sanction_sync(actor: Actor, sanction_id: UUID) -> SanctionGet:
    ensure_sanctioner(actor)

    with atomic():
        sanction: Any = (
            Sanction.objects.select_for_update().filter(pk=sanction_id).first()
        )

        if sanction is None:
            raise NotFoundError(detail="No encontramos esa sanción.")

        if not sanction_active(sanction):
            raise ConflictError(detail="Esa sanción ya no está vigente.")

        lift(sanction, actor.user)

    return sanction_payload(sanctions().get(pk=sanction_id))


# Las suspensiones con fin que ya terminaron se levantan solas (con `syncevents`).
def expire_sanctions() -> int:
    ended = list(
        Sanction.objects.filter(
            ends_at__lte=now(), kind="suspension", lifted_at__isnull=True
        )
    )

    for sanction in ended:
        with atomic():
            lift(sanction, None)

    return len(ended)
