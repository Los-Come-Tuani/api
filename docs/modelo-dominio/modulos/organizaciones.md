---
icon: lucide/store
---

# Organizaciones y comercios

Las dos organizaciones privadas que se dan de alta por su cuenta: la MIPYME que
aparece en el mapa y la institución que programa la agenda cultural. La alcaldía
no está aquí —vive en [`Territorio`][territorio] porque es autoridad sobre un
territorio, no una organización que se registra— y comercio e institución no
comparten tabla, por [`D-12`][d-12].

Ninguna de las dos tiene máquina de estados propia. Su visibilidad es
consecuencia de la verificación que corre en paralelo, de modo que lo único que
estas tablas guardan del proceso es el instante en que se aprobó; la cola que lo
resuelve vive en [`Moderación`][moderacion].

## Requerimientos cubiertos

- [`RF-C-01`][rf-c-01]
- [`RF-C-02`][rf-c-02]
- [`RF-C-03`][rf-c-03]
- [`RF-C-04`][rf-c-04]
- [`RF-C-05`][rf-c-05]
- [`RF-C-11`][rf-c-11]
- [`RF-C-12`][rf-c-12]
- [`RF-I-07`][rf-i-07]

---

## `comercio`

Ficha de la MIPYME registrada en el mapa. Es la tabla que más se lee sin que
nadie la escriba: se consulta en cada búsqueda por cercanía y solo se modifica
cuando el propio comercio corrige sus datos.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** cientos en el piloto
- **Origen:**
  > - [`RF-C-01`][rf-c-01]
  > - [`RF-C-03`][rf-c-03]

### Columnas

|       Campo        |      Tipo      | Nulo | Predeterminado |             Descripción              |
| :----------------: | :------------: | :--: | :------------: | :----------------------------------: |
|    `ciudad_id`     |     `uuid`     |  no  |                |       Llave foránea a `ciudad`       |
| `tipo_negocio_id`  |     `uuid`     |  no  |                |    Llave foránea a `tipo_negocio`    |
|       `ruc`        |   `varchar`    |  no  |                |   Registro único del contribuyente   |
|      `nombre`      |   `varchar`    |  no  |                |  Nombre comercial, no razón social   |
|    `direccion`     |   `varchar`    |  no  |                | Dirección escrita, para llegar a pie |
|     `telefono`     |   `varchar`    |  no  |                |    Teléfono principal de atención    |
| `telefono_alterno` |   `varchar`    |  no  |      `''`      |      Vacío si declara uno solo       |
|     `latitud`      | `numeric(9,6)` |  no  |                |      Punto exacto del marcador       |
|     `longitud`     | `numeric(9,6)` |  no  |                |                                      |
|    `creado_en`     | `timestamptz`  |  no  |    `now()`     |      Ordena la cola de revisión      |
|  `verificado_en`   | `timestamptz`  |  sí  |                | Nulo mientras la ficha no se aprueba |

### Llaves foráneas

|      Columna      |   Referencia   | `ON DELETE` |                Notas                |
| :---------------: | :------------: | :---------: | :---------------------------------: |
|    `ciudad_id`    |    `ciudad`    | `RESTRICT`  | Catálogo referenciado por operación |
| `tipo_negocio_id` | `tipo_negocio` | `RESTRICT`  |     Un tipo en uso no se borra      |

### Constraints

```postgresql
CONSTRAINT chk_comercio_ruc_formato
CHECK (ruc ~ '^[A-Z0-9-]{13,16}$')

CONSTRAINT chk_comercio_latitud_rango
CHECK (latitud BETWEEN 10.7 AND 15.1)

CONSTRAINT chk_comercio_longitud_rango
CHECK (longitud BETWEEN -87.7 AND -82.6)

CONSTRAINT chk_comercio_verificado_coherente
CHECK (
  verificado_en IS NULL
  OR
  verificado_en >= creado_en
)
```

El rango de coordenadas es el mismo que verifica `punto_interes` en
[`Territorio`][territorio]: una coordenada fuera del territorio nicaragüense es
un error de captura, no un comercio remoto.

### Unicidad

|       Nombre       | Definición |      Propósito       |
| :----------------: | :--------: | :------------------: |
| `unq_comercio_ruc` |  `(ruc)`   | [`RF-C-01`][rf-c-01] |

### Triggers

|              Nombre              |          Evento           | Momento  | Nivel |                   Regla                   |        Origen        |
| :------------------------------: | :-----------------------: | :------: | :---: | :---------------------------------------: | :------------------: |
| `trg_comercio_readonly_creadoen` |         `UPDATE`          | `BEFORE` | `ROW` |        `creado_en` no se reescribe        |      Convención      |
|   `trg_comercio_readonly_ruc`    |      `UPDATE OF ruc`      | `BEFORE` | `ROW` | El RUC no se reescribe una vez verificado | [`RF-C-01`][rf-c-01] |
|   `trg_comercio_noreverifica`    | `UPDATE OF verificado_en` | `BEFORE` | `ROW` |     `verificado_en` no vuelve a nulo      | [`RF-C-02`][rf-c-02] |

### Índices

|        Nombre         |                       Definición                       |              Propósito               |
| :-------------------: | :----------------------------------------------------: | :----------------------------------: |
| `idx_comercio_ciudad` |     `(ciudad_id) WHERE verificado_en IS NOT NULL`      |     Listado del mapa por ciudad      |
|  `idx_comercio_cola`  |       `(creado_en) WHERE verificado_en IS NULL`        |    [Cola por antigüedad][rf-b-01]    |
| `idx_comercio_punto`  |                 `(latitud, longitud)`                  | Acotar el rectángulo antes del radio |
| `gin_comercio_nombre` | `GIN (upper(immutable_unaccent(nombre)) gin_trgm_ops)` |     Búsqueda por nombre parcial      |

### Notas de diseño

No hay `estado_comercio`. La visibilidad del comercio es consecuencia de su
verificación y no una máquina propia: `verificado_en` nulo es la ficha que
todavía no aparece, y con valor es la que aparece. Es el uso de la nulidad que
[`Convenciones`][convenciones-nulabilidad] declara como excepción deliberada. Un
catálogo de estados habría duplicado, con otro nombre, lo que ya decide
[`SolicitudVerificacion`][moderacion], y abierto la posibilidad de que ambos
digan cosas distintas sobre la misma ficha.

El RUC no es la llave primaria. Identifica al contribuyente, pero se teclea a
mano en el alta y se corrige mientras la ficha está pendiente; una llave que
cambia arrastra a toda tabla que la referencie. La unicidad basta para impedir el
duplicado sin pagar ese precio.

Los teléfonos son dos columnas y no una tabla hija. [`RF-C-04`][rf-c-04] habla de
«los teléfonos habilitados» en plural, pero ningún requerimiento pide más de dos
ni los clasifica por uso. Una tabla hija se justificaría si hubiera que
distinguir el fijo del móvil o el de reservas del de quejas; mientras no ocurra,
dos columnas evitan una unión en la consulta más frecuente del sistema.

!!! warning "Formato del RUC sin fuente"

    [`RF-C-01`][rf-c-01] exige «el formato alfanumérico oficial» sin
    enumerarlo, y ninguna otra fuente del análisis lo define.
    `chk_comercio_ruc_formato` es provisional y hay que estrecharlo cuando la
    especificación exista.

---

## `comercio_horario`

Una fila por día de la semana. Es lo que permite responder si el local está
abierto ahora mismo sin interpretar texto.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** siete filas por comercio
- **Origen:**
  > - [`RF-C-04`][rf-c-04]

### Columnas

|     Campo     |    Tipo    | Nulo | Predeterminado |             Descripción              |
| :-----------: | :--------: | :--: | :------------: | :----------------------------------: |
| `comercio_id` |   `uuid`   |  no  |                |       Llave foránea `CASCADE`        |
| `dia_semana`  | `smallint` |  no  |                |      0 es domingo, 6 es sábado       |
|   `cerrado`   | `boolean`  |  no  |    `false`     |       El local no abre ese día       |
|    `abre`     |   `time`   |  sí  |                |        Nulo cuando `cerrado`         |
|   `cierra`    |   `time`   |  sí  |                | Menor que `abre` significa madrugada |

### Constraints

```postgresql
CONSTRAINT chk_comerciohorario_dia_rango
CHECK (dia_semana BETWEEN 0 AND 6)

CONSTRAINT chk_comerciohorario_coherente
CHECK (
  (cerrado AND num_nonnulls(abre, cierra) = 0)
  OR
  (NOT cerrado AND num_nonnulls(abre, cierra) = 2)
)

CONSTRAINT chk_comerciohorario_horas_distintas
CHECK (
  cerrado
  OR
  abre <> cierra
)
```

### Unicidad

|          Nombre           |         Definición          |       Propósito       |
| :-----------------------: | :-------------------------: | :-------------------: |
| `unq_comerciohorario_dia` | `(comercio_id, dia_semana)` | Un solo tramo por día |

### Índices

|            Nombre             |                  Definición                   |                   Propósito                    |
| :---------------------------: | :-------------------------------------------: | :--------------------------------------------: |
| `idx_comerciohorario_abierto` | `(comercio_id, dia_semana) WHERE NOT cerrado` | Resolver «abierto ahora» sin leer los cerrados |

### Notas de diseño

Las horas admiten nulo y el `CHECK` obliga a que ambas lo sean a la vez. Un día
cerrado no abre a las 00:00: no tiene hora de apertura. La coherencia ata las
tres columnas para que no exista un día cerrado con horario ni uno abierto sin
él.

Un cierre anterior a la apertura significa madrugada, no error. Un bar que abre a
las 18:00 y cierra a las 02:00 guarda `cierra` menor que `abre`, y la consulta de
«abierto ahora» tiene que contemplar los dos casos. Las alternativas —guardar
26:00, o partir el tramo en dos filas— o inventan una hora que el tipo no admite
o rompen la unicidad por día. Lo que sí se prohíbe es que ambas coincidan, que no
describe ni un día completo ni uno cerrado.

La unicidad por día impide declarar dos franjas, de modo que el comercio que
cierra a mediodía no puede expresar su pausa. Ningún requerimiento lo pide y
admitirlo obligaría a sustituir la unicidad por un `EXCLUDE` sobre rangos de
hora; queda anotado porque es la primera limitación que el segmento gastronómico
va a encontrar.

---

## `platillo_estrella`

El platillo emblemático, principal gancho del segmento gastronómico. Varias filas
por comercio, una sola vigente.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** unas pocas por comercio a lo largo del piloto
- **Origen:**
  > - [`RF-C-05`][rf-c-05]

### Columnas

|        Campo        |      Tipo       | Nulo | Predeterminado |             Descripción              |
| :-----------------: | :-------------: | :--: | :------------: | :----------------------------------: |
|    `comercio_id`    |     `uuid`      |  no  |                |       Llave foránea `CASCADE`        |
|      `nombre`       |    `varchar`    |  no  |                |                                      |
|    `descripcion`    |     `text`      |  no  |      `''`      |                                      |
| `precio_referencia` | `numeric(12,2)` |  no  |                |  Orientativo, no es tarifa cobrable  |
|     `moneda_id`     |     `uuid`      |  no  |                | Llave foránea `RESTRICT` a `moneda`  |
|      `foto_id`      |     `uuid`      |  sí  |                |  Llave foránea `SET NULL` a `foto`   |
|     `creado_en`     |  `timestamptz`  |  no  |    `now()`     |                                      |
|    `retirado_en`    |  `timestamptz`  |  sí  |                | Nulo mientras es el platillo vigente |

### Constraints

```postgresql
CONSTRAINT chk_platilloestrella_precio_positivo
CHECK (precio_referencia > 0)

CONSTRAINT chk_platilloestrella_retirado_coherente
CHECK (
  retirado_en IS NULL
  OR
  retirado_en >= creado_en
)
```

### Unicidad

|             Nombre             |                Definición                 |               Propósito               |
| :----------------------------: | :---------------------------------------: | :-----------------------------------: |
| `unq_platilloestrella_vigente` | `(comercio_id) WHERE retirado_en IS NULL` | Un solo platillo vigente por comercio |

### Triggers

|             Nombre              |         Evento          | Momento  | Nivel |             Regla              |        Origen        |
| :-----------------------------: | :---------------------: | :------: | :---: | :----------------------------: | :------------------: |
| `trg_platilloestrella_norevive` | `UPDATE OF retirado_en` | `BEFORE` | `ROW` | `retirado_en` no vuelve a nulo | [`RF-C-05`][rf-c-05] |

### Notas de diseño

Reemplazar es insertar y retirar, no actualizar. [`RF-C-05`][rf-c-05] llama
«reemplazo» a la operación y la palabra invita a un `UPDATE`. Se modela como dos
filas porque la anterior sigue siendo información útil —qué ofrecía el comercio
la temporada pasada— y porque una tarjeta que el turista ya vio no debería
cambiar de contenido bajo el mismo identificador.

El índice único parcial es lo que hace cumplir «uno vigente», no un trigger que
cuente filas. La unicidad parcial la impone el motor sin leer nada y sin ventana
de carrera entre dos reemplazos simultáneos.

---

## `suscripcion`

Plan de pago que destaca al comercio en el mapa. Es la única entidad del módulo
cuya ausencia es el estado normal.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** decenas en el piloto
- **Origen:**
  > - [`RF-C-11`][rf-c-11]
  > - [`RF-C-12`][rf-c-12]

### Columnas

|       Campo       |      Tipo       | Nulo | Predeterminado |              Descripción               |
| :---------------: | :-------------: | :--: | :------------: | :------------------------------------: |
|   `comercio_id`   |     `uuid`      |  no  |                |        Llave foránea `RESTRICT`        |
|      `monto`      | `numeric(12,2)` |  no  |                |         Congelado al contratar         |
|    `moneda_id`    |     `uuid`      |  no  |                |  Llave foránea `RESTRICT` a `moneda`   |
| `referencia_pago` |    `varchar`    |  no  |                | Identificador que devuelve la pasarela |
|    `inicia_en`    |  `timestamptz`  |  no  |    `now()`     |  Se escribe al confirmar la pasarela   |
|    `expira_en`    |  `timestamptz`  |  no  |                | Cuándo retorna a visibilidad estándar  |
|  `cancelada_en`   |  `timestamptz`  |  sí  |                |       Nulo salvo baja anticipada       |

### Constraints

```postgresql
CONSTRAINT chk_suscripcion_monto_positivo
CHECK (monto > 0)

CONSTRAINT chk_suscripcion_vigencia
CHECK (expira_en > inicia_en)

CONSTRAINT chk_suscripcion_cancelada_coherente
CHECK (
  cancelada_en IS NULL
  OR
  cancelada_en BETWEEN inicia_en AND expira_en
)
```

### Unicidad

|          Nombre          |                               Definición                                |                  Propósito                  |
| :----------------------: | :---------------------------------------------------------------------: | :-----------------------------------------: |
| `exc_suscripcion_solape` | `EXCLUDE (comercio_id WITH =, tstzrange(inicia_en, expira_en) WITH &&)` | Dos planes del mismo comercio no se solapan |

### Triggers

|              Nombre              |  Evento  | Momento  | Nivel |                    Regla                    |        Origen        |
| :------------------------------: | :------: | :------: | :---: | :-----------------------------------------: | :------------------: |
| `trg_suscripcion_readonly_cobro` | `UPDATE` | `BEFORE` | `ROW` | Monto, moneda y referencia no se reescriben | [`RF-C-11`][rf-c-11] |

### Índices

|          Nombre           |                 Definición                 |                 Propósito                 |
| :-----------------------: | :----------------------------------------: | :---------------------------------------: |
| `idx_suscripcion_activa`  | `(comercio_id) WHERE cancelada_en IS NULL` |   Resolver si el marcador va destacado    |
| `brin_suscripcion_expira` |             `BRIN (expira_en)`             | El barrido de vencimientos recorre rangos |

### Notas de diseño

La ausencia de suscripción es el estado normal, no una carencia.
[`RF-C-02`][rf-c-02] hace el registro gratuito de forma permanente, así que la
suscripción no puede ser una columna del comercio: sería nula en la mayoría de
las filas y obligaría a leer «sin plan» como un defecto. Es una entidad aparte
cuya inexistencia no significa nada malo.

Vencer no cambia ninguna fila. [`RF-C-12`][rf-c-12] devuelve al comercio a
visibilidad estándar sin perder ficha, campañas ni métricas, y eso se consigue
comparando `expira_en` con el instante de la consulta. No hay proceso que marque
suscripciones vencidas y, por lo tanto, no hay estado que pueda quedar
desincronizado si ese proceso falla.

Impedir dos planes simultáneos es impedir que dos rangos de fechas se solapen,
que es la forma de regla que [`Convenciones`][convenciones-invariantes] asigna a
`EXCLUDE`. Una unicidad sobre el comercio impediría además renovar por
adelantado, que es una operación legítima.

---

## `institucion_cultural`

Casa de cultura, fundación, ticketera o teatro que programa la agenda.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** decenas en el piloto
- **Origen:**
  > - [`RF-I-07`][rf-i-07]

### Columnas

|         Campo         |     Tipo      | Nulo | Predeterminado |              Descripción              |
| :-------------------: | :-----------: | :--: | :------------: | :-----------------------------------: |
|      `ciudad_id`      |    `uuid`     |  no  |                |     Dónde está, no dónde programa     |
| `tipo_institucion_id` |    `uuid`     |  no  |                |  Llave foránea a `tipo_institucion`   |
|       `nombre`        |   `varchar`   |  no  |                |                                       |
|   `correo_contacto`   |   `citext`    |  no  |                |                                       |
|      `telefono`       |   `varchar`   |  no  |                |                                       |
|    `documento_id`     |   `varchar`   |  no  |                |     Acredita su existencia legal      |
|      `creado_en`      | `timestamptz` |  no  |    `now()`     |      Ordena la cola de revisión       |
|    `verificado_en`    | `timestamptz` |  sí  |                | Nulo mientras el moderador no aprueba |

### Llaves foráneas

|        Columna        |     Referencia     | `ON DELETE` |         Notas          |
| :-------------------: | :----------------: | :---------: | :--------------------: |
|      `ciudad_id`      |      `ciudad`      | `RESTRICT`  |                        |
| `tipo_institucion_id` | `tipo_institucion` | `RESTRICT`  | Catálogo administrable |

### Constraints

```postgresql
CONSTRAINT chk_institucioncultural_verificado_coherente
CHECK (
  verificado_en IS NULL
  OR
  verificado_en >= creado_en
)
```

### Unicidad

|              Nombre              |          Definición          |                   Propósito                   |
| :------------------------------: | :--------------------------: | :-------------------------------------------: |
| `unq_institucioncultural_nombre` | `(ciudad_id, lower(nombre))` | Un teatro no se registra dos veces por ciudad |

### Triggers

|                   Nombre                    |        Evento        | Momento  | Nivel |                      Regla                       |        Origen        |
| :-----------------------------------------: | :------------------: | :------: | :---: | :----------------------------------------------: | :------------------: |
| `trg_institucioncultural_readonly_creadoen` |       `UPDATE`       | `BEFORE` | `ROW` |           `creado_en` no se reescribe            |      Convención      |
|     `trg_institucioncultural_programa`      | `INSERT` en `evento` | `BEFORE` | `ROW` | Solo programa la institución con `verificado_en` | [`RF-I-07`][rf-i-07] |

### Índices

|              Nombre              |                Definición                 |           Propósito            |
| :------------------------------: | :---------------------------------------: | :----------------------------: |
| `idx_institucioncultural_ciudad` |               `(ciudad_id)`               |       Agenda por ciudad        |
|  `idx_institucioncultural_cola`  | `(creado_en) WHERE verificado_en IS NULL` | [Cola por antigüedad][rf-b-01] |

### Notas de diseño

La institución pertenece a una ciudad y el evento puede ocurrir en otra. Un
teatro de León puede llevar una función a Granada, así que la ciudad del evento
es llave propia de [`Agenda`][agenda] y no se hereda de aquí. Esta columna dice
dónde está la institución, no dónde ocurre lo que programa.

El veto a programar es un trigger sobre `evento` y no una comprobación en el
servicio. [`RF-I-07`][rf-i-07] impide programar antes de la aprobación, y el
requerimiento no admite excepción por vía de escritura: una carga masiva de
agenda tiene que chocar con la misma regla que el formulario.

---

## `tipo_institucion`

Las cuatro figuras que enumera [`RF-I-07`][rf-i-07]. Sigue la forma de las listas
cerradas de [`Catálogos`][catalogos]: el código nunca cambia aunque cambie el
texto que se muestra.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

### Columnas

|   Campo    |   Tipo    | Nulo | Predeterminado |               Descripción                |
| :--------: | :-------: | :--: | :------------: | :--------------------------------------: |
|  `codigo`  | `varchar` |  no  |                |      Lo que referencian las reglas       |
| `etiqueta` | `varchar` |  no  |                |            Lo que se muestra             |
|  `activo`  | `boolean` |  no  |     `true`     | Retirarlo no borra las filas que lo usan |

### Unicidad

|            Nombre            | Definición |      Propósito       |
| :--------------------------: | :--------: | :------------------: |
| `unq_tipoinstitucion_codigo` | `(codigo)` | El código identifica |

### Filas

|     Código     |    Etiqueta     |
| :------------: | :-------------: |
| `casa_cultura` | Casa de cultura |
|  `fundacion`   |    Fundación    |
|  `ticketera`   |    Ticketera    |
|    `teatro`    |     Teatro      |

### Notas de diseño

!!! warning "Catálogo ausente en el módulo de catálogos"

    `tipo_institucion` **no aparece** en la lista de listas cerradas de
    [`Catálogos`][catalogos], que se cerró antes de redactar este módulo.
    Corresponde moverlo ahí, junto a `tipo_negocio` y `tipo_beneficio`, o
    aceptar que quede declarado solo aquí y romper la regla de que todo catálogo
    vive en el mismo sitio.

---

## Fuera de este módulo

|            Cosa            |             Dónde vive             |                             Por qué no aquí                             |
| :------------------------: | :--------------------------------: | :---------------------------------------------------------------------: |
|    `foto` del comercio     |     [`Territorio`][territorio]     | Una sola tabla de fotos con referencias excluyentes para cuatro dueños  |
|         `alcaldia`         |     [`Territorio`][territorio]     |  Es autoridad sobre un territorio, no una organización que se registra  |
|       `tipo_negocio`       |      [`Catálogos`][catalogos]      |           Lista cerrada, como el resto de las clasificaciones           |
|          `evento`          |         [`Agenda`][agenda]         |   Cuelga de la institución, pero su vigencia y su clonación son suyas   |
| `campania_cupon` y `cupon` |      [`Insignias`][insignias]      |       El comercio los emite, pero pertenecen al circuito de canje       |
|  `solicitud_verificacion`  |     [`Moderación`][moderacion]     | Una sola cola para acreditaciones, comercios, alcaldías e instituciones |
|         `geocerca`         | [`Notificaciones`][notificaciones] |             El radio se separa de la entidad que lo motiva              |

[agenda]: agenda.md
[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[convenciones-invariantes]: ../convenciones.md#invariantes
[convenciones-nulabilidad]: ../convenciones.md#nulabilidad
[d-12]: ../decisiones.md#d-12
[insignias]: insignias.md
[moderacion]: moderacion.md
[notificaciones]: notificaciones.md
[territorio]: territorio.md
[rf-b-01]: ../../requerimientos/funcionales/backoffice.md#rf-b-01
[rf-c-01]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-01
[rf-c-02]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-02
[rf-c-03]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-03
[rf-c-04]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-04
[rf-c-05]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-05
[rf-c-11]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-11
[rf-c-12]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-12
[rf-i-07]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-07
