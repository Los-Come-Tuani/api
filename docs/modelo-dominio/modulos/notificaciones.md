---
icon: lucide/bell
---

# Notificaciones

Los avisos que la aplicación entrega en el dispositivo: los que dispara cruzar la
geocerca de un comercio o un evento, y los que derivan de algo que el turista ya
contrató o siguió.

El módulo existe casi entero por una regla: el límite de tres avisos
promocionales por hora es una **ventana deslizante** y no un cupo que se
reinicia, por [`D-28`][d-28]. De ahí que cada envío deje su fila.

## Requerimientos cubiertos

- [`RF-S-14`][rf-s-14]
- [`RF-S-16`][rf-s-16]
- [`RF-I-05`][rf-i-05]

---

## `geocerca`

El radio que dispara los avisos por cercanía, separado de la entidad que lo
motiva.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** una por comercio y por evento vigente
- **Origen:**
  > - [`RF-S-16`][rf-s-16]

### Columnas

|     Campo      |      Tipo      | Nulo | Predeterminado |           Descripción           |
| :------------: | :------------: | :--: | :------------: | :-----------------------------: |
| `comercio_id`  |     `uuid`     |  sí  |                | Dueño A, excluyente con el otro |
|  `evento_id`   |     `uuid`     |  sí  |                | Dueño B, excluyente con el otro |
|   `latitud`    | `numeric(9,6)` |  no  |                |       Centro del círculo        |
|   `longitud`   | `numeric(9,6)` |  no  |                |                                 |
| `radio_metros` |   `smallint`   |  no  |     `500`      |  Valor de partida configurable  |
|    `activa`    |   `boolean`    |  no  |     `true`     |  Deja de disparar sin borrarse  |

### Constraints

```postgresql
CONSTRAINT chk_geocerca_dueno_excluyente
CHECK (num_nonnulls(comercio_id, evento_id) = 1)

CONSTRAINT chk_geocerca_radio_positivo
CHECK (radio_metros BETWEEN 1 AND 5000)

CONSTRAINT chk_geocerca_latitud_rango
CHECK (latitud BETWEEN 10.7 AND 15.1)

CONSTRAINT chk_geocerca_longitud_rango
CHECK (longitud BETWEEN -87.7 AND -82.6)
```

### Unicidad

|         Nombre          |                  Definición                   |         Propósito         |
| :---------------------: | :-------------------------------------------: | :-----------------------: |
| `unq_geocerca_comercio` | `(comercio_id) WHERE comercio_id IS NOT NULL` | Una geocerca por comercio |
|  `unq_geocerca_evento`  |   `(evento_id) WHERE evento_id IS NOT NULL`   |  Una geocerca por evento  |

### Índices

|        Nombre        |             Definición             |              Propósito               |
| :------------------: | :--------------------------------: | :----------------------------------: |
| `idx_geocerca_punto` | `(latitud, longitud) WHERE activa` | Acotar el rectángulo antes del radio |

### Notas de diseño

La geocerca es una entidad y no dos columnas en el comercio, para que cambiar el
radio por defecto no obligue a tocar ninguna ficha. El valor de partida de
quinientos metros vive en [`Parametro`][catalogos] y esta columna lo copia al
crearse: un ajuste global no reescribe las geocercas que alguien ya afinó a mano.

Las coordenadas se repiten aquí en lugar de leerse del dueño. La geocerca de un
evento no siempre se centra en el recinto —una feria puede querer avisar desde la
entrada del parque— y con una sola llave al dueño esa distinción no cabría.

`activa` es lo que apaga los avisos de un evento cancelado sin borrar la fila.
[`RF-I-05`][rf-i-05] exige dejar de atraer visitantes a un recinto donde ya no
ocurrirá nada, y el estado del evento lo propaga aquí.

---

## `token_notificacion`

Dónde entregar el aviso: el registro del dispositivo en el servicio de envío.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** uno o dos por usuario activo
- **Origen:**
  > - [`RF-S-14`][rf-s-14]

### Columnas

|        Campo        |     Tipo      | Nulo | Predeterminado |              Descripción               |
| :-----------------: | :-----------: | :--: | :------------: | :------------------------------------: |
|  `dispositivo_id`   |    `uuid`     |  no  |                |        Llave foránea `CASCADE`         |
|       `token`       |   `varchar`   |  no  |                |  Identificador del servicio de envío   |
|    `plataforma`     |   `varchar`   |  no  |                |           `android` o `ios`            |
| `permiso_ubicacion` |   `boolean`   |  no  |    `false`     | Si concedió ubicación en segundo plano |
|   `registrado_en`   | `timestamptz` |  no  |    `now()`     |                                        |
|    `revocado_en`    | `timestamptz` |  sí  |                |          Nulo mientras sirve           |

### Constraints

```postgresql
CONSTRAINT chk_tokennotificacion_plataforma
CHECK (plataforma IN ('android', 'ios'))
```

### Unicidad

|            Nombre             | Definición |             Propósito             |
| :---------------------------: | :--------: | :-------------------------------: |
| `unq_tokennotificacion_token` | `(token)`  | Un token no se registra dos veces |

### Notas de diseño

`permiso_ubicacion` se guarda porque [`RF-S-14`][rf-s-14] exige informar la
degradación en lugar de fallar en silencio. Sin la columna, la aplicación no
tendría forma de saber que este dispositivo dejó de acreditar visitas por falta
de permiso y no por ausencia del turista.

El token cuelga del dispositivo y no del usuario. Dos personas pueden usar el
mismo aparato y una misma persona dos aparatos; atarlo al usuario obligaría a
borrar y recrear el registro en cada cambio de sesión.

---

## `preferencia_aviso`

Qué categorías acepta cada usuario.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una por usuario y categoría desactivable
- **Origen:**
  > - [`RF-S-16`][rf-s-16]

### Columnas

|      Campo      |   Tipo    | Nulo | Predeterminado |       Descripción        |
| :-------------: | :-------: | :--: | :------------: | :----------------------: |
|  `usuario_id`   |  `uuid`   |  no  |                | Llave foránea `CASCADE`  |
| `tipo_aviso_id` |  `uuid`   |  no  |                | Llave foránea `RESTRICT` |
|  `habilitado`   | `boolean` |  no  |     `true`     |                          |

### Unicidad

|              Nombre              |          Definición           |           Propósito           |
| :------------------------------: | :---------------------------: | :---------------------------: |
| `unq_preferenciaaviso_categoria` | `(usuario_id, tipo_aviso_id)` | Una preferencia por categoría |

### Triggers

|               Nombre                |              Evento              | Momento  | Nivel |                    Regla                     |        Origen        |
| :---------------------------------: | :------------------------------: | :------: | :---: | :------------------------------------------: | :------------------: |
| `trg_preferenciaaviso_desactivable` | `INSERT`, `UPDATE OF habilitado` | `BEFORE` | `ROW` | Rechaza apagar una categoría no desactivable | [`RF-S-16`][rf-s-16] |

### Notas de diseño

La preferencia se ajusta por categoría y no de forma global. Un interruptor único
obligaría a elegir entre recibir promociones o perderse la cancelación de un
evento al que uno se vinculó.

Qué categorías no se pueden apagar vive en `tipo_aviso.desactivable`, en
[`Catálogos`][catalogos], y no repartido por el código. Agregar una categoría
transaccional nueva es insertar una fila, no buscar todos los sitios donde se
comprueba.

---

## `aviso_emitido`

Cada aviso que salió, con su instante. Es la tabla que sostiene el límite.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** millones al año
- **Origen:**
  > - [`RF-S-16`][rf-s-16]
  > - [`RF-I-05`][rf-i-05]

### Columnas

|      Campo      |     Tipo      | Nulo | Predeterminado |            Descripción             |
| :-------------: | :-----------: | :--: | :------------: | :--------------------------------: |
|  `usuario_id`   |    `uuid`     |  no  |                |      Llave foránea `RESTRICT`      |
| `tipo_aviso_id` |    `uuid`     |  no  |                |      Llave foránea `RESTRICT`      |
|  `geocerca_id`  |    `uuid`     |  sí  |                | Nulo si no lo disparó una geocerca |
|   `estado_id`   |    `uuid`     |  no  |                |   Llave foránea a `estado_aviso`   |
|    `titulo`     |   `varchar`   |  no  |                |          Lo que se mostró          |
|    `cuerpo`     |    `text`     |  no  |      `''`      |                                    |
|  `emitido_en`   | `timestamptz` |  no  |    `now()`     |    Sobre esta columna se cuenta    |

### Índices

|           Nombre            |           Definición            |               Propósito                |
| :-------------------------: | :-----------------------------: | :------------------------------------: |
| `idx_avisoemitido_ventana`  | `(usuario_id, emitido_en DESC)` |   Contar los últimos sesenta minutos   |
| `brin_avisoemitido_emitido` |       `BRIN (emitido_en)`       | La purga por antigüedad recorre rangos |

### Notas de diseño

El límite se evalúa contando filas y no leyendo un contador, por
[`D-28`][d-28]. Un contador por hora dejaría pasar seis avisos entre las 10:59 y
las 11:01, porque se reinicia en un instante fijo mientras que la regla habla de
cualquier ventana de sesenta minutos.

Solo dos estados cuentan para el límite y por eso la pregunta vive en el
catálogo. Un aviso descartado por preferencia o fallido en la entrega no consumió
la cuota del usuario: no llegó. Preguntarle a `estado_aviso.cuenta_para_limite`
evita enumerar códigos en la consulta que decide si se puede enviar el siguiente.

La tabla guarda el título y el cuerpo que se mostraron, no una referencia a la
plantilla. Si el aviso dijera «consulta la campaña» y la campaña cambiara, el
historial dejaría de explicar qué vio el usuario.

---

## `estado_aviso`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 5 filas

A las cinco columnas comunes suma dos: `cuenta_para_limite` y
`admite_reintento`.

|    Código    | `cuenta_para_limite` | `admite_reintento` | `es_terminal` |
| :----------: | :------------------: | :----------------: | :-----------: |
|  `encolado`  |          no          |         no         |      no       |
| `descartado` |          no          |         no         |    **sí**     |
|  `enviado`   |        **sí**        |         no         |      no       |
| `entregado`  |        **sí**        |         no         |    **sí**     |
|  `fallido`   |          no          |       **sí**       |    **sí**     |

`fallido` es terminal y aun así admite reintento: reintentar no lo revive, crea
un aviso nuevo. Es la misma lógica que el rechazo de una verificación, donde
subsanar genera otro expediente en lugar de reabrir el cerrado.

---

## Fuera de este módulo

|         Cosa          |                       Dónde vive                        |                         Por qué no aquí                         |
| :-------------------: | :-----------------------------------------------------: | :-------------------------------------------------------------: |
|     `tipo_aviso`      |                [`Catálogos`][catalogos]                 |                Lista cerrada con `desactivable`                 |
|     `dispositivo`     |                [`Identidad`][identidad]                 |        El token cuelga de él; el aparato es de identidad        |
| `comercio` y `evento` | [`Organizaciones`][organizaciones] y [`Agenda`][agenda] |              Motivan la geocerca, no la contienen               |
|  `visita_acreditada`  |                [`Insignias`][insignias]                 | La proximidad que acredita son cincuenta metros, no la geocerca |

[agenda]: agenda.md
[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[d-28]: ../decisiones.md#d-28
[identidad]: identidad.md
[insignias]: insignias.md
[organizaciones]: organizaciones.md
[rf-i-05]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-05
[rf-s-14]: ../../requerimientos/funcionales/plataforma.md#rf-s-14
[rf-s-16]: ../../requerimientos/funcionales/plataforma.md#rf-s-16
