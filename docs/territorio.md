---
icon: lucide/map-pinned
---

# Lugares, circuitos e itinerarios

Los lugares que la app muestra en el mapa, los circuitos oficiales que se recorren sobre
ellos y los itinerarios que arma cada turista. Es la fase F4 de la
[hoja de ruta](hoja-de-ruta.md) y sigue el modelo de dominio de
[territorio](modelo-dominio/modulos/territorio.md) e
[itinerarios](modelo-dominio/modulos/itinerarios.md).

## Lo que se decidió

- **Circuitos**: el equipo de K'Plan con `circuits.manage` los crea en cualquier ciudad;
  cada alcaldía verificada, solo los de su ciudad. Hay tres tipos: `creative` (lo organiza
  la alcaldía de la ciudad; siempre en grupo y da tres insignias extra), `kplan` (especial
  de K'Plan, con insignias extra y temporada opcional) y `private` (del catálogo, cada
  grupo agenda el suyo).
- **Campos**: la base del modelo (estado, versión, paradas ordenadas) más lo que ya usan el
  portal y la app: precios, horarios de salida, dificultad, punto de encuentro, qué
  incluye, temporada e insignias extra.
- **La ficha de un lugar** la edita su dueño y **sale de inmediato** en la app; el equipo
  con `places.manage` puede corregirla después.
- **Los circuitos propios del turista** ("Mi circuito") se guardan en el API como
  itinerarios ([D-33](modelo-dominio/decisiones.md#d-33)).

## Lugares

Un lugar (`punto_interes`) existe aunque ningún circuito lo incluya
([D-18](modelo-dominio/decisiones.md#d-18)). Tiene, a lo sumo, una organización dueña:

| Dueño         | Cómo llega                                                       | Qué puede hacer                                  |
| ------------- | ---------------------------------------------------------------- | ------------------------------------------------ |
| Comercio      | Al **aprobar** su solicitud se le crea su lugar con su nombre, dirección, ubicación y la foto del platillo | Editar la ficha y publicar novedades. No crea otros lugares ni retira el suyo |
| Alcaldía      | Los crea ella en su ciudad, o el equipo se los asigna            | Crear, editar, retirar y devolver los suyos      |
| Institución   | El equipo se lo asigna                                           | Editar la ficha y publicar novedades             |
| Ninguno       | Los crea el equipo                                               | Los administra el equipo                         |

Un comercio tiene un solo lugar. La insignia de un lugar (`has_badge`) solo la cambia el
equipo con `places.manage` (la activación pagada llega con F6). Retirar un lugar lo saca
de la app sin borrarlo; uno que está en un circuito publicado no se retira (`409`).

### Rutas de la app (públicas, sin sesión)

| Ruta                    | Qué devuelve                                                                 |
| ----------------------- | ---------------------------------------------------------------------------- |
| `GET stop/`             | Lugares activos, paginados. Filtros: `city` (código, `leon`), `pillar` (`historia`...), `search`, `ids` (varios, separados por comas) |
| `GET stop/{id}/`        | Un lugar activo con su ficha (`profile`) y sus últimas diez novedades visibles (`posts`) |
| `GET catalog/pillar/`   | Los pilares culturales: `historia`, `cultura`, `gastronomia`, `naturaleza`, `aventura` |

```json
{
  "id": "…", "name": "Catedral de León",
  "pillar": { "code": "historia", "label": "Historia" },
  "city": { "id": "…", "code": "leon", "name": "León" },
  "address": "…", "description": "…", "tip": "…",
  "latitude": 12.4343, "longitude": -86.8780,
  "opens_at": "08:00", "closes_at": "17:00",
  "visit_minutes": 45, "has_badge": true, "rating": 4.8, "reviews_count": 210,
  "images": [{ "key": "…", "url": "https://…" }],
  "owner": { "kind": "municipality", "id": "…", "name": "Alcaldía de León" }
}
```

Sin horario (`opens_at` y `closes_at` nulos) es un lugar que no cierra. La primera imagen
es la portada. La `url` de una imagen del almacenamiento vence en minutos: se pide otra vez
el lugar para renovarla.

### Rutas del portal (sesión con cookies)

| Ruta                        | Quién                                                      | Qué hace                                  |
| --------------------------- | ---------------------------------------------------------- | ----------------------------------------- |
| `GET place/`                | `places.view`: todos. Una organización verificada: los suyos | Paginado. Filtros: `city_id`, `pillar`, `owner_kind` (`business`, `institution`, `municipality` o `none`), `owner_id`, `active`, `search` |
| `POST place/`               | `places.manage` (con `city_id`) o una alcaldía (en su ciudad) | Crea un lugar (`201`)                     |
| `GET place/{id}/`           | Quien lo ve                                                | El lugar, con `active`, `created_at` y en cuántos circuitos publicados está |
| `PATCH place/{id}/`         | `places.manage` o su dueño                                 | Cambia lo que llega                       |
| `DELETE place/{id}/`        | `places.manage` o la alcaldía dueña                        | Lo retira (`204`)                         |
| `PUT place/{id}/owner/`     | `places.manage` u `organizations.manage`                   | `{ kind, id }` le da dueño; `{}`, lo devuelve al equipo |
| `GET place/{id}/profile/`   | Quien lo ve                                                | La ficha                                  |
| `PUT place/{id}/profile/`   | `places.manage` o su dueño                                 | Reemplaza la ficha completa               |
| `GET post/`                 | Quien ve el lugar (`place_id` filtra)                      | Novedades, de la más reciente             |
| `POST post/`                | `places.manage` o el dueño del lugar                       | `{ place_id, title, body, image_key?, visible? }` (`201`) |
| `PATCH post/{id}/`          | El dueño, `places.manage` o `content.moderate`             | Cambia lo que llega; `visible: false` la oculta |
| `DELETE post/{id}/`         | El dueño, `places.manage` o `content.moderate`             | La borra (`204`)                          |

Un lugar de otra organización responde `404`, no `403`.

Cuerpo de `POST place/`: `{ city_id?, pillar, name, description?, address?, latitude,
longitude, opens_at?, closes_at?, visit_minutes?, tip?, has_badge?, images? }`. Las horas
van como `"HH:MM"`, las dos o ninguna, y el cierre después de la apertura. Las coordenadas
caen dentro de Nicaragua. `images` es una lista de claves (hasta ocho) de archivos subidos
con `POST /upload/` (`kind: "place-photo"`); las que el lugar ya tiene se mandan tal cual.

Cuerpo de la ficha:

```json
{
  "offerings": [{ "name": "Vigorón", "description": "", "price": 120 }],
  "amenities": ["card", "wifi"],
  "languages": ["Español", "Inglés"],
  "contact": { "phone": "+505 2311 0000", "whatsapp": "", "email": "",
               "website": "", "instagram": "", "facebook": "" }
}
```

El precio de una oferta es orientativo, en córdobas; nulo es "a consultar".

## Circuitos

| Estado        | En la app | Se edita |
| ------------- | --------- | -------- |
| `draft`       | no        | sí       |
| `published`   | **sí**    | sí       |
| `unpublished` | no        | sí       |
| `retired`     | no        | **no**   |

`version` sube **solo** cuando cambian las paradas o su orden: la app la compara con la que
tiene para saber si redibuja el recorrido ([RF-A-06](requerimientos/funcionales/portal-alcaldias.md#rf-a-06)).
Corregir el título no la mueve.

### Rutas de la app (públicas)

| Ruta               | Qué devuelve                                                         |
| ------------------ | -------------------------------------------------------------------- |
| `GET circuit/`     | Los publicados, sin paginar. Filtros: `city` (código), `kind`        |
| `GET circuit/{id}/`| Uno publicado con sus paradas (`stops`, cada una con el lugar completo) |

```json
{
  "id": "…", "kind": "creative", "status": "published",
  "city": { "id": "…", "code": "leon", "name": "León" },
  "municipality": { "id": "…", "name": "Alcaldía de León" },
  "title": "…", "short_title": "…", "subtitle": "…", "description": "…",
  "category": "city", "difficulty": "easy", "travel_mode": "walking",
  "price_adult": 250, "price_child": 0,
  "recommendations": "…", "includes": "…", "notes": "…",
  "meeting_point": "…", "meeting_latitude": 12.43, "meeting_longitude": -86.87,
  "start_times": ["08:30", "14:00"],
  "bonus_badges": 3, "booking_mode": "group",
  "available_from": null, "available_until": null,
  "version": 1, "rating": 4.7, "reviews_count": 98,
  "images": [{ "key": "…", "url": "…" }],
  "stop_ids": ["…", "…"],
  "route": [{ "point_id": "…", "name": "…", "latitude": 12.43, "longitude": -86.87,
              "visit_minutes": 45, "leg_minutes": null }],
  "badges": 5, "duration_minutes": 165,
  "created_at": "…", "published_at": "…",
  "stops": [{ "order": 0, "point": { "…": "un lugar" }, "directions": "", "leg_minutes": null }]
}
```

`category` es `city`, `nature` o `culture`; `difficulty`, `easy` o `moderate`. `badges` son
las insignias de sus paradas más las extra; `duration_minutes`, el tiempo de visita de las
paradas más los traslados: el escrito a mano (`leg_minutes`) o, si es nulo, el estimado con
la distancia y `travel_mode`, con la misma cuenta que el portal y la app. La
lista no trae `stops`: trae `stop_ids` y `route` (lo mínimo de cada parada para trazar el
recorrido y calcular la duración sin pedir los lugares).

### Rutas del portal

| Ruta                           | Quién                                                         | Qué hace                         |
| ------------------------------ | ------------------------------------------------------------- | -------------------------------- |
| `GET official-circuit/`        | `circuits.view`: todos. Una alcaldía verificada: los de su ciudad | Paginado, sin los retirados salvo `status=retired`. Filtros: `city_id`, `kind`, `status`, `search` |
| `POST official-circuit/`       | `circuits.manage` o una alcaldía                              | Crea (`201`)                     |
| `GET official-circuit/{id}/`   | Quien lo ve                                                   | Con sus paradas                  |
| `PUT official-circuit/{id}/`   | `circuits.manage` o la alcaldía que lo organiza               | Reemplaza todo                   |
| `DELETE official-circuit/{id}/`| `circuits.manage` o la alcaldía que lo organiza               | Lo retira para siempre (`204`)   |
| `GET official-circuit/{id}/departure/` | Quien lo ve                                           | Sus próximas salidas de guía, también las canceladas y aunque el circuito ya no esté publicado (la forma de [servicios](servicios.md)) |

Un circuito de otra ciudad no existe para una alcaldía, ni por identificador
([RF-A-03](requerimientos/funcionales/portal-alcaldias.md#rf-a-03)); los del equipo en su
ciudad los ve pero no los edita (`403`).

Cuerpo de `POST` y `PUT`:

```json
{
  "kind": "private", "city_id": "…",
  "title": "…", "short_title": "…", "subtitle": "…", "description": "…",
  "category": "city", "difficulty": "easy", "travel_mode": "walking",
  "price_adult": 250, "price_child": 0,
  "recommendations": "", "includes": "", "notes": "",
  "meeting_point": "…", "meeting_latitude": 12.43, "meeting_longitude": -86.87,
  "start_times": ["08:30"],
  "bonus_badges": 0, "booking_mode": "private",
  "available_from": null, "available_until": null,
  "images": ["circuit-photo/…"],
  "stops": [{ "point_id": "…", "directions": "", "leg_minutes": null }],
  "status": "draft"
}
```

Reglas:

- Entre dos y diez paradas, sin repetir, activas y de la ciudad del circuito.
- La alcaldía siempre crea `creative` de su ciudad: `kind` se ignora y otra `city_id`
  responde `400`. Un creativo del equipo queda a nombre de la alcaldía verificada de esa
  ciudad; sin ella, `400`.
- Cada tipo fija lo suyo: `creative` es en grupo y da tres insignias; `private` es privado,
  sin extras ni temporada; `kplan` da entre una y cinco y elige `booking_mode` y la
  temporada (las dos fechas o ninguna).
- Publicar (`status: "published"`) pide al menos una foto y un horario.
- En `PUT`, `status: "draft"` sobre algo que ya se publicó lo deja `unpublished`.
- Despublicar o retirar un circuito **cancela sus próximas salidas de guía y sus reservas**:
  el pago pendiente se anula, el cobrado queda por reembolsar y el turista y el guía
  reciben un aviso `reserva`.
- Con menos de dos paradas, `field_errors["body.stops"]` dice cuántas hacen falta.
- `images` son claves de `POST /upload/` con `kind: "circuit-photo"`.

## Itinerarios del turista

"Mi circuito" de la app. Cada quien ve y cambia solo los suyos (el de otra persona responde
`404`). Piden sesión (en la app, el `Bearer`).

| Ruta                     | Qué hace                                                       |
| ------------------------ | -------------------------------------------------------------- |
| `GET itinerary/`         | Los suyos, del más nuevo al más viejo                          |
| `POST itinerary/`        | Crea uno (`201`)                                               |
| `GET itinerary/{id}/`    | Uno                                                            |
| `PATCH itinerary/{id}/`  | Cambia lo que llega                                            |
| `DELETE itinerary/{id}/` | Lo saca de la colección (`204`; la fila queda para las métricas) |

Tres maneras de empezar (`POST`):

- `{ "title", "circuit_id" }`: **sigue** un circuito publicado tal cual. No copia nada:
  `stops` son las del circuito vivo, y una corrección de la alcaldía le llega.
- `{ "title", "circuit_id", "stop_ids" }`: una copia propia que salió de ese circuito.
- `{ "title", "stop_ids"? }`: desde cero.

También acepta `start_time` (`"HH:MM"`, por defecto `09:00`), `travel_mode` (`walking`,
`vehicle`), `pace` (`relaxed`, `balanced`, `intense`) y `fixed_arrivals`.

`PATCH` acepta `title`, `stop_ids`, `start_time`, `travel_mode`, `pace` y `fixed_arrivals`
(posición de la parada, como texto, a minutos desde la medianoche: `{ "0": 600 }`).
**Cambiar las paradas de uno que sigue un circuito lo vuelve una copia propia, y eso no se
revierte**: `adjusted` pasa a `true`, `followed_circuit` a nulo y las paradas guardan su
nombre y sus coordenadas ([D-16](modelo-dominio/decisiones.md#d-16)). Mandar las mismas
paradas del circuito no es un ajuste.

```json
{
  "id": "…", "title": "Mi León", "status": "planned",
  "adjusted": false,
  "followed_circuit": { "id": "…", "title": "…", "version": 1, "published": true },
  "origin_circuit_ids": ["…"],
  "stops": [{ "order": 0, "point_id": "…", "name": "…", "latitude": 12.43,
              "longitude": -86.87, "visited_at": null }],
  "start_time": "09:00", "travel_mode": "walking", "pace": "balanced",
  "fixed_arrivals": {}, "created_at": "…"
}
```

Un itinerario completado no se edita (`409`) y uno en curso no se descarta (`409`). Iniciar
y completar un recorrido llega con F7.

## Contenido de ejemplo

`python src/manage.py seedcontent` carga los lugares y circuitos que la app traía en sus
JSON de ejemplo (`src/api_territory/fixtures/`), activa sus ciudades y crea las alcaldías
verificadas que organizan los creativos. Es para desarrollo y demo: con `DEPLOY=True` pide
`--force`. Los de Rivas (Ometepe) se saltan: Rivas no es una de las diez Ciudades Creativas.

## Dónde se aparta del modelo

- El pilar es uno por lugar (el que la app usa para el ícono y la insignia), no la tabla
  `punto_pilar` de varios.
- La versión sube en el servicio al guardar paradas distintas, no con un disparador; el
  mínimo de dos paradas también lo cuida el servicio.
- El circuito oficial guarda la ciudad y una alcaldía opcional: los del equipo no tienen
  alcaldía.
- El itinerario cuelga de la cuenta, no de `perfil_turista` (llega con las insignias).
- No hay tablas `transicion_*`: los cambios de estado quedan en el historial (`pghistory`).

## Lo que queda para después

- Los horarios de grupo de un circuito (`circuit/{id}/group-session/`), que publican los
  guías: F7.
- Las reseñas y comentarios de circuitos y lugares (`rating` y `reviews_count` son hoy un
  resumen fijo): F7.
- Las métricas del circuito para la alcaldía (iniciaron, modificaron, completaron;
  [RF-A-10](requerimientos/funcionales/portal-alcaldias.md#rf-a-10)): cuando exista el
  inicio de un recorrido.
- Que una organización pida otro lugar (`place-request/`) y la lista de organizaciones del
  portal.
