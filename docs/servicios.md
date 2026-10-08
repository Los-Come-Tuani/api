---
icon: lucide/handshake
---

# Guías, reservas, chat y reseñas

Lo que pasa entre el turista y el guía: encontrarlo, reservarlo, hablar con él y calificarse
al terminar. Es la fase F7 de la [hoja de ruta](hoja-de-ruta.md) y sigue el modelo de
dominio de [servicios](modelo-dominio/modulos/servicios.md),
[mensajería](modelo-dominio/modulos/mensajeria.md) y
[reputación](modelo-dominio/modulos/reputacion.md).

## Lo que se decidió

- **Dos caminos según el circuito.** En un circuito oficial (creativo, especial de K'Plan o
  cualquiera que el turista no creó ni modificó) el guía publica sus **salidas** y el
  turista reserva una. En un itinerario propio del turista (armado o ajustado por él), el
  turista publica una **convocatoria**, los guías se postulan con su precio y él elige.
- La reserva se confirma al crearse y el monto queda congelado
  ([D-20](modelo-dominio/decisiones.md#d-20)). Desde F8 abre su cobro con la pasarela
  (hoy, manual): ver [Cobros, comisiones y retiros](finanzas.md).
- El turista cancela gratis **hasta 24 horas antes**; el guía cancela con un motivo.
- Chat por **consultas periódicas**: la app pide los mensajes posteriores al último que
  tiene.
- Reseñas **publicadas al instante**; el reseñado puede impugnarlas y el equipo con
  `content.moderate` decide.

## Los guías que ve el turista (públicas)

| Ruta                          | Qué devuelve                                                                                                                                                                                              |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET guide/`                  | Prestadores activos, de mejor a peor calificados (los nuevos al final). Paginado. Filtros: `city` (código: los de esa ciudad y los de todo el país), `language` (código), `service` (`guia`, `traductor`) |
| `GET guide/{id}/`             | Uno, con sus últimas reseñas (`reviews`) y sus próximas salidas (`departures`)                                                                                                                            |
| `GET circuit/{id}/departure/` | Las próximas salidas de guía de un circuito oficial                                                                                                                                                       |

Un guía: `{ id, user_id, name, photo, presentation, services, languages: [{ code, name,
level }], city, carries_tourists, rating, reviews_count }`. `id` es su perfil de prestador
(el de `guide/{id}/`) y `user_id` su cuenta (la de `POST report/` con `target_kind: "user"`).
`rating` es nulo sin reseñas. Cada reseña del perfil: `{ id, rating, comment, author,
created_at }` (`id` sirve para reportarla).

Una salida: `{ id, circuit: { id, title, kind, city }, guide: { id, name, photo }, date,
start_time, capacity, booked, remaining, exclusive, transport_included, note, cancelled,
price_adult, price_child }`. Una salida `exclusive` (en un circuito privado) la toma la
primera reserva; en una de grupo, varias reservas comparten los cupos.

## Salidas (el guía, sesión de la app)

| Ruta                          | Qué hace                                                                          |
| ----------------------------- | --------------------------------------------------------------------------------- |
| `GET departure/`              | Sus próximas salidas                                                              |
| `POST departure/`             | `{ circuit_id, date, start_time, capacity?, transport_included?, note? }` (`201`) |
| `PATCH departure/{id}/`       | `capacity` (no menos de lo reservado), `transport_included`, `note`               |
| `POST departure/{id}/cancel/` | `{ reason }`: la cancela y cancela sus reservas                                   |

Solo un guía aprobado (prestador activo con el servicio de guía) publica salidas (`403`). El
circuito tiene que estar publicado y ser de su ciudad (o el guía, de todo el país). Un guía
no sale dos veces a la misma hora (`409`).

## Convocatorias y postulaciones

| Ruta                                | Quién   | Qué hace                                                                                    |
| ----------------------------------- | ------- | ------------------------------------------------------------------------------------------- |
| `GET service-request/`              | Turista | Las suyas, con sus postulaciones                                                            |
| `POST service-request/`             | Turista | `{ itinerary_id, date, start_time, adults?, children?, max_fee?, note?, city_id? }` (`201`) |
| `GET service-request/{id}/`         | Turista | Una, con sus postulaciones (de menor a mayor precio)                                        |
| `POST service-request/{id}/accept/` | Turista | `{ application_id }`: crea la reserva (`201`) y cierra la convocatoria                      |
| `POST service-request/{id}/cancel/` | Turista | La cancela                                                                                  |
| `GET open-request/`                 | Guía    | Las abiertas de su ciudad (o todas, si es de todo el país), con `applied`                   |
| `POST open-request/{id}/apply/`     | Guía    | `{ fee, message? }` (`201`; `409` si ya se postuló)                                         |
| `GET application/mine/`             | Guía    | Sus postulaciones                                                                           |
| `POST application/{id}/withdraw/`   | Guía    | Retira una que todavía no se resolvió                                                       |

Una postulación: `{ id, request_id, request: { itinerary: { id, title, stops }, city, date,
start_time, adults, children }, guide, fee, message, status, created_at }`; `request` resume
la convocatoria para la lista del guía.

Una convocatoria es para un itinerario **propio** (`adjusted`): uno que sigue un circuito
oficial responde `400` (se reserva una salida). La ciudad, si no llega, es la de la primera
parada. Un itinerario tiene una convocatoria abierta a la vez. Con `max_fee`, nadie se
postula por más (`400`). Aceptar comprueba que el guía siga libre a esa hora (`409`); las
demás postulaciones quedan rechazadas. Las convocatorias cuya fecha pasó vencen solas (y
con `syncevents`).

## Reservas

| Ruta                        | Quién          | Qué hace                                                           |
| --------------------------- | -------------- | ------------------------------------------------------------------ |
| `GET booking/`              | Turista o guía | Las suyas (`role` dice cómo las ve)                                |
| `POST booking/`             | Turista        | `{ departure_id, adults?, children? }`: reserva una salida (`201`) |
| `GET booking/{id}/`         | Los dos        | Una                                                                |
| `POST booking/{id}/cancel/` | Los dos        | `{ reason? }` (el guía tiene que dar el motivo)                    |
| `POST booking/{id}/start/`  | Guía           | El día del recorrido: pasa a `in_progress`                         |
| `POST booking/{id}/finish/` | Guía           | Terminó: pasa a `delivered`                                        |

```json
{
  "id": "…",
  "role": "tourist",
  "status": "confirmed",
  "date": "2026-10-10",
  "start_time": "08:30",
  "adults": 2,
  "children": 1,
  "amount": 600,
  "payment_status": "pendiente",
  "payment_instructions": "El equipo de K'Plan te escribirá para confirmar el pago…",
  "circuit": { "id": "…", "title": "…" },
  "itinerary": null,
  "guide": { "id": "…", "name": "Pedro", "photo": null },
  "tourist": { "id": "…", "name": "Ana" },
  "departure_id": "…",
  "cancel_deadline": "…",
  "can_cancel": true,
  "cancelled_at": null,
  "cancel_reason": "",
  "created_at": "…",
  "unread_messages": 0,
  "reviewed": false
}
```

Estados: `confirmed`, `in_progress`, `delivered`, `closed` y `cancelled`. Una reserva
prestada se cierra (`closed`) cuando además está pagada: ahí se guarda la comisión y el
resto entra al saldo del guía ([finanzas](finanzas.md)). `payment_status` es `sin_cobro`
(gratis), `pendiente`, `pagado`, `por_reembolsar`, `reembolsado` o `anulado`; cancelar
anula el pago pendiente o deja por reembolsar el ya hecho. El monto de una salida es
`price_adult × adults + price_child × children` del circuito; el de una convocatoria, el
`fee` del guía elegido. Una reserva de otra persona responde `404`. Pasadas las 24 horas
previas el turista ya no cancela (`409`).

## Chat

| Ruta                              | Qué hace                                                                      |
| --------------------------------- | ----------------------------------------------------------------------------- |
| `GET booking/{id}/message/`       | Los mensajes, del más viejo; con `after` (fecha y hora), solo los posteriores |
| `POST booking/{id}/message/`      | `{ body }` (hasta 2000 caracteres; `201`)                                     |
| `POST booking/{id}/message/read/` | Quien pregunta leyó todo (`204`)                                              |

Solo el turista y el guía de la reserva (`404` para los demás). Un mensaje: `{ id,
sender_id, mine, body, sent_at }`. La reserva cuenta `unread_messages`. En una reserva
cancelada el chat queda de solo lectura (`409` al escribir). Sugerido: preguntar cada 5 a 10
segundos con la conversación abierta.

## Reseñas

| Ruta                                | Quién              | Qué hace                                                                                 |
| ----------------------------------- | ------------------ | ---------------------------------------------------------------------------------------- |
| `POST booking/{id}/review/`         | Turista o guía     | `{ rating, comment? }` (1 a 5) cuando el recorrido terminó (`409` antes o si ya la dejó) |
| `POST review/{id}/dispute/`         | El reseñado        | `{ reason }`: pide que el equipo la revise                                               |
| `GET review-dispute/`               | `content.moderate` | Las impugnaciones, de la más vieja. Filtro `status` (`pending`, `upheld`, `rejected`)    |
| `POST review-dispute/{id}/resolve/` | `content.moderate` | `{ upheld, note? }`: con `upheld` la reseña se oculta                                    |

La reseña del turista alimenta el promedio del guía (`rating` y `reviews_count` de su
perfil) y el del circuito, si la reserva era de uno. Ocultarla los recalcula.

## Al desplegar

- Migraciones nuevas `apiservices.0001`, `apimessaging.0001` y `apireputation.0001` (siembran
  los estados de convocatoria y de reserva).
- `syncevents` también vence las convocatorias.

## Lo que queda para después

- El cobro en línea con una pasarela real (hoy el equipo confirma los pagos a mano).
- El chat en tiempo real (WebSocket) y el chat antes de reservar.
- La agenda de llegadas para los lugares (`visit-events`) y el avance del viaje parada por
  parada.
- La lectura de reservas por el equipo para atender incidencias.

## Dónde se aparta del modelo

- La salida guiada sobre un circuito oficial hace de `recorrido` + `recorrido_dia`: el
  producto del guía es guiar un circuito oficial en una fecha y hora.
- La reserva no pasa por `pendiente_pago` ni `expirada`: se confirma al nacer y el pago va
  aparte (`estado_pago`).
- Las convocatorias y reservas cuelgan de la cuenta, no de `perfil_turista`.
- No hay tablas `transicion_*`: los cambios quedan en el historial (`pghistory`).
