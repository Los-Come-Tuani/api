---
icon: lucide/drama
---

# Agenda cultural

Los eventos que programan las instituciones culturales. Es la vertical que da
dinamismo al circuito: los comercios y las paradas son oferta permanente,
mientras que la agenda cambia por temporada y es la razón por la que una misma
ciudad resulta distinta según la semana en que se visita.

El módulo es pequeño —una tabla de dominio, su catálogo de estado y su
historial— pero concentra dos reglas que no se parecen a nada más del sistema: la
vigencia la gobierna el calendario y no la institución, y un evento cancelado
sigue visible.

## Requerimientos cubiertos

- [`RF-I-01`][rf-i-01]
- [`RF-I-02`][rf-i-02]
- [`RF-I-03`][rf-i-03]
- [`RF-I-04`][rf-i-04]
- [`RF-I-05`][rf-i-05]
- [`RF-I-06`][rf-i-06]

---

## `evento`

Una función, feria, taller o festival con su recinto, su rango de fechas y su
precio de entrada.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** cientos por temporada
- **Origen:**
  > - [`RF-I-01`][rf-i-01]
  > - [`RF-I-04`][rf-i-04]
  > - [`RF-I-06`][rf-i-06]

### Columnas

|           Campo           |      Tipo       | Nulo | Predeterminado |                 Descripción                 |
| :-----------------------: | :-------------: | :--: | :------------: | :-----------------------------------------: |
| `institucion_cultural_id` |     `uuid`      |  no  |                |              Quién lo programa              |
|        `ciudad_id`        |     `uuid`      |  no  |                | Dónde ocurre, no dónde está la institución  |
|        `estado_id`        |     `uuid`      |  no  |                |       Llave foránea a `estado_evento`       |
|      `clonado_de_id`      |     `uuid`      |  sí  |                |     Rastro del evento del que se copió      |
|         `nombre`          |    `varchar`    |  no  |                |                                             |
|       `descripcion`       |     `text`      |  no  |      `''`      |                                             |
|         `recinto`         |    `varchar`    |  no  |                |          Nombre del local o plaza           |
|         `latitud`         | `numeric(9,6)`  |  no  |                |     Ubicación geolocalizada del recinto     |
|        `longitud`         | `numeric(9,6)`  |  no  |                |                                             |
|      `fecha_inicio`       |     `date`      |  no  |                |                                             |
|        `fecha_fin`        |     `date`      |  no  |                |    Igual a `fecha_inicio` si dura un día    |
|       `hora_inicio`       |     `time`      |  no  |                |    Horario diario, no el del primer día     |
|        `hora_fin`         |     `time`      |  no  |                | Menor que `hora_inicio` significa madrugada |
|     `precio_entrada`      | `numeric(12,2)` |  no  |                |         Cero si la entrada es libre         |
|        `moneda_id`        |     `uuid`      |  no  |                |     Llave foránea `RESTRICT` a `moneda`     |
|        `creado_en`        |  `timestamptz`  |  no  |    `now()`     |                                             |

### Llaves foráneas

|          Columna          |       Referencia       | `ON DELETE` |                   Notas                    |
| :-----------------------: | :--------------------: | :---------: | :----------------------------------------: |
| `institucion_cultural_id` | `institucion_cultural` | `RESTRICT`  | La institución no se borra con agenda viva |
|        `ciudad_id`        |        `ciudad`        | `RESTRICT`  |    Catálogo referenciado por operación     |
|        `estado_id`        |    `estado_evento`     | `RESTRICT`  |        Un estado en uso no se borra        |
|      `clonado_de_id`      |        `evento`        | `SET NULL`  |       El clon sobrevive al original        |
|        `moneda_id`        |        `moneda`        | `RESTRICT`  |                                            |

### Constraints

```postgresql
CONSTRAINT chk_evento_fechas_orden
CHECK (fecha_fin >= fecha_inicio)

CONSTRAINT chk_evento_horas_distintas
CHECK (hora_fin <> hora_inicio)

CONSTRAINT chk_evento_precio_no_negativo
CHECK (precio_entrada >= 0)

CONSTRAINT chk_evento_latitud_rango
CHECK (latitud BETWEEN 10.7 AND 15.1)

CONSTRAINT chk_evento_longitud_rango
CHECK (longitud BETWEEN -87.7 AND -82.6)

CONSTRAINT chk_evento_no_autoclon
CHECK (clonado_de_id IS DISTINCT FROM id)
```

Que las fechas sean futuras **no** aparece aquí. Es la regla que
[`Convenciones`][convenciones-invariantes] señala como el error más frecuente:
vale al crear el evento y deja de valer al día siguiente, así que como
restricción permanente impediría actualizar la fila del evento de ayer. La
comprueba el servicio en el alta y en la edición.

### Triggers

|             Nombre             |        Evento         | Momento  | Nivel |                          Regla                           |        Origen        |
| :----------------------------: | :-------------------: | :------: | :---: | :------------------------------------------------------: | :------------------: |
| `trg_evento_readonly_creadoen` |       `UPDATE`        | `BEFORE` | `ROW` |               `creado_en` no se reescribe                |      Convención      |
| `trg_evento_edicion_permitida` |       `UPDATE`        | `BEFORE` | `ROW` | Rechaza el cambio si el estado no tiene `admite_edicion` | [`RF-I-04`][rf-i-04] |
|     `trg_evento_historial`     | `UPDATE OF estado_id` | `AFTER`  | `ROW` |  Inserta la fila correspondiente en `transicion_evento`  | [`RF-S-10`][rf-s-10] |

### Índices

|         Nombre          |                       Definición                       |             Propósito             |
| :---------------------: | :----------------------------------------------------: | :-------------------------------: |
|   `idx_evento_agenda`   |              `(ciudad_id, fecha_inicio)`               |   Agenda de la ciudad por fecha   |
| `idx_evento_calendario` |     `(institucion_cultural_id, fecha_inicio DESC)`     |   [Calendario mensual][rf-i-03]   |
|  `idx_evento_vigencia`  |              `(fecha_inicio, fecha_fin)`               | El barrido que publica y finaliza |
|  `idx_evento_clonado`   |   `(clonado_de_id) WHERE clonado_de_id IS NOT NULL`    | Trazar la programación recurrente |
|   `gin_evento_nombre`   | `GIN (upper(immutable_unaccent(nombre)) gin_trgm_ops)` |    Búsqueda por nombre parcial    |

### Notas de diseño

Fechas y horario son cuatro columnas y no dos marcas de tiempo. Un festival de
cinco días con función de 18:00 a 22:00 no es un intervalo continuo de ciento
veinte horas: son cinco ventanas. Con `inicia_en` y `finaliza_en` habría que
elegir entre describir mal la duración o partir el festival en cinco filas, y
[`RF-I-01`][rf-i-01] lo trata como un solo evento con fechas y horario separados.

`hora_fin` menor que `hora_inicio` significa que la función termina después de
medianoche, igual que en `comercio_horario`. Lo que se prohíbe es que ambas
coincidan, que no describe ni una función instantánea ni una de veinticuatro
horas.

La ciudad del evento es una llave propia y no se hereda de la institución. Un
teatro de León puede llevar una función a Granada, y si la agenda leyera la
ciudad de quien programa, esa función aparecería en el mapa equivocado.

`clonado_de_id` es trazabilidad y por eso anula en lugar de restringir. Clonar
copia descripción, recinto y precio dejando las fechas vacías, y el clon es un
registro independiente desde que se guarda: cancelar el original no cancela la
función del domingo siguiente, que es exactamente lo que
[`RF-I-06`][rf-i-06] pide de la programación recurrente.

---

## `estado_evento`

Catálogo del ciclo de vida del evento. Los cuatro booleanos propios son las
preguntas que el sistema hace sobre el estado, según [`D-11`][d-11].

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas
- **Origen:**
  > - [`RF-I-02`][rf-i-02]
  > - [`RF-I-05`][rf-i-05]

### Columnas

A las cinco columnas comunes a todo `estado_<entidad>` —`codigo`, `etiqueta`,
`es_inicial`, `es_terminal` y `orden`— este catálogo suma tres.

|      Campo       |   Tipo    | Nulo | Predeterminado |            Descripción            |
| :--------------: | :-------: | :--: | :------------: | :-------------------------------: |
|   `es_visible`   | `boolean` |  no  |    `false`     | Aparece en el mapa y en la agenda |
| `admite_edicion` | `boolean` |  no  |    `false`     |  La institución puede corregirlo  |
| `genera_avisos`  | `boolean` |  no  |    `false`     |    Dispara avisos por cercanía    |

### Filas

|    Código    | `es_visible` | `admite_edicion` | `genera_avisos` | `es_terminal` |
| :----------: | :----------: | :--------------: | :-------------: | :-----------: |
| `programado` |      no      |      **sí**      |       no        |      no       |
| `publicado`  |    **sí**    |      **sí**      |     **sí**      |      no       |
| `finalizado` |      no      |        no        |       no        |    **sí**     |
| `cancelado`  |    **sí**    |        no        |       no        |    **sí**     |

### Notas de diseño

`es_visible` y `genera_avisos` son dos preguntas y no una. `cancelado` las separa:
el evento sigue visible marcado como tal —para que quien ya lo tenía visto
entienda qué pasó en lugar de encontrarse con que desapareció— pero deja de
atraer visitantes a un recinto donde ya no ocurrirá nada, que es lo que exige
[`RF-I-05`][rf-i-05]. Con un solo booleano habría que elegir entre ocultarlo y
seguir avisando, y ninguna de las dos cosas es lo pedido.

`admite_edicion` se separa de `es_terminal` porque no coinciden: `programado` no
es terminal y admite edición, `finalizado` es terminal y no la admite, pero
`publicado` admite edición estando ya visible. Una función que ya empezó todavía
puede corregir su precio o su horario; una que terminó, no, porque sería
reescribir algo que ya ocurrió.

Nadie despublica nada. [`RF-I-02`][rf-i-02] hace que la vigencia la gobierne el
calendario, así que las transiciones a `publicado` y a `finalizado` las dispara
un proceso programado leyendo `fecha_inicio` y `fecha_fin`, no la institución.

---

## `transicion_evento`

Instancia del patrón común de transición: quién cambió el estado del evento,
cuándo y por qué.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** dos a cuatro filas por evento
- **Origen:**
  > - [`RF-I-05`][rf-i-05]
  > - [`RF-S-10`][rf-s-10]

Comparte columnas y reglas con las demás `transicion_<entidad>`, descritas en
[`Auditoría`][auditoria-modulo]: estado de origen, estado de destino,
responsable, motivo, nota e instante. Dos particularidades propias:

- `usuario_id` es nulo en las transiciones a `publicado` y a `finalizado`, porque
  las dispara el proceso programado y no una persona.
- El motivo es opcional al cancelar. [`RF-I-05`][rf-i-05] lo declara opcional, a
  diferencia del rechazo de una verificación, donde es obligatorio.

---

## Fuera de este módulo

|                Cosa                |             Dónde vive             |                          Por qué no aquí                           |
| :--------------------------------: | :--------------------------------: | :----------------------------------------------------------------: |
|       `institucion_cultural`       | [`Organizaciones`][organizaciones] |         Es la organización que programa, no lo programado          |
|         `foto` del evento          |     [`Territorio`][territorio]     |        Una sola tabla de fotos con referencias excluyentes         |
|       `geocerca` del evento        | [`Notificaciones`][notificaciones] |           El radio se separa de la entidad que lo motiva           |
| El veto a programar sin aprobación | [`Organizaciones`][organizaciones] | Es una condición de la institución, aunque el trigger dispare aquí |

[auditoria]: ../convenciones.md#auditoria
[auditoria-modulo]: auditoria.md
[convenciones-invariantes]: ../convenciones.md#invariantes
[d-11]: ../decisiones.md#d-11
[notificaciones]: notificaciones.md
[organizaciones]: organizaciones.md
[territorio]: territorio.md
[rf-i-01]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-01
[rf-i-02]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-02
[rf-i-03]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-03
[rf-i-04]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-04
[rf-i-05]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-05
[rf-i-06]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-06
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
