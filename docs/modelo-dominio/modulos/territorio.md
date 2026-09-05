---
icon: lucide/map
---

# Territorio y circuitos

Las diez Ciudades Creativas, sus gobiernos locales, los lugares que las componen
y los recorridos que la alcaldía publica sobre ellos.

Dos separaciones gobiernan el módulo. La ciudad es territorio y la alcaldía es
autoridad: no son la misma entidad, y confundirlas insinuaría una potestad
municipal sobre negocios privados que ninguna fuente respalda. Y el punto de
interés existe por sí mismo, no como propiedad de un circuito, por
[`D-18`][d-18].

## Requerimientos cubiertos

- [`RF-A-01`][rf-a-01]
- [`RF-A-02`][rf-a-02]
- [`RF-A-05`][rf-a-05]
- [`RF-A-06`][rf-a-06]
- [`RF-T-29`][rf-t-29]

---

## `ciudad`

Una de las diez Ciudades Creativas de la Red Nacional. El catálogo está completo
desde el primer día.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 10 filas

### Columnas

|   Campo    |      Tipo      | Nulo | Predeterminado |                Descripción                |
| :--------: | :------------: | :--: | :------------: | :---------------------------------------: |
|  `codigo`  |   `varchar`    |  no  |                |                                           |
|  `nombre`  |   `varchar`    |  no  |                |                                           |
| `latitud`  | `numeric(9,6)` |  no  |                |       Centro para encuadrar el mapa       |
| `longitud` | `numeric(9,6)` |  no  |                |                                           |
|  `activa`  |   `boolean`    |  no  |    `false`     | Verdadero al incorporarse a la plataforma |

### Unicidad

|       Nombre        | Definición | Propósito |
| :-----------------: | :--------: | :-------: |
| `unq_ciudad_codigo` | `(codigo)` |           |

### Notas de diseño

`activa` existe porque el catálogo está completo pero la incorporación es
progresiva y despareja. Una ciudad sin alcaldía dada de alta no tiene circuitos
oficiales y aun así puede albergar comercios y puntos de interés.

---

## `alcaldia`

El gobierno local, dado de alta en la plataforma. Es la única autoridad que
publica contenido oficial.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** hasta 10 filas
- **Origen:**
  > - [`RF-A-01`][rf-a-01]

### Columnas

|       Campo       |     Tipo      | Nulo | Predeterminado |              Descripción              |
| :---------------: | :-----------: | :--: | :------------: | :-----------------------------------: |
|    `ciudad_id`    |    `uuid`     |  no  |                |  Llave foránea `RESTRICT`, **única**  |
|     `nombre`      |   `varchar`   |  no  |                |                                       |
| `correo_contacto` |   `citext`    |  no  |                |                                       |
|    `telefono`     |   `varchar`   |  no  |                |                                       |
| `dada_de_alta_en` | `timestamptz` |  no  |    `now()`     |                                       |
|  `verificado_en`  | `timestamptz` |  sí  |                | Nulo mientras el moderador no aprueba |

### Unicidad

|        Nombre         |  Definición   |          Propósito           |
| :-------------------: | :-----------: | :--------------------------: |
| `unq_alcaldia_ciudad` | `(ciudad_id)` | Una sola alcaldía por ciudad |

### Notas de diseño

La relación con la ciudad es de cero o uno, y esa unicidad es lo que la impone.
No es un descuido: es la incorporación progresiva.

Igual que las organizaciones, la alcaldía no tiene máquina de estados. Su
visibilidad es consecuencia de la verificación que corre en
[`Moderación`][moderacion], y `verificado_en` nulo es el registro que aún no
opera.

---

## `punto_interes`

Un lugar concreto del territorio, con su ubicación. Existe aunque ningún circuito
lo incluya.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** cientos por ciudad
- **Origen:**
  > - [`RF-A-02`][rf-a-02]

### Columnas

|     Campo     |      Tipo      | Nulo | Predeterminado |             Descripción             |
| :-----------: | :------------: | :--: | :------------: | :---------------------------------: |
|  `ciudad_id`  |     `uuid`     |  no  |                |      Llave foránea `RESTRICT`       |
|   `nombre`    |   `varchar`    |  no  |                |                                     |
| `descripcion` |     `text`     |  no  |      `''`      |                                     |
|   `latitud`   | `numeric(9,6)` |  no  |                |                                     |
|  `longitud`   | `numeric(9,6)` |  no  |                |                                     |
|   `activo`    |   `boolean`    |  no  |     `true`     | Retirarlo no borra lo que ya otorgó |
|  `creado_en`  | `timestamptz`  |  no  |    `now()`     |                                     |

### Constraints

```postgresql
CONSTRAINT chk_puntointeres_latitud_rango
CHECK (latitud BETWEEN 10.7 AND 15.1)

CONSTRAINT chk_puntointeres_longitud_rango
CHECK (longitud BETWEEN -87.7 AND -82.6)
```

### Índices

|          Nombre           |         Definición         |              Propósito               |
| :-----------------------: | :------------------------: | :----------------------------------: |
| `idx_puntointeres_ciudad` | `(ciudad_id) WHERE activo` |        El mapa de una ciudad         |
| `idx_puntointeres_punto`  |   `(latitud, longitud)`    | Acotar el rectángulo antes del radio |

### Notas de diseño

Las coordenadas son dos columnas decimales con escala fija y rango verificado, no
un tipo geográfico nativo. Es la opción que funciona sin extensiones instaladas;
si el motor de producción las tiene, la columna cambia de tipo y las búsquedas
por radio dejan de aproximarse sobre un rectángulo.

El punto es compartido y sobrevive al circuito. Un mismo lugar aparece en varios
circuitos y otorga insignias por sí mismo, así que existe como entidad del
territorio: retirarlo de un circuito no lo borra del mapa ni cancela lo que ya
acreditó.

---

## `circuito_oficial` y `circuito_parada`

El recorrido que la alcaldía publica y respalda: una secuencia ordenada de puntos
de su ciudad.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** decenas por ciudad
- **Origen:**
  > - [`RF-A-01`][rf-a-01]
  > - [`RF-A-05`][rf-a-05]
  > - [`RF-A-06`][rf-a-06]

### Columnas de `circuito_oficial`

|       Campo       |     Tipo      | Nulo | Predeterminado |            Descripción            |
| :---------------: | :-----------: | :--: | :------------: | :-------------------------------: |
|   `alcaldia_id`   |    `uuid`     |  no  |                |     Llave foránea `RESTRICT`      |
|    `estado_id`    |    `uuid`     |  no  |                | Llave foránea a `estado_circuito` |
|     `titulo`      |   `varchar`   |  no  |                |                                   |
|   `descripcion`   |    `text`     |  no  |      `''`      |                                   |
| `foto_portada_id` |    `uuid`     |  sí  |                |     Llave foránea `SET NULL`      |
|     `version`     |   `integer`   |  no  |      `1`       | Sube solo al cambiar la geometría |
|  `publicado_en`   | `timestamptz` |  sí  |                |     Nulo mientras es borrador     |

### Columnas de `circuito_parada`

|       Campo        |    Tipo    | Nulo | Predeterminado |             Descripción              |
| :----------------: | :--------: | :--: | :------------: | :----------------------------------: |
|   `circuito_id`    |   `uuid`   |  no  |                |       Llave foránea `CASCADE`        |
| `punto_interes_id` |   `uuid`   |  no  |                |       Llave foránea `RESTRICT`       |
|      `orden`       | `smallint` |  no  |                |                                      |
|    `indicacion`    |   `text`   |  no  |      `''`      | Cómo llegar desde la parada anterior |

### Unicidad

|           Nombre           |            Definición             |                       Propósito                       |
| :------------------------: | :-------------------------------: | :---------------------------------------------------: |
| `unq_circuitoparada_orden` | `(circuito_id, orden)`, diferida  |  Reordenar intercambia posiciones en una transacción  |
| `unq_circuitoparada_punto` | `(circuito_id, punto_interes_id)` | Un lugar no se visita dos veces en el mismo recorrido |

### Triggers

|           Nombre           |                           Evento                           | Momento  | Nivel |                       Regla                       |        Origen        |
| :------------------------: | :--------------------------------------------------------: | :------: | :---: | :-----------------------------------------------: | :------------------: |
|   `trg_circuito_version`   | `INSERT`, `DELETE`, `UPDATE OF orden` en `circuito_parada` | `AFTER`  | `ROW` |         Incrementa `version` del circuito         | [`RF-A-06`][rf-a-06] |
| `trg_circuito_dos_paradas` |                   `UPDATE OF estado_id`                    | `BEFORE` | `ROW` | Un circuito visible conserva al menos dos paradas | [`RF-A-05`][rf-a-05] |
|  `trg_circuito_historial`  |                   `UPDATE OF estado_id`                    | `AFTER`  | `ROW` |     Inserta la fila en `transicion_circuito`      | [`RF-S-10`][rf-s-10] |

### Notas de diseño

`version` sube cuando cambia la geometría y solo entonces.
Editar el título no lo mueve, porque la aplicación usa ese número
para decidir si debe redibujar el trazado, y una corrección de
ortografía no debería obligar a redescargarlo.

La unicidad del orden es diferida. Reordenar intercambia posiciones dentro de una
transacción y con una restricción inmediata el primer `UPDATE` chocaría contra el
valor que el segundo va a liberar.

Un recorrido de un punto no se puede trazar, y por eso el mínimo de dos paradas
es un trigger sobre la publicación y no un `CHECK`: la regla cruza filas.

Borrar un circuito restringe si tiene itinerarios que lo siguen. Hay que
despublicarlo primero, que es una decisión explícita y no un efecto colateral.

---

## `estado_circuito`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma dos: `es_visible` y `admite_edicion`.

|     Código     | `es_visible` | `admite_edicion` | `es_terminal` |
| :------------: | :----------: | :--------------: | :-----------: |
|   `borrador`   |      no      |      **sí**      |      no       |
|  `publicado`   |    **sí**    |      **sí**      |      no       |
| `despublicado` |      no      |      **sí**      |      no       |
|   `retirado`   |      no      |        no        |    **sí**     |

---

## `punto_pilar` y `foto`

La clasificación cultural del punto y las imágenes de todo el módulo.

- **Régimen:** [Mutable rastreada][auditoria]
- **Origen:**
  > - [`RF-T-29`][rf-t-29]
  > - [`RF-S-12`][rf-s-12]

### Columnas de `foto`

|        Campo        |    Tipo    | Nulo | Predeterminado |           Descripción           |
| :-----------------: | :--------: | :--: | :------------: | :-----------------------------: |
| `punto_interes_id`  |   `uuid`   |  sí  |                |             Dueño A             |
|    `circuito_id`    |   `uuid`   |  sí  |                |             Dueño B             |
|    `comercio_id`    |   `uuid`   |  sí  |                |             Dueño C             |
|     `evento_id`     |   `uuid`   |  sí  |                |             Dueño D             |
|    `archivo_id`     | `varchar`  |  no  |                | Referencia en el almacenamiento |
| `texto_alternativo` | `varchar`  |  no  |      `''`      |                                 |
|       `orden`       | `smallint` |  no  |      `0`       |                                 |

### Constraints

```postgresql
CONSTRAINT chk_foto_dueno_excluyente
CHECK (
  num_nonnulls(punto_interes_id, circuito_id, comercio_id, evento_id) = 1
)
```

### Unicidad

|        Nombre        |               Definición                |                   Propósito                    |
| :------------------: | :-------------------------------------: | :--------------------------------------------: |
| `unq_puntopilar_par` | `(punto_interes_id, pilar_cultural_id)` | Un pilar no se asigna dos veces al mismo lugar |

### Notas de diseño

`foto` usa el mismo patrón de referencias excluyentes que el ámbito de un rol:
cuatro llaves nulables y una verificación que exige exactamente una presente. Una
tabla de fotos por dueño habría duplicado cuatro veces las mismas columnas.

`punto_pilar` es una tabla y no una columna porque un punto pertenece a más de un
pilar: una casona colonial que además es taller de artesanía aparece en los dos
filtros de [`RF-T-29`][rf-t-29].

---

## Fuera de este módulo

|         Cosa         |             Dónde vive             |                  Por qué no aquí                  |
| :------------------: | :--------------------------------: | :-----------------------------------------------: |
|     `itinerario`     |    [`Itinerarios`][itinerarios]    |   Lo que el turista arma sobre estos circuitos    |
|      `comercio`      | [`Organizaciones`][organizaciones] | Está situado en la ciudad, pero nadie lo gobierna |
| `insignia` del punto |      [`Insignias`][insignias]      | El punto la otorga; el circuito de canje es otro  |
|   `pilar_cultural`   |      [`Catálogos`][catalogos]      |  La lista es de allí; la clasificación, de aquí   |

[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[d-18]: ../decisiones.md#d-18
[insignias]: insignias.md
[itinerarios]: itinerarios.md
[moderacion]: moderacion.md
[organizaciones]: organizaciones.md
[rf-a-01]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-01
[rf-a-02]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-02
[rf-a-05]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-05
[rf-a-06]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-06
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
[rf-s-12]: ../../requerimientos/funcionales/plataforma.md#rf-s-12
[rf-t-29]: ../../requerimientos/funcionales/app-turista.md#rf-t-29
