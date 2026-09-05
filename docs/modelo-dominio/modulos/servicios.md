---
icon: lucide/handshake
---

# Servicios y reservas

El motor del sistema: lo que el guía publica, lo que el turista solicita, cómo se
encuentran y qué queda registrado del servicio acordado. Es el módulo con más
tablas calientes y el único donde el dinero cambia de manos, aunque el cobro en
sí viva en [`Finanzas`][finanzas].

La reserva nace por dos caminos —una postulación aceptada o la contratación
directa de un recorrido publicado— y es una sola tabla, porque todo lo posterior
es idéntico: sala de chat, cierre, evaluación mutua, pago y comisión.

## Requerimientos cubiertos

- [`RF-P-08`][rf-p-08]
- [`RF-P-09`][rf-p-09]
- [`RF-P-10`][rf-p-10]
- [`RF-P-11`][rf-p-11]
- [`RF-P-12`][rf-p-12]
- [`RF-P-13`][rf-p-13]
- [`RF-P-14`][rf-p-14]
- [`RF-T-15`][rf-t-15]
- [`RF-T-16`][rf-t-16]
- [`RF-T-17`][rf-t-17]
- [`RF-T-18`][rf-t-18]
- [`RF-T-30`][rf-t-30]

---

## `recorrido`

Ficha del producto que publica un guía, con su tarifa y sus cupos. Es lo que
[`Convenciones`][convenciones-reservadas] reserva bajo esa palabra: lo que el
turista arma es un **itinerario**, no un recorrido.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** unos pocos por guía
- **Origen:**
  > - [`RF-P-08`][rf-p-08]
  > - [`RF-P-10`][rf-p-10]
  > - [`RF-P-11`][rf-p-11]

### Columnas

|         Campo         |      Tipo       | Nulo | Predeterminado |             Descripción             |
| :-------------------: | :-------------: | :--: | :------------: | :---------------------------------: |
| `perfil_prestador_id` |     `uuid`      |  no  |                |     Solo un perfil de tipo guía     |
|      `ciudad_id`      |     `uuid`      |  no  |                |   Zona de operación del recorrido   |
|       `titulo`        |    `varchar`    |  no  |                |                                     |
|     `descripcion`     |     `text`      |  no  |      `''`      |                                     |
|        `ruta`         |     `text`      |  no  |      `''`      |  Descripción de la ruta que sigue   |
|  `duracion_estimada`  |   `interval`    |  no  |                |                                     |
|       `tarifa`        | `numeric(12,2)` |  no  |                |     Por reserva, no por persona     |
|      `moneda_id`      |     `uuid`      |  no  |                | Llave foránea `RESTRICT` a `moneda` |
|  `capacidad_minima`   |   `smallint`    |  no  |      `1`       |                                     |
|  `capacidad_maxima`   |   `smallint`    |  no  |                |   Tope duro de cincuenta personas   |
|       `pausado`       |    `boolean`    |  no  |    `false`     |  Fuera del catálogo sin retirarlo   |
|      `creado_en`      |  `timestamptz`  |  no  |    `now()`     |                                     |
|     `retirado_en`     |  `timestamptz`  |  sí  |                | Nulo mientras sigue en el catálogo  |

### Llaves foráneas

|        Columna        |     Referencia     | `ON DELETE` |          Notas          |
| :-------------------: | :----------------: | :---------: | :---------------------: |
| `perfil_prestador_id` | `perfil_prestador` | `RESTRICT`  | Es histórico y contable |
|      `ciudad_id`      |      `ciudad`      | `RESTRICT`  |                         |
|      `moneda_id`      |      `moneda`      | `RESTRICT`  |                         |

### Constraints

```postgresql
CONSTRAINT chk_recorrido_tarifa_positiva
CHECK (tarifa > 0)

CONSTRAINT chk_recorrido_capacidad_tope
CHECK (capacidad_maxima BETWEEN 1 AND 50)

CONSTRAINT chk_recorrido_capacidad_orden
CHECK (capacidad_minima BETWEEN 1 AND capacidad_maxima)

CONSTRAINT chk_recorrido_duracion_positiva
CHECK (duracion_estimada > INTERVAL '0')

CONSTRAINT chk_recorrido_retirado_coherente
CHECK (
  retirado_en IS NULL
  OR
  retirado_en >= creado_en
)
```

### Triggers

|              Nombre               |                  Evento                   | Momento  | Nivel |                      Regla                      |        Origen        |
| :-------------------------------: | :---------------------------------------: | :------: | :---: | :---------------------------------------------: | :------------------: |
|     `trg_recorrido_solo_guia`     | `INSERT`, `UPDATE OF perfil_prestador_id` | `BEFORE` | `ROW` |  El perfil ofrece el tipo de servicio de guía   | [`RF-P-08`][rf-p-08] |
| `trg_recorrido_retiro_bloqueado`  |          `UPDATE OF retirado_en`          | `BEFORE` | `ROW` | Rechaza el retiro con reservas pagadas a futuro | [`RF-P-11`][rf-p-11] |
| `trg_recorrido_readonly_creadoen` |                 `UPDATE`                  | `BEFORE` | `ROW` |           `creado_en` no se reescribe           |      Convención      |

### Índices

|          Nombre          |                           Definición                            |               Propósito                |
| :----------------------: | :-------------------------------------------------------------: | :------------------------------------: |
| `idx_recorrido_catalogo` |        `(perfil_prestador_id) WHERE retirado_en IS NULL`        |    [Listado del catálogo][rf-p-09]     |
|  `idx_recorrido_oferta`  | `(ciudad_id, tarifa) WHERE retirado_en IS NULL AND NOT pausado` | Búsqueda del turista por zona y precio |

### Notas de diseño

`pausado` y `retirado_en` son dos cosas distintas y por eso son dos columnas.
[`RF-P-09`][rf-p-09] pide mostrar el recorrido como publicado, pausado o sin
cupos: pausar es reversible y saca la ficha de la oferta sin perderla; retirar es
la baja, y [`RF-P-11`][rf-p-11] la bloquea mientras haya reservas pagadas a
futuro. «Sin cupos» no es ninguna de las dos: se deriva contando reservas vivas
contra `capacidad_maxima`, y guardarlo sería un contador que puede quedar
desincronizado.

El recorrido no tiene máquina de estados. Dos booleanos y una fecha describen
todo su ciclo, y ningún requerimiento pide registrar quién lo pausó ni por qué,
que es lo que justificaría un catálogo de estado con su tabla de transiciones.

Solo el guía publica catálogo. El traductor llega al trabajo por un único
camino, la postulación, y por eso `trg_recorrido_solo_guia` comprueba el tipo de
servicio del perfil. Sin ese trigger la regla viviría solo en la interfaz, y una
carga masiva o una corrección manual la saltaría sin que nadie lo note.

---

## `recorrido_dia`

Los días de la semana en que el recorrido se ofrece. Una fila por día.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** hasta siete filas por recorrido
- **Origen:**
  > - [`RF-P-08`][rf-p-08]

### Columnas

|     Campo      |    Tipo    | Nulo | Predeterminado |        Descripción        |
| :------------: | :--------: | :--: | :------------: | :-----------------------: |
| `recorrido_id` |   `uuid`   |  no  |                |  Llave foránea `CASCADE`  |
|  `dia_semana`  | `smallint` |  no  |                | 0 es domingo, 6 es sábado |

### Constraints

```postgresql
CONSTRAINT chk_recorridodia_rango
CHECK (dia_semana BETWEEN 0 AND 6)
```

### Unicidad

|         Nombre         |          Definición          |           Propósito            |
| :--------------------: | :--------------------------: | :----------------------------: |
| `unq_recorridodia_dia` | `(recorrido_id, dia_semana)` | Un día no se declara dos veces |

### Notas de diseño

Es una tabla y no una cadena separada por comas ni un arreglo, porque la
disponibilidad se consulta al filtrar: el turista busca recorridos de un sábado y
esa consulta tiene que poder usar un índice. Una cadena obligaría a interpretarla
en cada fila candidata y no se puede restringir para que no contenga un octavo
día.

---

## `convocatoria`

Lo que el turista publica para que guías y traductores se postulen. Circula sin
su identidad.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** miles al año
- **Origen:**
  > - [`RF-T-15`][rf-t-15]
  > - [`RF-T-16`][rf-t-16]

### Columnas

|         Campo          |      Tipo       | Nulo | Predeterminado |              Descripción              |
| :--------------------: | :-------------: | :--: | :------------: | :-----------------------------------: |
|  `perfil_turista_id`   |     `uuid`      |  no  |                |  Quién la publica; **no se expone**   |
|    `itinerario_id`     |     `uuid`      |  no  |                |   La ruta planificada que se ofrece   |
|      `idioma_id`       |     `uuid`      |  no  |                |     Idioma requerido al prestador     |
|   `tipo_servicio_id`   |     `uuid`      |  no  |                |     Guía o traductor, nunca ambos     |
|      `estado_id`       |     `uuid`      |  no  |                | Llave foránea a `estado_convocatoria` |
|     `fecha_inicio`     |     `date`      |  no  |                |       Inicio del rango de viaje       |
|      `fecha_fin`       |     `date`      |  no  |                |        Fin del rango de viaje         |
| `presupuesto_estimado` | `numeric(12,2)` |  no  |                |      Orientativo, no compromete       |
|      `moneda_id`       |     `uuid`      |  no  |                |  Llave foránea `RESTRICT` a `moneda`  |
|      `creado_en`       |  `timestamptz`  |  no  |    `now()`     |                                       |

### Llaves foráneas

|       Columna       |      Referencia       | `ON DELETE` |               Notas               |
| :-----------------: | :-------------------: | :---------: | :-------------------------------: |
| `perfil_turista_id` |   `perfil_turista`    | `RESTRICT`  |           Es histórico            |
|   `itinerario_id`   |     `itinerario`      | `RESTRICT`  | No se borra con convocatoria viva |
|     `idioma_id`     |       `idioma`        | `RESTRICT`  |                                   |
| `tipo_servicio_id`  |    `tipo_servicio`    | `RESTRICT`  |                                   |
|     `estado_id`     | `estado_convocatoria` | `RESTRICT`  |                                   |
|     `moneda_id`     |       `moneda`        | `RESTRICT`  |                                   |

### Constraints

```postgresql
CONSTRAINT chk_convocatoria_fechas_orden
CHECK (fecha_fin >= fecha_inicio)

CONSTRAINT chk_convocatoria_presupuesto_positivo
CHECK (presupuesto_estimado > 0)
```

Que las fechas sean futuras se comprueba al publicar y no como restricción, por
la misma razón que en [`Agenda`][agenda]: mañana la convocatoria de hoy la
violaría y la fila dejaría de poder actualizarse.

### Triggers

|            Nombre            |        Evento         | Momento | Nivel |                    Regla                     |        Origen        |
| :--------------------------: | :-------------------: | :-----: | :---: | :------------------------------------------: | :------------------: |
| `trg_convocatoria_historial` | `UPDATE OF estado_id` | `AFTER` | `ROW` | Inserta la fila en `transicion_convocatoria` | [`RF-S-10`][rf-s-10] |

### Índices

|           Nombre            |                  Definición                   |                Propósito                 |
| :-------------------------: | :-------------------------------------------: | :--------------------------------------: |
| `idx_convocatoria_tablero`  | `(tipo_servicio_id, idioma_id, fecha_inicio)` |     [Tablero del prestador][rf-p-12]     |
| `idx_convocatoria_vigencia` |               `(fecha_inicio)`                | El barrido que expira las no adjudicadas |
| `idx_convocatoria_turista`  |     `(perfil_turista_id, creado_en DESC)`     |        Sus convocatorias abiertas        |

### Notas de diseño

El anonimato de [`RF-T-16`][rf-t-16] no se modela ocultando la llave: la
convocatoria sabe perfectamente de quién es, porque hace falta para adjudicar y
para abrir la sala. Lo que no ocurre es que el tablero del prestador lea
`perfil_turista_id`, y esa restricción vive en la proyección que sirve
[`RF-P-12`][rf-p-12], no en el esquema. Guardar la convocatoria sin dueño habría
hecho imposible saber quién la publicó.

`tipo_servicio_id` obliga a que contratar guía y traductor sean dos
convocatorias. [`RF-T-30`][rf-t-30] los declara servicios independientes con su
tarifa, su sala, su cierre y su evaluación; una sola convocatoria con dos
adjudicaciones habría hecho que cancelar una arrastrara a la otra.

Nadie declara un plazo de cierre. [`RF-T-15`][rf-t-15] ya obliga a dar el rango
de fechas del viaje, así que la convocatoria expira al llegar `fecha_inicio` sin
adjudicar. Un plazo aparte sería un segundo dato que puede contradecir al
primero.

---

## `estado_convocatoria`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma una: `admite_postulacion`.

|    Código    | `admite_postulacion` | `es_terminal` |
| :----------: | :------------------: | :-----------: |
| `publicada`  |        **sí**        |      no       |
| `adjudicada` |          no          |    **sí**     |
| `cancelada`  |          no          |    **sí**     |
|  `expirada`  |          no          |    **sí**     |

---

## `postulacion`

La oferta de un prestador sobre una convocatoria.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** varias por convocatoria
- **Origen:**
  > - [`RF-P-13`][rf-p-13]
  > - [`RF-T-17`][rf-t-17]

### Columnas

|         Campo         |      Tipo       | Nulo | Predeterminado |             Descripción             |
| :-------------------: | :-------------: | :--: | :------------: | :---------------------------------: |
|   `convocatoria_id`   |     `uuid`      |  no  |                |      Llave foránea `RESTRICT`       |
| `perfil_prestador_id` |     `uuid`      |  no  |                |      Llave foránea `RESTRICT`       |
|  `tarifa_propuesta`   | `numeric(12,2)` |  no  |                |      Lo que el prestador pide       |
|      `moneda_id`      |     `uuid`      |  no  |                | Llave foránea `RESTRICT` a `moneda` |
|       `mensaje`       |     `text`      |  no  |      `''`      |         Presentación breve          |
|      `creado_en`      |  `timestamptz`  |  no  |    `now()`     |                                     |
|     `aceptada_en`     |  `timestamptz`  |  sí  |                |      Nulo salvo la adjudicada       |
|    `descartada_en`    |  `timestamptz`  |  sí  |                |        Nulo salvo las demás         |

### Constraints

```postgresql
CONSTRAINT chk_postulacion_tarifa_positiva
CHECK (tarifa_propuesta > 0)

CONSTRAINT chk_postulacion_resolucion_excluyente
CHECK (num_nonnulls(aceptada_en, descartada_en) <= 1)
```

### Unicidad

|           Nombre            |                    Definición                     |                   Propósito                    |
| :-------------------------: | :-----------------------------------------------: | :--------------------------------------------: |
| `unq_postulacion_prestador` |     `(convocatoria_id, perfil_prestador_id)`      |      Un prestador se postula una sola vez      |
| `unq_postulacion_aceptada`  | `(convocatoria_id) WHERE aceptada_en IS NOT NULL` | Una convocatoria adjudica una sola postulación |

### Triggers

|                 Nombre                 |  Evento  | Momento  | Nivel |                       Regla                       |        Origen        |
| :------------------------------------: | :------: | :------: | :---: | :-----------------------------------------------: | :------------------: |
| `trg_postulacion_convocatoria_abierta` | `INSERT` | `BEFORE` | `ROW` |    La convocatoria tiene `admite_postulacion`     | [`RF-P-13`][rf-p-13] |
|       `trg_postulacion_norevive`       | `UPDATE` | `BEFORE` | `ROW` | `aceptada_en` y `descartada_en` no vuelven a nulo | [`RF-T-17`][rf-t-17] |

### Índices

|            Nombre             |               Definición                |             Propósito             |
| :---------------------------: | :-------------------------------------: | :-------------------------------: |
| `idx_postulacion_comparacion` |     `(convocatoria_id, creado_en)`      | [Comparar postulaciones][rf-t-17] |
|  `idx_postulacion_prestador`  | `(perfil_prestador_id, creado_en DESC)` |    Sus postulaciones enviadas     |

### Notas de diseño

La postulación no tiene catálogo de estado ni tabla de transiciones. Su situación
son dos fechas nulables: ambas nulas es `enviada`, una u otra con valor es
`aceptada` o `descartada`. Es el uso de la nulidad que
[`Convenciones`][convenciones-nulabilidad] declara informativa, y evita inventar
una máquina para un ciclo que no se ramifica ni admite vuelta atrás.

Adjudicar es una sola transacción: escribe `aceptada_en` en una fila,
`descartada_en` en las demás, mueve la convocatoria a `adjudicada` y crea la
reserva. `unq_postulacion_aceptada` es lo que impide que dos adjudicaciones
simultáneas produzcan dos reservas sobre la misma convocatoria; sin él, la
comprobación viviría en la aplicación y tendría ventana de carrera.

---

## `reserva`

El servicio contratado. Es la tabla más caliente del sistema y la única que
concentra las dos vías de contratación.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** decenas de miles al año
- **Origen:**
  > - [`RF-T-18`][rf-t-18]
  > - [`RF-P-14`][rf-p-14]
  > - [`RF-P-10`][rf-p-10]

### Columnas

|         Campo         |      Tipo       | Nulo | Predeterminado |           Descripción            |
| :-------------------: | :-------------: | :--: | :------------: | :------------------------------: |
|  `perfil_turista_id`  |     `uuid`      |  no  |                |     Llave foránea `RESTRICT`     |
| `perfil_prestador_id` |     `uuid`      |  no  |                |     Llave foránea `RESTRICT`     |
|   `postulacion_id`    |     `uuid`      |  sí  |                | Origen A, excluyente con el otro |
|    `recorrido_id`     |     `uuid`      |  sí  |                | Origen B, excluyente con el otro |
|    `itinerario_id`    |     `uuid`      |  sí  |                | Nulo si se contrató un recorrido |
|      `estado_id`      |     `uuid`      |  no  |                | Llave foránea a `estado_reserva` |
|       `tarifa`        | `numeric(12,2)` |  no  |                |      **Congelada** al crear      |
|      `moneda_id`      |     `uuid`      |  no  |                |        Congelada al crear        |
|  `cantidad_personas`  |   `smallint`    |  no  |      `1`       |        Congelada al crear        |
|   `punto_encuentro`   |    `varchar`    |  no  |      `''`      |      Se acuerda en la sala       |
|      `inicia_en`      |  `timestamptz`  |  no  |                |    Cuándo empieza el servicio    |
|     `finaliza_en`     |  `timestamptz`  |  no  |                |          Cuándo termina          |
|      `creado_en`      |  `timestamptz`  |  no  |    `now()`     |                                  |

### Llaves foráneas

|        Columna        |     Referencia     | `ON DELETE` |               Notas               |
| :-------------------: | :----------------: | :---------: | :-------------------------------: |
|  `perfil_turista_id`  |  `perfil_turista`  | `RESTRICT`  |      Es histórico y contable      |
| `perfil_prestador_id` | `perfil_prestador` | `RESTRICT`  |      Es histórico y contable      |
|   `postulacion_id`    |   `postulacion`    | `RESTRICT`  |                                   |
|    `recorrido_id`     |    `recorrido`     | `RESTRICT`  |                                   |
|    `itinerario_id`    |    `itinerario`    | `RESTRICT`  | Bloquea el borrado del itinerario |
|      `estado_id`      |  `estado_reserva`  | `RESTRICT`  |                                   |
|      `moneda_id`      |      `moneda`      | `RESTRICT`  |                                   |

### Constraints

```postgresql
CONSTRAINT chk_reserva_origen_excluyente
CHECK (num_nonnulls(postulacion_id, recorrido_id) = 1)

CONSTRAINT chk_reserva_tarifa_positiva
CHECK (tarifa > 0)

CONSTRAINT chk_reserva_personas_positiva
CHECK (cantidad_personas >= 1)

CONSTRAINT chk_reserva_horario_orden
CHECK (finaliza_en > inicia_en)
```

### Unicidad

|             Nombre             |                                                Definición                                                 |                 Propósito                 |
| :----------------------------: | :-------------------------------------------------------------------------------------------------------: | :---------------------------------------: |
|   `unq_reserva_postulacion`    |                            `(postulacion_id) WHERE postulacion_id IS NOT NULL`                            |   Una adjudicación produce una reserva    |
| `exc_reserva_solape_prestador` | `EXCLUDE (perfil_prestador_id WITH =, tstzrange(inicia_en, finaliza_en) WITH &&) WHERE (NOT es_terminal)` | Dos reservas del mismo guía no se solapan |

### Triggers

|              Nombre              |        Evento         | Momento  | Nivel |                    Regla                    |           Origen           |
| :------------------------------: | :-------------------: | :------: | :---: | :-----------------------------------------: | :------------------------: |
|  `trg_reserva_readonly_tarifa`   |       `UPDATE`        | `BEFORE` | `ROW` | Tarifa, moneda y cantidad no se reescriben  |    [`RF-P-10`][rf-p-10]    |
| `trg_reserva_cancelacion_motivo` | `UPDATE OF estado_id` | `BEFORE` | `ROW` |   Cancelar con menos de 24 h exige motivo   | [Reserva][estados-reserva] |
|     `trg_reserva_historial`      | `UPDATE OF estado_id` | `AFTER`  | `ROW` |   Inserta la fila en `transicion_reserva`   |    [`RF-S-10`][rf-s-10]    |
|     `trg_reserva_no_borrar`      |       `DELETE`        | `BEFORE` | `ROW` | Bloquea el borrado; es un registro contable |    [`RF-T-26`][rf-t-26]    |

### Índices

|         Nombre          |                   Definición                    |                Propósito                |
| :---------------------: | :---------------------------------------------: | :-------------------------------------: |
|  `idx_reserva_turista`  |      `(perfil_turista_id, inicia_en DESC)`      |          Historial del turista          |
| `idx_reserva_prestador` |     `(perfil_prestador_id, inicia_en DESC)`     |          Agenda del prestador           |
|  `idx_reserva_estado`   |            `(estado_id, inicia_en)`             |  El barrido que abre, expira y cierra   |
| `idx_reserva_recorrido` | `(recorrido_id) WHERE recorrido_id IS NOT NULL` | Contar cupos vivos y bloquear el retiro |

### Notas de diseño

Las dos vías de contratación son dos llaves nulables y un `CHECK` que exige
exactamente una, no dos tablas. Todo lo posterior a la creación —sala, cierre,
evaluación mutua, pago y comisión— es idéntico en ambos casos, así que dos tablas
habrían duplicado el ciclo completo y obligado a unirlas en cada consulta de
historial. Es el mismo patrón de referencias excluyentes que usa `foto` en
[`Territorio`][territorio].

La tarifa se congela y un trigger lo impone. [`RF-P-10`][rf-p-10] prohíbe que un
cambio de tarifa afecte reservas ya creadas, y si la reserva leyera el precio del
recorrido, un ajuste posterior cambiaría retroactivamente lo que el turista
aceptó pagar. El valor copiado no es redundancia: es la tarifa que se acordó, un
hecho propio de la reserva.

El solapamiento se impide con `EXCLUDE` y no con una comprobación en el servicio.
Es la regla que [`Convenciones`][convenciones-invariantes] nombra como ejemplo
del mecanismo: dos reservas del mismo guía en el mismo horario. Con dos
peticiones simultáneas, una comprobación por lectura previa dejaría pasar ambas.

`itinerario_id` es nulo cuando el turista contrató un recorrido del catálogo,
porque el trazado en ese caso es del prestador. Es la relación opcional que el
diagrama de nivel 0 muestra entre `Itinerario` y `Reserva`.

---

## `estado_reserva`

Siete estados. Es el catálogo con más columnas propias del sistema, porque de él
depende dónde está el dinero.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 7 filas

A las cinco columnas comunes suma dos: `admite_cancelacion` y `retiene_fondos`.

|      Código      |         Dónde está el dinero          | `admite_cancelacion` | `retiene_fondos` | `es_terminal` |
| :--------------: | :-----------------------------------: | :------------------: | :--------------: | :-----------: |
| `pendiente_pago` |         En tránsito, de nadie         |          no          |        no        |      no       |
|   `confirmada`   |      Retenido por la plataforma       |        **sí**        |      **sí**      |      no       |
|    `en_curso`    |      Retenido por la plataforma       |          no          |      **sí**      |      no       |
|    `prestada`    |      Retenido por la plataforma       |          no          |      **sí**      |      no       |
|    `cerrada`     | Liberado al prestador, menos comisión |          no          |        no        |    **sí**     |
|   `cancelada`    |        Reembolsado al turista         |          no          |        no        |    **sí**     |
|    `expirada`    |            Nunca se cobró             |          no          |        no        |    **sí**     |

### Notas de diseño

Hay dos estados antes del recorrido porque el turista paga al reservar y la
plataforma retiene el dinero hasta el cierre: uno mientras la pasarela confirma
el cobro y otro cuando el dinero ya está retenido. Sin esa separación no habría
forma de distinguir una reserva que nadie pagó de una pagada, que es la
diferencia entre `expirada` y `cancelada`.

`retiene_fondos` existe para que [`Finanzas`][finanzas] no tenga que enumerar
estados. La liberación de la comisión se dispara al entrar en el único estado
terminal que venía de retener, y preguntarle al catálogo evita repartir la lista
de siete códigos por el código de dos módulos.

!!! warning "Umbral sin definir"

    El plazo para completar el pago antes de que la reserva pase a `expirada`
    **no está definido** en ninguna fuente del análisis. Es el parámetro que
    falta para cerrar esta máquina; cuando exista, su sitio es
    [`Parametro`][catalogos] y no una constante en el código.

---

## `transicion_reserva` y `transicion_convocatoria`

Instancias del patrón común descrito en [`Auditoría`][auditoria-modulo]: estado
de origen, estado de destino, responsable, motivo, nota e instante, en régimen
[de solo inserción][auditoria].

Dos particularidades de `transicion_reserva`:

- `usuario_id` es nulo cuando la transición la dispara el proceso programado: el
  paso a `en_curso` al llegar la fecha, la expiración por falta de pago y las
  cancelaciones automáticas por acreditación vencida o expulsión del prestador.
- El motivo es obligatorio al cancelar con menos de veinticuatro horas de
  antelación y opcional por encima de ese plazo, según la tabla de cancelación
  del [diagrama de estados de la reserva][estados-reserva]. Lo impone
  `trg_reserva_cancelacion_motivo`.

---

## Fuera de este módulo

|        Cosa         |          Dónde vive          |                          Por qué no aquí                           |
| :-----------------: | :--------------------------: | :----------------------------------------------------------------: |
|   `conversacion`    |  [`Mensajería`][mensajeria]  | Cuelga de la convocatoria o de la reserva, pero es su propio ciclo |
|      `resena`       |  [`Reputación`][reputacion]  |             La evaluación mutua que cierra el servicio             |
| `pago` y `comision` |    [`Finanzas`][finanzas]    |        El cobro y la retención, que la reserva solo dispara        |
|    `itinerario`     | [`Itinerarios`][itinerarios] |       Lo que el turista arma; la reserva solo lo referencia        |
| `perfil_prestador`  |    [`Perfiles`][perfiles]    |        Incluye el tipo de servicio que este módulo consulta        |

[agenda]: agenda.md
[auditoria]: ../convenciones.md#auditoria
[auditoria-modulo]: auditoria.md
[catalogos]: catalogos.md
[convenciones-invariantes]: ../convenciones.md#invariantes
[convenciones-nulabilidad]: ../convenciones.md#nulabilidad
[convenciones-reservadas]: ../convenciones.md#palabras-reservadas
[estados-reserva]: ../../diagramas/estados/reserva.md
[finanzas]: finanzas.md
[itinerarios]: itinerarios.md
[mensajeria]: mensajeria.md
[perfiles]: perfiles.md
[reputacion]: reputacion.md
[territorio]: territorio.md
[rf-p-08]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-08
[rf-p-09]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-09
[rf-p-10]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-10
[rf-p-11]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-11
[rf-p-12]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-12
[rf-p-13]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-13
[rf-p-14]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-14
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
[rf-t-15]: ../../requerimientos/funcionales/app-turista.md#rf-t-15
[rf-t-16]: ../../requerimientos/funcionales/app-turista.md#rf-t-16
[rf-t-17]: ../../requerimientos/funcionales/app-turista.md#rf-t-17
[rf-t-18]: ../../requerimientos/funcionales/app-turista.md#rf-t-18
[rf-t-26]: ../../requerimientos/funcionales/app-turista.md#rf-t-26
[rf-t-30]: ../../requerimientos/funcionales/app-turista.md#rf-t-30
