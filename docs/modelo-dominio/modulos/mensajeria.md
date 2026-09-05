---
icon: lucide/messages-square
---

# Mensajería

La sala donde el turista y el prestador acuerdan tarifa, punto de encuentro y
detalles del servicio. Nunca existe por sí sola: nace de una convocatoria o de
una reserva, y esa dependencia es lo que ata cada acuerdo al trabajo que lo
motivó.

Es el módulo que más filas escribe por usuario activo y el único cuyo contenido
la plataforma no interpreta salvo para una regla: impedir que la negociación se
desplace fuera del sistema antes de que haya reserva confirmada.

## Requerimientos cubiertos

- [`RF-S-17`][rf-s-17]
- [`RF-S-18`][rf-s-18]
- [`RF-S-19`][rf-s-19]
- [`RF-S-20`][rf-s-20]
- [`RF-S-21`][rf-s-21]

---

## `conversacion`

La sala. Cuelga del objeto que la origina, con dos llaves mutuamente
excluyentes.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una por convocatoria adjudicada y por reserva
- **Origen:**
  > - [`RF-S-17`][rf-s-17]

### Columnas

|        Campo        |     Tipo      | Nulo | Predeterminado |           Descripción            |
| :-----------------: | :-----------: | :--: | :------------: | :------------------------------: |
|  `convocatoria_id`  |    `uuid`     |  sí  |                | Origen A, excluyente con el otro |
|    `reserva_id`     |    `uuid`     |  sí  |                | Origen B, excluyente con el otro |
|     `creada_en`     | `timestamptz` |  no  |    `now()`     |                                  |
| `ultimo_mensaje_en` | `timestamptz` |  sí  |                |   Nulo mientras nadie escribe    |

### Llaves foráneas

|      Columna      |   Referencia   | `ON DELETE` |              Notas               |
| :---------------: | :------------: | :---------: | :------------------------------: |
| `convocatoria_id` | `convocatoria` | `RESTRICT`  | El historial sobrevive al cierre |
|   `reserva_id`    |   `reserva`    | `RESTRICT`  | El historial sobrevive al cierre |

### Constraints

```postgresql
CONSTRAINT chk_conversacion_origen_excluyente
CHECK (num_nonnulls(convocatoria_id, reserva_id) = 1)
```

### Unicidad

|             Nombre              |                      Definición                       |         Propósito         |
| :-----------------------------: | :---------------------------------------------------: | :-----------------------: |
| `unq_conversacion_convocatoria` | `(convocatoria_id) WHERE convocatoria_id IS NOT NULL` | Una sala por convocatoria |
|   `unq_conversacion_reserva`    |      `(reserva_id) WHERE reserva_id IS NOT NULL`      |   Una sala por reserva    |

### Triggers

|              Nombre              |        Evento         | Momento  | Nivel |                  Regla                   |        Origen        |
| :------------------------------: | :-------------------: | :------: | :---: | :--------------------------------------: | :------------------: |
| `trg_conversacion_ultimomensaje` | `INSERT` en `mensaje` | `AFTER`  | `ROW` |      Actualiza `ultimo_mensaje_en`       | [`RF-S-19`][rf-s-19] |
|   `trg_conversacion_no_borrar`   |       `DELETE`        | `BEFORE` | `ROW` | Bloquea el borrado; archivar no destruye | [`RF-S-21`][rf-s-21] |

### Notas de diseño

`ultimo_mensaje_en` está denormalizado porque [`RF-S-19`][rf-s-19] ordena la
bandeja por la fecha del último mensaje, y esa consulta es la primera pantalla
que ve cualquiera de las dos partes. Agregar el máximo sobre `mensaje` en cada
carga de bandeja obligaría a recorrer la tabla más grande del módulo para
ordenar unas pocas filas. Lo mantiene un trigger y no la aplicación, para que
ninguna vía de escritura pueda dejarlo obsoleto.

Es nulo y no `creada_en` mientras nadie ha escrito. Una sala recién abierta no
tuvo su último mensaje en el instante de crearse: no tuvo ninguno, y esa
distinción es la que permite ordenar las salas vacías al final sin inventar una
fecha.

---

## `conversacion_participante`

Quién interviene en la sala y en qué papel. Es donde vive el archivado.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** dos por conversación
- **Origen:**
  > - [`RF-S-19`][rf-s-19]
  > - [`RF-S-21`][rf-s-21]

### Columnas

|        Campo        |     Tipo      | Nulo | Predeterminado |           Descripción            |
| :-----------------: | :-----------: | :--: | :------------: | :------------------------------: |
|  `conversacion_id`  |    `uuid`     |  no  |                |     Llave foránea `CASCADE`      |
|    `usuario_id`     |    `uuid`     |  no  |                |     Llave foránea `RESTRICT`     |
|       `papel`       |   `varchar`   |  no  |                |     `turista` o `prestador`      |
|   `archivada_en`    | `timestamptz` |  sí  |                | Nulo mientras está en la bandeja |
| `ultima_lectura_en` | `timestamptz` |  sí  |                |      Nulo si nunca la abrió      |

### Constraints

```postgresql
CONSTRAINT chk_conversacionparticipante_papel
CHECK (papel IN ('turista', 'prestador'))
```

### Unicidad

|                 Nombre                 |           Definición            |         Propósito         |
| :------------------------------------: | :-----------------------------: | :-----------------------: |
| `unq_conversacionparticipante_usuario` | `(conversacion_id, usuario_id)` | Nadie participa dos veces |
|  `unq_conversacionparticipante_papel`  |   `(conversacion_id, papel)`    |     Un papel por sala     |

### Índices

|                 Nombre                 |          Definición          |               Propósito               |
| :------------------------------------: | :--------------------------: | :-----------------------------------: |
| `idx_conversacionparticipante_bandeja` | `(usuario_id, archivada_en)` | [Bandeja activa e histórica][rf-s-19] |

### Notas de diseño

El archivado vive aquí y no en la conversación. [`RF-S-21`][rf-s-21] exige que
sea independiente por participante, y una columna en la sala afectaría a ambas
partes: que el turista archivara sacaría el hilo también de la bandeja del
prestador. Es la misma razón por la que `ultima_lectura_en` es de cada quien.

Archivar escribe una fecha y no borra nada. El requerimiento es explícito en que
el archivado «en ningún caso destruye el historial», así que la fila permanece y
la bandeja principal filtra por `archivada_en IS NULL`.

---

## `mensaje`

Cada intervención en la sala.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** millones al año
- **Origen:**
  > - [`RF-S-17`][rf-s-17]
  > - [`RF-S-18`][rf-s-18]
  > - [`RF-S-20`][rf-s-20]

### Columnas

|       Campo       |     Tipo      | Nulo | Predeterminado |             Descripción             |
| :---------------: | :-----------: | :--: | :------------: | :---------------------------------: |
| `conversacion_id` |    `uuid`     |  no  |                |       Llave foránea `CASCADE`       |
| `participante_id` |    `uuid`     |  no  |                |     Quién lo envió, en su papel     |
|     `cuerpo`      |    `text`     |  no  |      `''`      | Vacío si el mensaje es solo adjunto |
|   `enviado_en`    | `timestamptz` |  no  |    `now()`     |                                     |

### Constraints

```postgresql
CONSTRAINT chk_mensaje_cuerpo_longitud
CHECK (length(cuerpo) <= 2000)
```

### Triggers

|             Nombre             |  Evento  | Momento  | Nivel |                            Regla                             |        Origen        |
| :----------------------------: | :------: | :------: | :---: | :----------------------------------------------------------: | :------------------: |
| `trg_mensaje_contacto_directo` | `INSERT` | `BEFORE` | `ROW` | Rechaza teléfonos y correos si la reserva no está confirmada | [`RF-S-18`][rf-s-18] |

### Índices

|         Nombre          |                       Definición                       |                 Propósito                  |
| :---------------------: | :----------------------------------------------------: | :----------------------------------------: |
| `idx_mensaje_historial` |          `(conversacion_id, enviado_en DESC)`          |    Cargar la sala en orden cronológico     |
|  `gin_mensaje_cuerpo`   | `GIN (upper(immutable_unaccent(cuerpo)) gin_trgm_ops)` |   [Búsqueda dentro de la sala][rf-s-20]    |
| `brin_mensaje_enviado`  |                  `BRIN (enviado_en)`                   | El archivado por antigüedad recorre rangos |

### Notas de diseño

El mensaje referencia al participante y no al usuario. Así el historial conserva
en qué papel intervino cada quien aunque después cambien sus perfiles: una
persona que hoy contrata como turista y mañana opera como guía no reescribe lo
que dijo en una sala anterior.

El límite de dos mil caracteres es un `CHECK` y no un `varchar(2000)`, porque
[`Convenciones`][convenciones-tipos] declara el texto sin límite salvo que el
límite sea regla de negocio. Aquí lo es, y como restricción nombrada produce un
error atribuible al campo en lugar de un truncamiento silencioso.

La restricción de contacto directo es un trigger sobre la inserción y no una
validación en el cliente. [`RF-S-18`][rf-s-18] la justifica en que la comisión
que sostiene la plataforma depende de que la negociación no se desplace fuera, y
una regla con ese incentivo en contra no puede vivir donde el interesado puede
saltarla.

!!! warning "Cifrado sin definir"

    [`RF-S-17`][rf-s-17] exige que la sala sea «cifrada» sin precisar si se
    refiere al transporte o al contenido en reposo. El modelo guarda `cuerpo`
    en claro, que es lo único compatible con la búsqueda por texto de
    [`RF-S-20`][rf-s-20] y con el trigger de contacto directo. Si la exigencia
    fuera cifrado en reposo, ambas funciones tendrían que rediseñarse.

---

## `mensaje_adjunto`

Imágenes y documentos que acompañan a un mensaje.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** una fracción de los mensajes
- **Origen:**
  > - [`RF-S-17`][rf-s-17]

### Columnas

|       Campo       |   Tipo    | Nulo | Predeterminado |                  Descripción                  |
| :---------------: | :-------: | :--: | :------------: | :-------------------------------------------: |
|   `mensaje_id`    |  `uuid`   |  no  |                |            Llave foránea `CASCADE`            |
|   `archivo_id`    | `varchar` |  no  |                |      Identificador en el almacenamiento       |
|   `tipo_medio`    | `varchar` |  no  |                | `image/jpeg`, `image/png` o `application/pdf` |
| `nombre_original` | `varchar` |  no  |      `''`      |        Cómo lo llamaba quien lo subió         |
|  `tamano_bytes`   | `integer` |  no  |                |                                               |

### Constraints

```postgresql
CONSTRAINT chk_mensajeadjunto_tipo_permitido
CHECK (tipo_medio IN ('image/jpeg', 'image/png', 'application/pdf'))

CONSTRAINT chk_mensajeadjunto_tamano_positivo
CHECK (tamano_bytes > 0)
```

### Notas de diseño

Los tipos permitidos son un `CHECK` sobre una lista corta y no un catálogo,
porque [`RF-S-17`][rf-s-17] los enumera de forma cerrada —texto, imágenes y PDF—
y no hay ningún atributo que colgar de cada tipo. Es la excepción que
[`D-12`][d-12] admite: sin columnas propias por valor, no hace falta una tabla.

---

## Fuera de este módulo

|            Cosa            |             Dónde vive             |                Por qué no aquí                |
| :------------------------: | :--------------------------------: | :-------------------------------------------: |
| `convocatoria` y `reserva` |      [`Servicios`][servicios]      |    La sala cuelga de ellas, nunca al revés    |
|         `usuario`          |      [`Identidad`][identidad]      |  El participante lo referencia, no lo define  |
| El aviso de mensaje nuevo  | [`Notificaciones`][notificaciones] | Es una categoría de aviso como cualquier otra |

[auditoria]: ../convenciones.md#auditoria
[convenciones-tipos]: ../convenciones.md#tipos
[d-12]: ../decisiones.md#d-12
[identidad]: identidad.md
[notificaciones]: notificaciones.md
[servicios]: servicios.md
[rf-s-17]: ../../requerimientos/funcionales/plataforma.md#rf-s-17
[rf-s-18]: ../../requerimientos/funcionales/plataforma.md#rf-s-18
[rf-s-19]: ../../requerimientos/funcionales/plataforma.md#rf-s-19
[rf-s-20]: ../../requerimientos/funcionales/plataforma.md#rf-s-20
[rf-s-21]: ../../requerimientos/funcionales/plataforma.md#rf-s-21
