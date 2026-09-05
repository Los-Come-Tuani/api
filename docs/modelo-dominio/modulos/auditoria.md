---
icon: lucide/scroll-text
---

# Auditoría

Qué cambió, quién lo provocó y por qué. Tres mecanismos distintos que no compiten
entre sí: la tabla de eventos que acompaña a cada tabla rastreada, la transición
que registra cada cambio de estado y la bitácora de las acciones internas que no
modifican ninguna fila.

Este módulo define dos **patrones** que el resto instancia. `estado_<entidad>` y
`transicion_<entidad>` no son dos tablas: son dos formas que se repiten una vez
por cada entidad con ciclo de vida, y aquí se documentan una sola vez.

## Requerimientos cubiertos

- [`RF-S-10`][rf-s-10]
- [`RF-B-10`][rf-b-10]

---

## `contexto_peticion`

Quién provocó un cambio, desde dónde y sobre qué recurso.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** una por petición que escribe
- **Origen:**
  > - [`RF-S-10`][rf-s-10]

### Columnas

|     Campo     |     Tipo      | Nulo | Predeterminado |              Descripción              |
| :-----------: | :-----------: | :--: | :------------: | :-----------------------------------: |
| `usuario_id`  |    `uuid`     |  sí  |                | Nulo si lo hizo un proceso programado |
|   `metodo`    |   `varchar`   |  no  |                |         Verbo de la petición          |
|     `url`     |   `varchar`   |  no  |                |     Recurso sobre el que se actuó     |
|  `ip_origen`  |    `inet`     |  sí  |                |       Nulo en procesos internos       |
|   `agente`    |   `varchar`   |  no  |      `''`      |           Cliente declarado           |
| `ocurrido_en` | `timestamptz` |  no  |    `now()`     |                                       |

### Índices

|              Nombre              |            Definición            |          Propósito          |
| :------------------------------: | :------------------------------: | :-------------------------: |
|  `idx_contextopeticion_usuario`  | `(usuario_id, ocurrido_en DESC)` |    Qué hizo una persona     |
|    `gin_contextopeticion_url`    |    `GIN` trigrama sobre `url`    | Buscar por recurso afectado |
| `brin_contextopeticion_ocurrido` |       `BRIN (ocurrido_en)`       |   La purga por antigüedad   |

### Notas de diseño

El contexto se separa del evento porque una sola petición cambia varias filas de
varias tablas. Repetir usuario, dirección y recurso en cada evento multiplicaría
el dato por el número de filas tocadas; con la referencia, se escribe una vez y
todos los eventos de esa transacción apuntan ahí.

`usuario_id` admite nulo y esa nulidad **es** la información: significa que el
cambio no lo hizo una persona sino el proceso que publica eventos, expira
convocatorias o cumple sanciones. Sin ella habría que inventar un usuario
ficticio del sistema y confundirlo con uno real.

---

## `<entidad>_evento`

La tabla de eventos que acompaña a cada tabla **rastreada**. Se genera una por
cada una, con el mismo nombre más el sufijo.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** proporcional a las escrituras de su tabla base
- **Origen:**
  > - [`RF-S-10`][rf-s-10]

### Columnas

Cada tabla de eventos replica **todas** las columnas de su tabla base y agrega
cuatro propias.

|      Campo       |     Tipo      | Nulo | Predeterminado |            Descripción             |
| :--------------: | :-----------: | :--: | :------------: | :--------------------------------: |
|     `pgh_id`     |    `uuid`     |  no  |                |      Identificador del evento      |
|   `pgh_label`    |   `varchar`   |  no  |                |   `insert`, `update` o `delete`    |
|  `pgh_context`   |    `jsonb`    |  sí  |                | El `contexto_peticion` serializado |
| `pgh_created_at` | `timestamptz` |  no  |    `now()`     |         Cuándo se registró         |

### Índices

Cada tabla de eventos lleva el mismo juego, declarado una sola vez en el
decorador que las genera.

|            Nombre            |                 Definición                 |           Propósito            |
| :--------------------------: | :----------------------------------------: | :----------------------------: |
|   `gin_%(class)s_ctx_path`   |     `GIN (pgh_context jsonb_path_ops)`     |   Buscar dentro del contexto   |
|   `gin_%(class)s_ctx_url`    | `GIN (pgh_context ->> 'url' gin_trgm_ops)` |       Buscar por recurso       |
|  `idx_%(class)s_ctx_userid`  |    `((pgh_context -> 'user' ->> 'id'))`    |     Qué cambió una persona     |
| `idx_%(class)s_pghcreatedat` |             `(pgh_created_at)`             |       Recorrer por fecha       |
|      `idx_%(class)s_id`      |                   `(id)`                   | Historial de una fila concreta |

### Notas de diseño

Las columnas sensibles se excluyen de la réplica. El secreto del segundo factor y
los hashes de recuperación no se copian al evento: replicarlos multiplicaría por
el número de versiones la superficie de un dato que
[`Convenciones`][convenciones-auditoria] ya obliga a cifrar. La exclusión se
declara por tabla, junto al régimen.

El contexto se guarda serializado y no como llave foránea. Una tabla de eventos
que restringiera el borrado del contexto impediría purgar peticiones antiguas sin
purgar antes todo el historial; con el `jsonb`, el evento sobrevive por sí solo y
conserva lo que hacía falta saber.

---

## `estado_<entidad>`

Patrón del catálogo de estados. Se instancia una vez por entidad con ciclo de
vida, por [`D-11`][d-11].

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** entre 3 y 7 filas cada uno

### Columnas comunes

|     Campo     |    Tipo    | Nulo | Predeterminado |         Descripción          |
| :-----------: | :--------: | :--: | :------------: | :--------------------------: |
|   `codigo`    | `varchar`  |  no  |                | Cómo lo referencia el código |
|  `etiqueta`   | `varchar`  |  no  |                |       Cómo se muestra        |
| `es_inicial`  | `boolean`  |  no  |    `false`     |    Con cuál nace la fila     |
| `es_terminal` | `boolean`  |  no  |    `false`     |    Desde cuál no se sale     |
|    `orden`    | `smallint` |  no  |      `0`       | Cómo se ordena en un listado |

A esas cinco, cada entidad suma las suyas.

|       Catálogo        |                Columnas propias                 |
| :-------------------: | :---------------------------------------------: |
|   `estado_usuario`    |        `permite_operar`, `revoca_sesion`        |
|   `estado_circuito`   |         `es_visible`, `admite_edicion`          |
|    `estado_evento`    | `es_visible`, `admite_edicion`, `genera_avisos` |
| `estado_convocatoria` |              `admite_postulacion`               |
|   `estado_reserva`    |     `admite_cancelacion`, `retiene_fondos`      |
|   `estado_campania`   |                 `admite_canje`                  |
|    `estado_cupon`     |               `admite_validacion`               |
| `estado_verificacion` |                  `en_bandeja`                   |
|    `estado_aviso`     |    `cuenta_para_limite`, `admite_reintento`     |

### Unicidad

|             Nombre             |           Definición            |            Propósito             |
| :----------------------------: | :-----------------------------: | :------------------------------: |
| `unq_estado_<entidad>_codigo`  |           `(codigo)`            | El código identifica y no cambia |
| `unq_estado_<entidad>_inicial` | `(es_inicial) WHERE es_inicial` |      Un solo estado inicial      |

### Notas de diseño

Los booleanos son las preguntas que el sistema hace sobre el estado, no
descripciones. Un valor en columna obligaría a repartir esas preguntas en
condicionales por todo el código, y agregar un estado exigiría migrar un tipo;
con el catálogo, agregar un estado es insertar una fila.

Cada entidad tiene sus propias preguntas y por eso son nueve catálogos y no uno
compartido. Es la aplicación de [`D-12`][d-12]: si agregar un valor obliga a
agregar columnas que solo aplican a ese valor, no es un estado del mismo tipo
sino otro concepto.

---

## `transicion_<entidad>`

Patrón del historial de cambios de estado, por [`D-13`][d-13].

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** proporcional al ciclo de vida de su entidad
- **Origen:**
  > - [`RF-S-10`][rf-s-10]

### Columnas comunes

|        Campo        |     Tipo      | Nulo | Predeterminado |              Descripción              |
| :-----------------: | :-----------: | :--: | :------------: | :-----------------------------------: |
|   `<entidad>_id`    |    `uuid`     |  no  |                |          La fila que cambió           |
| `estado_origen_id`  |    `uuid`     |  sí  |                |            Nulo en el alta            |
| `estado_destino_id` |    `uuid`     |  no  |                |                                       |
|    `usuario_id`     |    `uuid`     |  sí  |                | Nulo si lo hizo un proceso programado |
|     `motivo_id`     |    `uuid`     |  sí  |                |  Obligatorio donde la regla lo exige  |
|       `nota`        |    `text`     |  no  |      `''`      |                                       |
|    `ocurrida_en`    | `timestamptz` |  no  |    `now()`     |                                       |

### Constraints

```postgresql
CONSTRAINT chk_transicion_<entidad>_estados_distintos
CHECK (estado_origen_id IS DISTINCT FROM estado_destino_id)
```

### Índices

|                Nombre                |             Definición             |       Propósito       |
| :----------------------------------: | :--------------------------------: | :-------------------: |
|   `idx_transicion_<entidad>_fila`    | `(<entidad>_id, ocurrida_en DESC)` | Historial de una fila |
| `brin_transicion_<entidad>_ocurrida` |        `BRIN (ocurrida_en)`        | Recorrer por periodo  |

### Notas de diseño

El estado actual vive como llave foránea en la propia entidad y no se deriva de
aquí. Las consultas frecuentes no pueden pagar una agregación sobre el historial
para saber en qué estado está una reserva, y por eso el dato se duplica: la
entidad tiene el estado vigente y esta tabla, cómo llegó a él.

Una transición hacia el mismo estado no es una transición, y el `CHECK` la
descarta. Es el error típico de un proceso que reescribe el estado por descuido y
llena el historial de filas que no dicen nada.

Dónde el motivo es obligatorio no se declara aquí sino en el trigger de cada
entidad, porque la condición cambia: al rechazar una verificación siempre, al
cancelar una reserva solo con menos de veinticuatro horas de antelación, y al
cancelar un evento nunca.

---

## `bitacora`

Las acciones internas que no modifican ninguna fila y aun así hay que poder
reconstruir.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** cientos de miles al año
- **Origen:**
  > - [`RF-B-10`][rf-b-10]

### Columnas

|     Campo     |     Tipo      | Nulo | Predeterminado |              Descripción               |
| :-----------: | :-----------: | :--: | :------------: | :------------------------------------: |
| `usuario_id`  |    `uuid`     |  no  |                |            Quién la ejecutó            |
|   `accion`    |   `varchar`   |  no  |                |                Qué hizo                |
|   `recurso`   |   `varchar`   |  no  |                |               Sobre qué                |
| `recurso_id`  |    `uuid`     |  sí  |                | Nulo si la acción no apunta a una fila |
|  `motivo_id`  |    `uuid`     |  sí  |                |                                        |
|   `detalle`   |    `jsonb`    |  sí  |                |  Lo que hace falta para reconstruirla  |
|  `ip_origen`  |    `inet`     |  sí  |                |                                        |
| `ocurrida_en` | `timestamptz` |  no  |    `now()`     |                                        |

### Triggers

|           Nombre            |       Evento       | Momento  | Nivel |              Regla               |        Origen        |
| :-------------------------: | :----------------: | :------: | :---: | :------------------------------: | :------------------: |
| `trg_bitacora_no_modificar` | `UPDATE`, `DELETE` | `BEFORE` | `ROW` | Bloquea toda escritura posterior | [`RF-B-10`][rf-b-10] |

### Índices

|          Nombre          |                Definición                 |          Propósito           |
| :----------------------: | :---------------------------------------: | :--------------------------: |
|  `idx_bitacora_usuario`  |     `(usuario_id, ocurrida_en DESC)`      | Qué hizo un operador interno |
|  `idx_bitacora_recurso`  | `(recurso, recurso_id, ocurrida_en DESC)` |   Qué le pasó a un recurso   |
| `brin_bitacora_ocurrida` |           `BRIN (ocurrida_en)`            |   La purga por antigüedad    |

### Notas de diseño

La bitácora registra lo que la tabla de eventos no puede ver. Consultar el
expediente de un prestador, exportar un reporte de ingresos o abrir el documento
de una acreditación no cambian ninguna fila, y aun así son exactamente las
acciones que hay que poder reconstruir cuando se disputa una decisión interna.

Es la única tabla del sistema con `UPDATE` y `DELETE` bloqueados por trigger, no
solo por régimen declarado. Un registro de auditoría que el propio auditado puede
editar no es un registro de auditoría.

---

## Los tres regímenes

Cada tabla del modelo declara a cuál pertenece, y esa declaración es lo que
determina si lleva tabla de eventos y qué disparadores se le instalan.

|        Régimen        |                  Qué permite                  |                                                 Tablas                                                  |
| :-------------------: | :-------------------------------------------: | :-----------------------------------------------------------------------------------------------------: |
| **De solo inserción** |      Insertar. No actualizar ni eliminar      | Movimientos, visitas acreditadas, transiciones, intentos de acceso, avisos emitidos, mensajes, bitácora |
| **Mutable rastreada** |   Todo, con historial completo de versiones   |                      Usuario, perfiles, comercios, circuitos, eventos, recorridos                       |
| **Mutable protegida** | Todo salvo columnas congeladas por disparador |                        Reserva y cupón, cuya tarifa y beneficio no se reescriben                        |

Ninguna tabla admite vaciado masivo: un disparador lo impide en la tabla base de
la que heredan todas, y por eso no aparece en la ficha de ninguna.

---

## Fuera de este módulo

|               Cosa               |         Dónde vive         |                 Por qué no aquí                  |
| :------------------------------: | :------------------------: | :----------------------------------------------: |
|             `motivo`             |  [`Catálogos`][catalogos]  |   Lista cerrada con `exige_texto` por contexto   |
|            `sancion`             | [`Moderación`][moderacion] | Es una decisión, no el registro de una decisión  |
| Cada `estado_<entidad>` concreto |  El módulo de su entidad   | Aquí está la forma; allí, las filas y sus reglas |

[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[convenciones-auditoria]: ../convenciones.md#auditoria
[d-11]: ../decisiones.md#d-11
[d-12]: ../decisiones.md#d-12
[d-13]: ../decisiones.md#d-13
[moderacion]: moderacion.md
[rf-b-10]: ../../requerimientos/funcionales/backoffice.md#rf-b-10
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
