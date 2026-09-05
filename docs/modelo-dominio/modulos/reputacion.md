---
icon: lucide/star
---

# Reputación

La evaluación mutua que cierra cada servicio y el promedio que sostiene la
decisión de contratación. Una sola tabla de reseña con emisor y receptor
explícitos, por [`D-22`][d-22].

La visibilidad no es una columna configurable: se deriva del papel de quien
recibe la reseña. La reseña sobre un prestador es pública porque sostiene la
contratación; la reseña sobre un turista circula solo entre prestadores porque
sirve de advertencia y no de castigo público.

## Requerimientos cubiertos

- [`RF-S-22`][rf-s-22]
- [`RF-S-23`][rf-s-23]
- [`RF-S-24`][rf-s-24]
- [`RF-S-25`][rf-s-25]
- [`RF-P-15`][rf-p-15]

---

## `resena`

La evaluación de una parte sobre la otra, atada a la reserva que la origina.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** hasta dos por reserva
- **Origen:**
  > - [`RF-S-22`][rf-s-22]
  > - [`RF-S-24`][rf-s-24]

### Columnas

|     Campo      |     Tipo      | Nulo | Predeterminado |             Descripción              |
| :------------: | :-----------: | :--: | :------------: | :----------------------------------: |
|  `reserva_id`  |    `uuid`     |  no  |                |       Llave foránea `RESTRICT`       |
|  `emisor_id`   |    `uuid`     |  no  |                | Llave foránea `RESTRICT` a `usuario` |
| `receptor_id`  |    `uuid`     |  no  |                | Llave foránea `RESTRICT` a `usuario` |
|  `puntuacion`  |  `smallint`   |  no  |                |       De una a cinco estrellas       |
|  `comentario`  |    `text`     |  no  |      `''`      |                                      |
|  `creada_en`   | `timestamptz` |  no  |    `now()`     |    Abre la ventana de corrección     |
| `corregida_en` | `timestamptz` |  sí  |                |        Nulo si nunca se editó        |
| `retirada_en`  | `timestamptz` |  sí  |                |         Solo por moderación          |

### Constraints

```postgresql
CONSTRAINT chk_resena_puntuacion_rango
CHECK (puntuacion BETWEEN 1 AND 5)

CONSTRAINT chk_resena_partes_distintas
CHECK (emisor_id <> receptor_id)

CONSTRAINT chk_resena_comentario_longitud
CHECK (length(comentario) <= 2000)

CONSTRAINT chk_resena_correccion_coherente
CHECK (
  corregida_en IS NULL
  OR
  corregida_en >= creada_en
)
```

### Unicidad

|         Nombre         |        Definición         |            Propósito             |
| :--------------------: | :-----------------------: | :------------------------------: |
| `unq_resena_direccion` | `(reserva_id, emisor_id)` | Una reseña por sentido y reserva |

### Triggers

|              Nombre               |                    Evento                     | Momento  | Nivel |                        Regla                        |        Origen        |
| :-------------------------------: | :-------------------------------------------: | :------: | :---: | :-------------------------------------------------: | :------------------: |
|  `trg_resena_ventana_correccion`  |      `UPDATE OF puntuacion, comentario`       | `BEFORE` | `ROW` |   Rechaza la edición pasadas 24 h de `creada_en`    | [`RF-S-24`][rf-s-24] |
| `trg_resena_partes_de_la_reserva` |                   `INSERT`                    | `BEFORE` | `ROW` | Emisor y receptor son las dos partes de esa reserva | [`RF-S-22`][rf-s-22] |
|       `trg_resena_promedio`       | `INSERT`, `UPDATE OF puntuacion, retirada_en` | `AFTER`  | `ROW` |         Recalcula el promedio del receptor          |    [`D-23`][d-23]    |
|      `trg_resena_no_borrar`       |                   `DELETE`                    | `BEFORE` | `ROW` |    Retirar es escribir `retirada_en`, no borrar     | [`RF-S-25`][rf-s-25] |

### Índices

|        Nombre         |                        Definición                         |                 Propósito                 |
| :-------------------: | :-------------------------------------------------------: | :---------------------------------------: |
| `idx_resena_receptor` | `(receptor_id, creada_en DESC) WHERE retirada_en IS NULL` | [Historial de reseñas recibidas][rf-p-15] |
| `idx_resena_reserva`  |                      `(reserva_id)`                       |  Saber si falta la evaluación del cierre  |

### Notas de diseño

Una sola tabla con dirección explícita, no una pública y otra privada. Dos tablas
habrían duplicado la ventana de corrección, la impugnación y el recálculo del
promedio, con el riesgo de que las dos copias divergieran. La visibilidad que
pide [`RF-S-23`][rf-s-23] se resuelve al leer: se consulta el papel del receptor
en la reserva, y no hace falta guardarla.

La ventana de corrección es un trigger y no un `CHECK`. Depende de comparar
`now()` con `creada_en`, así que es una regla que cambia de resultado con el paso
del tiempo: como restricción permanente impediría cualquier actualización
posterior de la fila, incluida la que escribe `retirada_en` la moderación.

Retirar no borra. [`RF-S-25`][rf-s-25] permite que la moderación retire una
reseña impugnada, pero el promedio tiene que poder recalcularse y la disputa
tiene que quedar documentada. `retirada_en` la saca de los listados y del
promedio sin destruir la evidencia.

El promedio se mantiene desde la base y no desde la aplicación, por
[`D-23`][d-23]. Es el cálculo más caro y más repetido del sistema —se consulta
en cada listado de prestadores y en cada tablero de postulaciones— y si dependiera
de que el servicio recuerde recalcularlo, cualquier vía de escritura nueva podría
dejarlo obsoleto.

---

## `resena_impugnacion`

El caso de disputa que abre el prestador que recibe una reseña ofensiva o falsa.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una fracción de las reseñas
- **Origen:**
  > - [`RF-S-25`][rf-s-25]

### Columnas

|      Campo      |     Tipo      | Nulo | Predeterminado |             Descripción             |
| :-------------: | :-----------: | :--: | :------------: | :---------------------------------: |
|   `resena_id`   |    `uuid`     |  no  |                |       Llave foránea `CASCADE`       |
| `impugnador_id` |    `uuid`     |  no  |                |       Quien recibió la reseña       |
|   `motivo_id`   |    `uuid`     |  no  |                | Llave foránea `RESTRICT` a `motivo` |
|  `descripcion`  |    `text`     |  no  |      `''`      |                                     |
|   `creada_en`   | `timestamptz` |  no  |    `now()`     |    Ordena la cola de moderación     |
|  `resuelta_en`  | `timestamptz` |  sí  |                | Nulo mientras el caso está abierto  |
| `resuelta_por`  |    `uuid`     |  sí  |                |       Qué moderador la cerró        |
|  `procedente`   |   `boolean`   |  sí  |                |   Nulo mientras no hay resolución   |

### Constraints

```postgresql
CONSTRAINT chk_resenaimpugnacion_resolucion_completa
CHECK (
  num_nonnulls(resuelta_en, resuelta_por, procedente) IN (0, 3)
)
```

### Unicidad

|             Nombre             |  Definición   |             Propósito              |
| :----------------------------: | :-----------: | :--------------------------------: |
| `unq_resenaimpugnacion_resena` | `(resena_id)` | Una reseña se impugna una sola vez |

### Triggers

|              Nombre              |         Evento         | Momento  | Nivel |                     Regla                      |        Origen        |
| :------------------------------: | :--------------------: | :------: | :---: | :--------------------------------------------: | :------------------: |
| `trg_resenaimpugnacion_receptor` |        `INSERT`        | `BEFORE` | `ROW` |      Solo impugna quien recibió la reseña      | [`RF-S-25`][rf-s-25] |
|  `trg_resenaimpugnacion_retira`  | `UPDATE OF procedente` | `AFTER`  | `ROW` | Si procede, escribe `retirada_en` en la reseña | [`RF-S-25`][rf-s-25] |

### Índices

|            Nombre            |               Definición                |            Propósito            |
| :--------------------------: | :-------------------------------------: | :-----------------------------: |
| `idx_resenaimpugnacion_cola` | `(creada_en) WHERE resuelta_en IS NULL` | Cola de disputas por antigüedad |

### Notas de diseño

Las tres columnas de resolución se escriben juntas o ninguna, y el `CHECK` lo
impone con `num_nonnulls`. Una impugnación con veredicto pero sin responsable no
es una resolución: es un registro que nadie puede defender cuando el autor de la
reseña pregunte quién decidió.

`procedente` es un booleano nulable y no dos estados. Nulo significa que el caso
sigue abierto, y esa nulidad es la que alimenta la cola de moderación. Un
catálogo de estados habría añadido una tabla para distinguir tres situaciones que
dos columnas ya separan sin ambigüedad.

La marca no oculta la reseña. [`RF-S-25`][rf-s-25] es explícito: impugnar abre un
caso, no retira nada, y el autor no se entera mientras no haya resolución. Por
eso `resena.retirada_en` solo lo escribe el trigger de resolución y nunca la
inserción de la impugnación.

---

## Fuera de este módulo

|         Cosa          |         Dónde vive         |                      Por qué no aquí                      |
| :-------------------: | :------------------------: | :-------------------------------------------------------: |
| `promedio_valoracion` |   [`Perfiles`][perfiles]   |   Es dato derivado del prestador, mantenido desde aquí    |
|       `reserva`       |  [`Servicios`][servicios]  | La reseña cuelga de ella; el cierre del servicio la exige |
|       `motivo`        |  [`Catálogos`][catalogos]  |     Lista cerrada compartida con reportes y sanciones     |
| `reporte` y `sancion` | [`Moderación`][moderacion] | La impugnación es una disputa, no un reporte de conducta  |

[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[d-22]: ../decisiones.md#d-22
[d-23]: ../decisiones.md#d-23
[moderacion]: moderacion.md
[perfiles]: perfiles.md
[servicios]: servicios.md
[rf-p-15]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-15
[rf-s-22]: ../../requerimientos/funcionales/plataforma.md#rf-s-22
[rf-s-23]: ../../requerimientos/funcionales/plataforma.md#rf-s-23
[rf-s-24]: ../../requerimientos/funcionales/plataforma.md#rf-s-24
[rf-s-25]: ../../requerimientos/funcionales/plataforma.md#rf-s-25
