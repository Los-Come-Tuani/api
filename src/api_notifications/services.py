import logging

from typing import TYPE_CHECKING, Any, Final

from django.db.transaction import on_commit
from django.utils.timezone import now

from api_core.services.pages import paginate
from api_exceptions.errors import NotFoundError
from api_notifications import push
from api_notifications.models import DeviceToken, Notification, NotificationPreference
from api_notifications.schemas import NotificationGet, PreferenceGet, UnreadCountGet

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from api_auth.models import ApiUser
    from api_core.schemas.pagination import Paginated
    from api_notifications.schemas import (
        DeviceTokenPost,
        NotificationQuery,
        PreferencePut,
    )

########################################################################################

logger = logging.getLogger(__name__)

# - las clases de aviso, en el orden en que se muestran las preferencias
KINDS: Final[dict[str, str]] = {
    "mensaje": "Mensajes nuevos del chat",
    "reserva": "Reservas: nuevas, canceladas o por empezar",
    "convocatoria": "Postulaciones y convocatorias",
    "resena": "Reseñas que me dejan",
    "pago": "Pagos, reembolsos y retiros",
    "cuenta": "Avisos de mi cuenta",
}

########################################################################################
# Emitir


def push_enabled_for(user_id: UUID, kind: str) -> bool:
    preference: NotificationPreference | None = NotificationPreference.objects.filter(
        kind=kind, user_id=user_id
    ).first()

    return True if preference is None else bool(preference.push_enabled)


def deliver(notification_id: UUID) -> None:
    notification: Any = Notification.objects.filter(pk=notification_id).first()

    if notification is None:
        return

    tokens = list(DeviceToken.objects.filter(user_id=notification.user_id))
    status: str = "omitido"

    for device in tokens:
        try:
            if push.send(
                str(device.token),
                str(notification.title),
                str(notification.body),
                {"kind": str(notification.kind), **notification.data},
            ):
                status = "enviado"
            else:
                DeviceToken.objects.filter(pk=device.pk).delete()
        except Exception:
            # un aviso que no sale no rompe lo que lo causó: queda en la bandeja
            logger.exception("No salió el aviso %s", notification_id)
            status = "fallido" if status != "enviado" else status

    Notification.objects.filter(pk=notification_id).update(push_status=status)


# Deja el aviso en la bandeja y, si la persona lo quiere y hay Firebase, lo manda al
# teléfono cuando la transacción que lo causó se confirma.
def notify(
    user_id: UUID,
    kind: str,
    title: str,
    body: str,
    data: Mapping[str, str] | None = None,
) -> None:
    notification: Notification = Notification.objects.create(
        body=body,
        data=dict(data or {}),
        kind=kind,
        title=title,
        user_id=user_id,
    )

    if push.enabled() and push_enabled_for(user_id, kind):
        on_commit(lambda: deliver(notification.pk))


########################################################################################
# La bandeja


def notification_payload(notification: Notification) -> NotificationGet:
    found: Any = notification

    return NotificationGet(
        body=str(found.body),
        created_at=found.created_at,
        data={str(key): str(value) for key, value in found.data.items()},
        id=found.pk,
        kind=str(found.kind),
        read=found.read_at is not None,
        title=str(found.title),
    )


def notifications_sync(
    user: ApiUser, query: NotificationQuery
) -> Paginated[NotificationGet]:
    found = Notification.objects.filter(user=user)

    if query.unread:
        found = found.filter(read_at__isnull=True)

    return paginate(
        found.order_by("-created_at", "id"),
        query,
        notification_payload,
        NotificationGet,
    )


def mark_read_sync(user: ApiUser, notification_id: UUID) -> NotificationGet:
    notification: Notification | None = Notification.objects.filter(
        pk=notification_id, user=user
    ).first()

    if notification is None:
        raise NotFoundError(detail="No encontramos ese aviso.")

    Notification.objects.filter(pk=notification.pk, read_at__isnull=True).update(
        read_at=now()
    )

    return notification_payload(Notification.objects.get(pk=notification.pk))


def unread_count_sync(user: ApiUser) -> UnreadCountGet:
    return UnreadCountGet(
        count=Notification.objects.filter(read_at__isnull=True, user=user).count()
    )


def mark_all_read_sync(user: ApiUser) -> None:
    Notification.objects.filter(read_at__isnull=True, user=user).update(read_at=now())


########################################################################################
# Teléfonos y preferencias


def register_token_sync(user: ApiUser, data: DeviceTokenPost) -> None:
    # el mismo teléfono con otra cuenta pasa a la nueva
    DeviceToken.objects.update_or_create(
        token=data.token,
        defaults={"last_seen_at": now(), "platform": data.platform, "user": user},
    )


def remove_token_sync(user: ApiUser, token: str) -> None:
    DeviceToken.objects.filter(token=token, user=user).delete()


def preferences_sync(user: ApiUser) -> list[PreferenceGet]:
    stored: dict[str, bool] = {
        str(item.kind): bool(item.push_enabled)
        for item in NotificationPreference.objects.filter(user=user)
    }

    return [
        PreferenceGet(kind=kind, label=label, push_enabled=stored.get(kind, True))
        for kind, label in KINDS.items()
    ]


def update_preferences_sync(user: ApiUser, data: PreferencePut) -> list[PreferenceGet]:
    for item in data.preferences:
        if item.kind not in KINDS:
            continue

        NotificationPreference.objects.update_or_create(
            kind=item.kind,
            user=user,
            defaults={"push_enabled": item.push_enabled},
        )

    return preferences_sync(user)
