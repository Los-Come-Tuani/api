import logging

from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.core.mail import send_mail

from api_core.config import CONFIG

if TYPE_CHECKING:
    from datetime import timedelta
    from typing import Final

########################################################################################

logger: Final[logging.Logger] = logging.getLogger("api_auth.mail")

########################################################################################


def minutes(delta: timedelta) -> int:
    return max(1, int(delta.total_seconds() // 60))


def lifetime_line() -> str:
    return (
        f"Vence en {minutes(CONFIG.VERIFICATION_LIFETIME)} minutos "
        "y sirve una sola vez."
    )


async def send_email(*, body: str, kind: str, subject: str, to: str) -> bool:
    # Manda un correo sin dejar que un fallo del proveedor rompa la petición. El cuerpo
    # trae códigos de un solo uso: jamás se registra, y del destinatario solo se deja
    # constancia del tipo de correo.
    try:
        sent: int = await sync_to_async(send_mail)(
            subject,
            body,
            CONFIG.DEFAULT_FROM_EMAIL,
            [to],
        )
    except Exception:
        logger.exception("No se pudo enviar el correo de tipo '%s'.", kind)

        return False

    return sent > 0


########################################################################################


async def send_verification_code(*, code: str, to: str) -> bool:
    return await send_email(
        body=(
            f"Tu código para crear tu cuenta de K'Plan es: {code}\n\n"
            f"{lifetime_line()} Si no lo pediste, ignora este mensaje.\n"
        ),
        kind="email",
        subject="Tu código de verificación de K'Plan",
        to=to,
    )


async def send_password_reset_code(*, code: str, to: str) -> bool:
    return await send_email(
        body=(
            f"Tu código para crear una contraseña nueva es: {code}\n\n"
            f"{lifetime_line()} Si no lo pediste, ignora este mensaje: tu contraseña "
            "actual sigue siendo la misma.\n"
        ),
        kind="password_reset",
        subject="Recupera tu contraseña de K'Plan",
        to=to,
    )


async def send_invitation_code(*, code: str, name: str, to: str) -> bool:
    return await send_email(
        body=(
            f"Hola {name}, te invitaron a formar parte del equipo de K'Plan.\n\n"
            f"Tu código para activar tu cuenta y elegir tu contraseña es: {code}\n\n"
            f"{lifetime_line()}\n"
        ),
        kind="invitation",
        subject="Te invitaron al equipo de K'Plan",
        to=to,
    )


async def send_application_decision(  # ruff: ignore[too-many-arguments]
    *,
    approved: bool,
    name: str,
    note: str,
    organization: str,
    reason: str,
    to: str,
) -> bool:
    # lo que el equipo decidió sobre la solicitud de una organización, con el motivo y
    # la nota si se rechazó: sin saber por qué, quien se postuló reintenta a ciegas
    if approved:
        body = (
            f"Hola {name}, aprobamos la solicitud de {organization}.\n\n"
            "Ya puedes entrar al portal de K'Plan con tu correo y tu contraseña.\n"
        )
        subject = "Aprobamos tu solicitud en K'Plan"
    else:
        detail = f"\nNota del equipo: {note}\n" if note else ""
        body = (
            f"Hola {name}, no pudimos aprobar la solicitud de {organization}.\n\n"
            f"Motivo: {reason}.\n{detail}\n"
            "Entra al portal de K'Plan para ver qué corregir y volver a enviarla.\n"
        )
        subject = "Sobre tu solicitud en K'Plan"

    return await send_email(
        body=body,
        kind="application_decision",
        subject=subject,
        to=to,
    )


async def send_provider_decision(  # ruff: ignore[too-many-arguments]
    *,
    approved: bool,
    documents: list[tuple[str, str, str]],
    name: str,
    note: str,
    reason: str,
    renewal: bool,
    to: str,
) -> bool:
    # lo que el equipo decidió sobre un guía o traductor. `documents` son los
    # rechazados, (documento, motivo, nota), para corregirlos sin adivinar
    if approved:
        body = (
            f"Hola {name}, aprobamos la renovación de tus documentos.\n\n"
            "Siguen en vigor y puedes seguir trabajando con K'Plan.\n"
            if renewal
            else f"Hola {name}, aprobamos tu perfil en K'Plan.\n\n"
            "Ya apareces para los turistas: entra a la app con tu correo y tu "
            "contraseña.\n"
        )
        subject = "Aprobamos tu perfil en K'Plan"
    else:
        lines = "".join(
            f"- {document}: {cause}." + (f" {detail}" if detail else "") + "\n"
            for document, cause, detail in documents
        )
        listed = f"\nLo que hay que corregir:\n{lines}" if lines else ""
        detail = f"\nNota del equipo: {note}\n" if note else ""
        body = (
            f"Hola {name}, no pudimos aprobar tu solicitud.\n\n"
            f"Motivo: {reason}.\n{listed}{detail}\n"
            "Entra a la app de K'Plan para ver qué corregir y volver a enviarla.\n"
        )
        subject = "Sobre tu solicitud en K'Plan"

    return await send_email(
        body=body,
        kind="provider_decision",
        subject=subject,
        to=to,
    )


async def send_provider_suspended(*, documents: list[str], name: str, to: str) -> bool:
    # se le venció un documento sin renovación aprobada: deja de recibir contrataciones
    listed = "".join(f"- {document}\n" for document in documents)

    return await send_email(
        body=(
            f"Hola {name}, se venció un documento que te pedimos para trabajar con "
            f"K'Plan:\n\n{listed}\n"
            "Mientras no lo renueves no apareces para los turistas ni recibes "
            "contrataciones nuevas. Entra a la app y sube el documento vigente.\n"
        ),
        kind="provider_suspended",
        subject="Se venció un documento de tu perfil en K'Plan",
        to=to,
    )


async def send_closing_notice(*, days: int, to: str) -> bool:
    return await send_email(
        body=(
            "Recibimos tu solicitud para dar de baja tu cuenta de K'Plan.\n\n"
            f"Tu cuenta quedó inactiva y dentro de {days} días eliminaremos tu "
            "información. Si te arrepientes antes de ese plazo, vuelve a iniciar "
            "sesión desde la opción 'Reactivar mi cuenta'.\n"
        ),
        kind="closing",
        subject="Tu cuenta de K'Plan está en proceso de baja",
        to=to,
    )
