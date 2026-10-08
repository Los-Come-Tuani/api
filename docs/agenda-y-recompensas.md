---
icon: lucide/award
---

# Agenda, insignias y cupones

La oferta que cambia: los eventos que programan las instituciones y las alcaldías, las
insignias que el turista gana al visitar un lugar y los cupones que canjea con ellas en los
comercios. Es la fase F6 de la [hoja de ruta](hoja-de-ruta.md) y sigue el modelo de dominio
de [agenda](modelo-dominio/modulos/agenda.md) e [insignias](modelo-dominio/modulos/insignias.md).

## Lo que se decidió

- Publican eventos las instituciones culturales **y las alcaldías** verificadas; el equipo
  con `content.moderate` programa además los especiales de K'Plan.
- **Moderación después**: el evento se ve según sus fechas y la campaña de cupones al
  crearse; el equipo con `content.moderate` oculta un evento o retira una campaña.
- La insignia de un lugar se gana **escaneando su QR y estando a menos de 50 m** (las dos
  cosas), una vez por lugar cada 24 horas
  ([RF-S-15](requerimientos/funcionales/plataforma.md#rf-s-15)).
- Activar la insignia de un lugar es pagado: la activa el equipo con `places.manage`
  (`has_badge` del lugar) y, desde F8, el comercio la paga cada mes en su estado de cuenta
  junto con los cupones que validó ([finanzas](finanzas.md)).
- Un comercio tiene **hasta tres campañas de cupones activas** a la vez.

## Agenda

| Estado      | En la app              | Se edita |
| ----------- | ---------------------- | -------- |
| `scheduled` | sí, como próximo       | sí       |
| `ongoing`   | sí                     | sí       |
| `finished`  | no                     | no       |
| `cancelled` | sí, señalado           | no       |

La vigencia la gobierna el calendario ([RF-I-02](requerimientos/funcionales/portal-instituciones.md#rf-i-02)):
nadie publica ni despublica. Un evento que empieza hoy o antes está `ongoing`; uno cuya
fecha de fin quedó atrás, `finished`. Se pone al día antes de cada lectura y con el comando
diario `python src/manage.py syncevents` (que también vence campañas y cupones).

### Rutas de la app (públicas)

| Ruta              | Qué devuelve                                                              |
| ----------------- | ------------------------------------------------------------------------- |
| `GET event/`      | Lo próximo y lo que está en curso (y lo cancelado que no terminó), sin lo oculto. Paginado. Filtros: `city` (código), `category`, `from_date`, `to_date` (alguno de sus días cae en el rango), `featured` |
| `GET event/{id}/` | Un evento visible                                                          |
| `GET catalog/event-category/` | Las clases: `tradicion`, `feria`, `cultura`, `taller`, `charla`, `musica`, `gastronomia` |

```json
{
  "id": "…", "name": "Noche de marimba", "description": "…",
  "category": { "code": "musica", "label": "Música" },
  "city": { "id": "…", "code": "leon", "name": "León" },
  "venue": "Teatro Municipal", "address": "…", "latitude": 12.43, "longitude": -86.87,
  "start_date": "2026-10-10", "end_date": "2026-10-11",
  "start_time": "18:00", "end_time": "22:00",
  "entry_price": 100, "featured": false,
  "status": "scheduled", "cancellation_reason": "",
  "organizer": { "kind": "institution", "id": "…", "name": "Teatro de León" },
  "point_id": null, "images": [{ "key": "…", "url": "…" }],
  "cloned_from_id": null, "created_at": "…"
}
```

`organizer.kind` es `institution`, `municipality` o `kplan` (sin `id`). El horario es el de
cada día; una hora de fin menor que la de inicio termina de madrugada. `entry_price` en
córdobas; cero es libre.

### Rutas del portal

| Ruta                              | Quién                                                       | Qué hace                         |
| --------------------------------- | ----------------------------------------------------------- | -------------------------------- |
| `GET cultural-event/`             | `content.moderate`: todos. Institución o alcaldía: los suyos | Paginado, del más reciente. Filtros: `city_id`, `category`, `status`, `from_date`, `to_date`, `search`. Trae `hidden` y `hidden_reason` |
| `POST cultural-event/`            | Institución o alcaldía verificada; `content.moderate` (especial de K'Plan) | Lo programa (`201`)     |
| `GET cultural-event/{id}/`        | Quien lo ve                                                  | Uno                              |
| `PATCH cultural-event/{id}/`      | Quien lo ve                                                  | Corrige lo que llega (`409` si terminó o se canceló) |
| `POST cultural-event/{id}/cancel/`| Quien lo ve                                                  | `{ reason? }`: lo cancela; sigue visible, señalado |
| `POST cultural-event/{id}/clone/` | Quien lo ve                                                  | `{ start_date, end_date }`: copia todo lo demás (`201`) |
| `POST cultural-event/{id}/hide/`  | `content.moderate`                                           | `{ reason }`: lo saca de la app  |
| `POST cultural-event/{id}/show/`  | `content.moderate`                                           | Lo devuelve                      |

Un evento de otra organización responde `404`. Cuerpo de `POST`: `{ city_id, category,
name, description?, venue, address?, latitude, longitude, start_date, end_date, start_time,
end_time, entry_price?, point_id?, images?, featured? }`. La ciudad es la de donde ocurre
(un teatro de León puede llevar una función a Granada). Las fechas empiezan hoy o después y
la de fin no es anterior a la de inicio; las horas son distintas. `featured` (destacado en
el inicio de la app) solo lo cambia el equipo. `point_id` es un lugar activo de esa ciudad.
`images` son claves de `POST /upload/` con `kind: "event-photo"`.

## Insignias

Cada lugar con `has_badge` tiene su insignia y su QR. El QR lleva `kplan://visit/<código>`.

| Ruta                   | Quién                                  | Qué hace                                      |
| ---------------------- | -------------------------------------- | --------------------------------------------- |
| `GET place/{id}/qr/`   | Quien ve el lugar en el portal          | `{ point_id, payload, token, value, active }`; `404` si el lugar no da insignia |
| `POST visit/`          | Un turista (sesión de la app)           | `{ qr, latitude, longitude }`: acredita la visita (`201`) |
| `GET badge/mine/`      | Un turista                              | Su saldo                                      |

`POST visit/` acepta el texto que leyó la cámara (`kplan://visit/…`) o solo el código.
Responde `{ id, point: { id, name, pillar }, amount, balance, distance_meters,
accredited_at }`. Errores: `404` si el QR no es de un lugar con insignia (o se apagó), `400`
con `body.latitude` si está a más de 50 m, `409` si ya ganó la de ese lugar en las últimas
24 horas, `403` si la cuenta no es de turista.

`GET badge/mine/`:

```json
{
  "balance": 4, "earned": 7, "spent": 3,
  "by_pillar": [{ "code": "historia", "label": "Historia", "count": 3 }],
  "visited_point_ids": ["…"],
  "recent": [{ "amount": -3, "kind": "coupon", "label": "10% en tu almuerzo", "recorded_at": "…" }]
}
```

El saldo es la suma de un libro de movimientos
([D-24](modelo-dominio/decisiones.md#d-24)): una visita abona, un cupón carga, y la base no
deja que quede negativo.

## Cupones

| Estado de la campaña | En la tienda |
| -------------------- | ------------ |
| `active`             | sí           |
| `sold_out`           | no           |
| `withdrawn`          | no           |
| `expired`            | no           |

### La app

| Ruta              | Quién                | Qué hace                                         |
| ----------------- | -------------------- | ------------------------------------------------ |
| `GET reward/`     | Pública              | La tienda: campañas activas con cupos. Paginado. Filtro `city` (del comercio) |
| `GET reward/{id}/`| Pública              | Una                                              |
| `POST coupon/`    | Un turista           | `{ campaign_id }`: canjea insignias por un cupón (`201`) |
| `GET coupon/mine/`| Un turista           | Su billetera, del más reciente                    |

Una recompensa: `{ id, title, description, terms, benefit: { type, amount, currency, label },
cost_badges, remaining, expires_at, image, business: { id, name, city, place_id } }`.
`benefit.label` viene listo: "10% de descuento", "C$ 50 de descuento", "Producto gratis",
"Regalo".

Canjear cobra y entrega a la vez: si no alcanzan las insignias responde `409`; si la
campaña ya no está disponible, `404`. El cupón trae un `code` de ocho caracteres (sin `I`,
`O`, `0` ni `1`) y `status` `valid`, `consumed` o `expired`. Copia el beneficio de la
campaña ([D-25](modelo-dominio/decisiones.md#d-25)): si el comercio la retira, el cupón vale
igual hasta su fecha límite.

### El portal

| Ruta                                   | Quién                                         | Qué hace                         |
| -------------------------------------- | --------------------------------------------- | -------------------------------- |
| `GET coupon-campaign/`                 | El comercio: las suyas. `content.moderate`: todas | Paginado. Filtros: `status`, `business_id`. Trae `stock_total`, `stock_delivered`, `consumed` |
| `POST coupon-campaign/`                | Un comercio verificado                        | Publica una campaña (`201`; `409` si ya tiene tres activas) |
| `GET coupon-campaign/{id}/`            | Quien la ve                                   | Una                              |
| `PATCH coupon-campaign/{id}/`          | El comercio                                   | `title`, `description`, `terms`, `stock_total` (no menos de lo entregado), `expires_at` (futura), `image_key`. El beneficio y el costo no cambian |
| `POST coupon-campaign/{id}/withdraw/`  | El comercio o `content.moderate`              | `{ reason? }`: corta la emisión  |
| `GET coupon-redemption/`               | El comercio: lo suyo. `content.moderate`: todo | Los cupones entregados, con el nombre del turista. Filtros: `status`, `campaign_id` |
| `POST coupon-redemption/validate/`     | El comercio                                   | `{ code }`: lo consume en el mostrador |

Cuerpo de `POST coupon-campaign/`: `{ benefit_type, title, description?, terms?,
benefit_amount?, cost_badges, stock_total, expires_at, image_key? }`. `benefit_type` sale de
`GET catalog/benefit-type/` (`descuento_porcentaje`, `descuento_monto`, `producto_gratis`,
`regalo`); los dos primeros exigen `benefit_amount` (un porcentaje no pasa de 100; el monto
es en córdobas). `image_key` es una clave de `POST /upload/` con `kind: "coupon-photo"`.

`validate/` acepta el código como lo dicte el turista (minúsculas, espacios o guiones). Un
código de otro comercio responde `404`; uno ya usado o vencido, `409`.

## Al desplegar

- Migraciones nuevas (`apicatalogs.0004_agenda_cupones`, `apiagenda.0001`,
  `apiorganizations.0004_foto_evento`, `apirewards.0001`) que siembran las clases de evento,
  los tipos de beneficio y los estados.
- Programar `python src/manage.py syncevents` una vez al día (las lecturas también ponen al
  día, pero el comando deja la base coherente para reportes).
- Los lugares que ya tenían `has_badge` reciben su insignia y su QR la primera vez que
  alguien pide `place/{id}/qr/` o el equipo vuelve a guardar el lugar.

## Lo que queda para después

- Las campañas de insignias extra con multiplicador y los paquetes.
- Los avisos a quien había visto un evento cancelado y los avisos por cercanía (la bandeja
  y el envío ya existen: [avisos](avisos.md)).
- Las medallas por ciudad y el nivel de exploración del turista (`perfil_turista`).
- La agenda de llegadas de los grupos (`visit-events`): con los recorridos de F7.

## Dónde se aparta del modelo

- La insignia cuelga del lugar (el comercio la tiene por su lugar), no de dos llaves.
- Visitas, movimientos y cupones cuelgan de la cuenta, no de `perfil_turista`.
- El evento admite también a la alcaldía como organizadora, y ninguno para los especiales
  de K'Plan; suma `featured`, el lugar opcional y la moderación (`hidden_at`).
- `programado` se ve en la agenda como próximo (el modelo lo deja oculto hasta empezar).
- El precio de entrada y el monto en córdobas son enteros o decimales sin tabla de moneda
  para la entrada.
- No hay `transicion_evento`: los cambios quedan en el historial (`pghistory`).
