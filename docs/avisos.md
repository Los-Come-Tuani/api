---
icon: lucide/bell
---

# Avisos, reportes y sanciones

La bandeja de avisos de cada cuenta (y su envío al teléfono por Firebase), los reportes que
cualquiera puede hacer y las sanciones del equipo. Es la fase F8 de la
[hoja de ruta](hoja-de-ruta.md) y sigue el modelo de dominio de
[notificaciones](modelo-dominio/modulos/notificaciones.md) y de
[moderación](modelo-dominio/modulos/moderacion.md).

## Lo que se decidió

- **Todo aviso queda en la bandeja** de la cuenta. Si además hay credenciales de Firebase
  (`FCM_PROJECT_ID` y `FCM_SERVICE_ACCOUNT`) y la persona no apagó esa clase de aviso, sale
  al teléfono por Firebase Cloud Messaging cuando se confirma lo que lo causó. Sin
  credenciales, solo la bandeja.
- Un aviso que no sale no rompe nada: queda en la bandeja con `push_status` `fallido`. Un
  teléfono que Firebase da por muerto se olvida.
- Entran los **reportes** (de una persona, una reseña, un lugar o un evento) y las
  **sanciones** (advertencia, suspensión con o sin fin, expulsión).

## La bandeja (cualquier sesión)

| Ruta                           | Qué hace                                                               |
| ------------------------------ | ---------------------------------------------------------------------- |
| `GET notification/`            | Los avisos, del más nuevo. Paginado. `unread=true`: solo los no leídos |
| `GET notification/unread/`     | `{ count }`: cuántos no ha leído, para el punto de la campana          |
| `POST notification/{id}/read/` | Lo marca leído y lo devuelve                                           |
| `POST notification/read-all/`  | Marca todo leído (`204`)                                               |

```json
{
  "id": "…",
  "kind": "mensaje",
  "title": "Ana",
  "body": "¡Hola!",
  "data": { "booking_id": "…" },
  "read": false,
  "created_at": "…"
}
```

`data` dice a qué pantalla lleva. Un aviso de otra cuenta responde `404`.

| `kind`           | Cuándo llega                                                                                                                                                                       | `data`                         |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| `mensaje`        | Un mensaje nuevo en el chat de una reserva                                                                                                                                         | `booking_id`                   |
| `reserva`        | Al guía: una reserva nueva o el turista aceptó su postulación. A los dos: una reserva cancelada (también cuando el guía cancela su salida o el circuito se despublica o se retira) | `booking_id`                   |
| `convocatoria`   | Al turista: un guía se postuló a su convocatoria                                                                                                                                   | `request_id`                   |
| `resena`         | Le dejaron una reseña                                                                                                                                                              | `booking_id`, `review_id`      |
| `pago`           | Pago confirmado o reembolsado (turista); retiro pagado o rechazado (guía)                                                                                                          | `booking_id` o `withdrawal_id` |
| `cuenta`         | Una sanción (advertencia, suspensión o expulsión)                                                                                                                                  | —                              |
| `solicitud_demo` | Al equipo con `demos.manage`: alguien pidió una demostración desde la landing ([Landing](landing.md))                                                                              | `demo_request_id`              |

## Teléfonos y preferencias

| Ruta                           | Qué hace                                                                                                                                                             |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `POST device-token/`           | `{ token, platform }` (`android`, `ios` o `web`): al iniciar sesión y cada vez que Firebase da otro token (`204`). El mismo teléfono con otra cuenta pasa a la nueva |
| `POST device-token/remove/`    | `{ token }`: al cerrar sesión (`204`)                                                                                                                                |
| `GET notification-preference/` | `[{ kind, label, push_enabled }]`, una por clase de aviso                                                                                                            |
| `PUT notification-preference/` | `{ preferences: [{ kind, push_enabled }] }`: solo cambia las que llegan                                                                                              |

Apagar una clase solo apaga el envío al teléfono: el aviso sigue llegando a la bandeja.

El mensaje de Firebase lleva `notification` (`title`, `body`) y `data` con `kind` más lo de
la tabla de arriba, para que la app abra la pantalla al tocarlo.

## Reportes

| Ruta                        | Quién                               | Qué hace                                                                                        |
| --------------------------- | ----------------------------------- | ----------------------------------------------------------------------------------------------- |
| `GET report/reason/`        | Cualquier sesión                    | `[{ code, label, requires_text }]`                                                              |
| `POST report/`              | Cualquier sesión                    | `{ target_kind, target_id, reason, note? }` (`204`)                                             |
| `GET report/`               | `content.moderate` o `users.manage` | La bandeja, del más viejo. Filtros `status` (`pending`, `handled`, `dismissed`) y `target_kind` |
| `POST report/{id}/resolve/` | `content.moderate` o `users.manage` | `{ status, note? }`: `handled` (se actuó) o `dismissed` (no procede)                            |

`target_kind` es `user`, `review`, `place` o `event`. Los motivos: `contenido_inapropiado`,
`acoso`, `fraude`, `informacion_falsa`, `incumplimiento` y `otro` (con `otro` hay que
escribir `note`, si no `400`). Nadie se reporta a sí mismo (`400`). Quien reporta no ve la
bandeja: la respuesta es vacía.

Un reporte en la bandeja: `{ id, target: { kind, id, label }, reason: { code, label,
requires_text }, note, reporter, status, created_at, resolved_at, resolution_note }`. `label`
es el nombre de la persona, del lugar o del evento, o un extracto de la reseña. Resolver uno
ya resuelto responde `409`.

## Sanciones

| Ruta                       | Permiso                       | Qué hace                                                |
| -------------------------- | ----------------------------- | ------------------------------------------------------- |
| `GET sanction/`            | `users.view` o `users.manage` | Paginado, de la más nueva. Filtros `user_id` y `active` |
| `POST sanction/`           | `users.manage`                | `{ user_id, kind, reason, days?, report_id? }` (`201`)  |
| `POST sanction/{id}/lift/` | `users.manage`                | La levanta                                              |

`kind` es `warning`, `suspension` o `expulsion`. Una suspensión con `days` termina sola
(`syncevents` la levanta); sin `days` dura hasta que se levante. Suspender deja la cuenta
`suspended` y expulsar la deja `expelled`; las dos cortan de inmediato sus sesiones.
Levantar la última sanción vigente devuelve la cuenta a `active`. La persona recibe un aviso
`cuenta` con el motivo. Nadie se sanciona a sí mismo y una cuenta de superusuario solo la
sanciona otro superusuario (`403`).

Una sanción: `{ id, user_id, user_name, kind, reason, starts_at, ends_at, created_by,
report_id, lifted_at, active }`. Levantar una que ya no está vigente responde `409`.

## Al desplegar

- Migraciones nuevas `apinotifications.0001` y `apireports.0001` (siembra los motivos de
  reporte).
- Para el envío al teléfono: crear el proyecto de Firebase, una cuenta de servicio con
  permiso de Firebase Cloud Messaging y definir `FCM_PROJECT_ID` y `FCM_SERVICE_ACCOUNT`
  (el JSON de la cuenta de servicio en una línea). Es un secreto: solo en las variables del
  servicio. La app necesita su propio `google-services.json` del mismo proyecto.
- `syncevents` (diario) también levanta las suspensiones vencidas.

## Lo que queda para después

- Avisos por correo y el recordatorio del día antes del recorrido.
- Mandar los avisos al teléfono desde una cola de tareas en lugar de al terminar la
  petición.
- Que el reporte resuelto avise a quien reportó.

## Dónde se aparta del modelo

- No hay `plantilla_notificacion`: el texto de cada aviso vive en el código que lo emite.
- La sanción cambia el estado de la cuenta con el mismo servicio que usa el equipo en
  `POST user-status/`; no hay un estado aparte de "sancionado".
