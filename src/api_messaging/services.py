from typing import TYPE_CHECKING, Any, Final

from django.utils.timezone import now

from api_exceptions.errors import ConflictError, NotFoundError
from api_messaging.models import Message, Participant
from api_messaging.schemas import MessageGet
from api_notifications.services import notify

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from api_auth.models import ApiUser

########################################################################################

# - cuántos mensajes trae una consulta: la app pide los posteriores al último que tiene
PAGE: Final[int] = 200

########################################################################################


# La sala de la reserva, si quien pregunta está dentro; si no, no existe para él.
def participant_of(user: ApiUser, booking_id: UUID) -> Participant:
    participant: Participant | None = (
        Participant.objects
        .select_related("conversation__booking__status")
        .filter(conversation__booking_id=booking_id, user=user)
        .first()
    )

    if participant is None:
        raise NotFoundError(detail="No encontramos esa reserva.")

    return participant


def message_payload(message: Message, viewer: ApiUser) -> MessageGet:
    found: Any = message

    return MessageGet(
        body=str(found.body),
        id=found.pk,
        mine=found.sender_id == viewer.pk,
        sender_id=found.sender_id,
        sent_at=found.sent_at,
    )


def messages_sync(
    user: ApiUser,
    booking_id: UUID,
    after: datetime | None,
) -> list[MessageGet]:
    participant: Any = participant_of(user, booking_id)
    found = Message.objects.filter(conversation_id=participant.conversation_id)

    if after is not None:
        found = found.filter(sent_at__gt=after)

    return [
        message_payload(item, user) for item in found.order_by("sent_at", "id")[:PAGE]
    ]


def send_sync(user: ApiUser, booking_id: UUID, body: str) -> MessageGet:
    participant: Any = participant_of(user, booking_id)

    # la sala de una reserva cancelada queda de solo lectura
    if participant.conversation.booking.status.code == "cancelada":
        raise ConflictError(detail="Esa reserva se canceló: el chat quedó cerrado.")

    message: Message = Message.objects.create(
        body=body.strip(),
        conversation_id=participant.conversation_id,
        sender=user,
    )

    # lo que uno escribe ya lo leyó
    Participant.objects.filter(pk=participant.pk).update(last_read_at=message.sent_at)

    for other in Participant.objects.filter(
        conversation_id=participant.conversation_id
    ).exclude(user=user):
        notify(
            other.user_id,
            "mensaje",
            user.display_name,
            body.strip()[:140],
            {"booking_id": str(booking_id)},
        )

    return message_payload(message, user)


def mark_read_sync(user: ApiUser, booking_id: UUID) -> None:
    participant: Participant = participant_of(user, booking_id)

    Participant.objects.filter(pk=participant.pk).update(last_read_at=now())
