---
icon: lucide/route
---

# Itinerarios

Lo que un turista concreto se propone recorrer. Es la palabra que
[`Convenciones`][convenciones-reservadas] reserva frente a **recorrido**, que es
el producto que publica un guía.

Todo el módulo gira alrededor de una distinción: seguir un circuito oficial tal
como la alcaldía lo publicó no copia nada, y ajustarlo congela una copia propia
que ya no recibe correcciones. Es [`D-33`][d-33], y de ahí salen las dos cifras
que la alcaldía mide por separado.

## Requerimientos cubiertos

- [`RF-T-07`][rf-t-07]
- [`RF-T-08`][rf-t-08]
- [`RF-T-28`][rf-t-28]
- [`RF-A-10`][rf-a-10]

---

## `itinerario`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** varios por turista activo
- **Origen:**
  > - [`RF-T-07`][rf-t-07]
  > - [`RF-T-28`][rf-t-28]

### Columnas

|         Campo         |     Tipo      | Nulo | Predeterminado |             Descripción             |
| :-------------------: | :-----------: | :--: | :------------: | :---------------------------------: |
|  `perfil_turista_id`  |    `uuid`     |  no  |                |      Llave foránea `RESTRICT`       |
|      `estado_id`      |    `uuid`     |  no  |                | Llave foránea a `estado_itinerario` |
|       `titulo`        |   `varchar`   |  no  |                |                                     |
| `circuito_seguido_id` |    `uuid`     |  sí  |                |     El circuito vivo que se lee     |
|      `ajustado`       |   `boolean`   |  no  |    `false`     |     Bandera de un solo sentido      |
|      `creado_en`      | `timestamptz` |  no  |    `now()`     |                                     |
|     `iniciado_en`     | `timestamptz` |  sí  |                |      Nulo mientras no arranca       |
|    `completado_en`    | `timestamptz` |  sí  |                |                                     |
|    `eliminado_en`     | `timestamptz` |  sí  |                |       Baja lógica del turista       |

### Constraints

```postgresql
CONSTRAINT chk_itinerario_seguido_coherente
CHECK (ajustado OR circuito_seguido_id IS NOT NULL)

CONSTRAINT chk_itinerario_titulo_longitud
CHECK (length(titulo) >= 3)
```

### Triggers

|                 Nombre                 |             Evento              | Momento  | Nivel |                        Regla                         |        Origen        |
| :------------------------------------: | :-----------------------------: | :------: | :---: | :--------------------------------------------------: | :------------------: |
| `trg_itinerario_ajustado_irreversible` |      `UPDATE OF ajustado`       | `BEFORE` | `ROW` |      `ajustado` solo pasa de falso a verdadero       |    [`D-33`][d-33]    |
|  `trg_itinerario_sin_paradas_propias`  | `INSERT` en `itinerario_parada` | `BEFORE` | `ROW` |        Rechaza paradas si `ajustado` es falso        |    [`D-33`][d-33]    |
|      `trg_itinerario_dos_paradas`      |            `UPDATE`             | `BEFORE` | `ROW` | Un itinerario ajustado conserva al menos dos paradas | [`RF-T-07`][rf-t-07] |

### Índices

|          Nombre           |                            Definición                            |                Propósito                |
| :-----------------------: | :--------------------------------------------------------------: | :-------------------------------------: |
| `idx_itinerario_turista`  | `(perfil_turista_id, creado_en DESC) WHERE eliminado_en IS NULL` |        La colección del turista         |
| `idx_itinerario_metricas` |                `(circuito_seguido_id, ajustado)`                 | [Iniciaron contra modificaron][rf-a-10] |

### Notas de diseño

`circuito_seguido_id` y `ajustado` son las dos columnas que separan los cuatro
modos. Mientras `ajustado` es falso, el itinerario no tiene filas en
`itinerario_parada` y la aplicación lee las paradas del circuito referenciado. La
primera edición pone `ajustado` en verdadero, copia las paradas y suelta la
referencia viva: a partir de ahí el itinerario es independiente.

|                 Modo                  | Circuitos de origen |        Paradas propias        |
| :-----------------------------------: | :-----------------: | :---------------------------: |
|      Seguir el circuito tal cual      |         uno         | ninguna: se leen del circuito |
|          Ajustar un circuito          |         uno         |      sí, desde la copia       |
| Combinar circuitos de varias ciudades |       varios        |              sí               |
|           Armar desde cero            |       ninguno       |              sí               |

La transición ocurre una sola vez y no se revierte, y un trigger lo impone. Si
`ajustado` pudiera volver a falso, el itinerario recuperaría una referencia viva
a un circuito que quizá ya cambió, y las paradas copiadas quedarían huérfanas sin
que nadie lo note.

Las tres cifras que mide la alcaldía salen de aquí sin cálculos adicionales:
iniciaron son los itinerarios con `iniciado_en`, modificaron los que tienen
`ajustado` verdadero, y completaron los que tienen `completado_en`. Si ambos
casos copiaran las paradas, la corrección de una parada mal ubicada no alcanzaría
a nadie que ya hubiera empezado y las dos primeras cifras serían
indistinguibles.

`eliminado_en` existe porque borrar está bloqueado mientras haya una reserva viva
sobre el itinerario. La llave foránea desde `reserva` restringe, así que el
turista despeja su colección marcando la fila y el borrado físico ocurre cuando
el servicio concluye.

---

## `itinerario_parada`

Las paradas propias, que solo existen cuando el itinerario se apartó del
circuito.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** varias por itinerario ajustado
- **Origen:**
  > - [`RF-T-07`][rf-t-07]

### Columnas

|       Campo        |      Tipo      | Nulo | Predeterminado |          Descripción           |
| :----------------: | :------------: | :--: | :------------: | :----------------------------: |
|  `itinerario_id`   |     `uuid`     |  no  |                |    Llave foránea `CASCADE`     |
| `punto_interes_id` |     `uuid`     |  sí  |                | **Solo rastro** de dónde salió |
|      `nombre`      |   `varchar`    |  no  |                |       Copiado, no leído        |
|     `latitud`      | `numeric(9,6)` |  no  |                |       Copiada, no leída        |
|     `longitud`     | `numeric(9,6)` |  no  |                |                                |
|      `orden`       |   `smallint`   |  no  |                |                                |
|   `visitada_en`    | `timestamptz`  |  sí  |                |   Nulo mientras no se llega    |

### Llaves foráneas

|      Columna       |   Referencia    | `ON DELETE` |            Notas             |
| :----------------: | :-------------: | :---------: | :--------------------------: |
|  `itinerario_id`   |  `itinerario`   |  `CASCADE`  |                              |
| `punto_interes_id` | `punto_interes` | `SET NULL`  | La parada sobrevive al punto |

### Unicidad

|            Nombre            |             Definición             |                      Propósito                      |
| :--------------------------: | :--------------------------------: | :-------------------------------------------------: |
| `unq_itinerarioparada_orden` | `(itinerario_id, orden)`, diferida | Reordenar intercambia posiciones en una transacción |

### Notas de diseño

La parada guarda `nombre`, `latitud` y `longitud` propios, con
`punto_interes_id` nulable solo como rastro. Si esa referencia fuera la única
fuente, retirar un punto oficial dejaría un hueco en el itinerario que alguien
lleva abierto a mitad de recorrido. Es la aplicación directa de que lo ya
otorgado no se destruye, y el precio es una denormalización deliberada
([`D-16`][d-16]).

Por eso la llave anula en lugar de restringir: la parada ya tiene todo lo que
necesita para mostrarse, y perder la trazabilidad al punto original no la deja
inservible.

---

## `itinerario_circuito`

De qué circuitos se derivó el itinerario. Es una relación de varios a varios.

- **Régimen:** [Mutable rastreada][auditoria]
- **Origen:**
  > - [`RF-T-08`][rf-t-08]

### Columnas

|      Campo      |    Tipo    | Nulo | Predeterminado |       Descripción        |
| :-------------: | :--------: | :--: | :------------: | :----------------------: |
| `itinerario_id` |   `uuid`   |  no  |                | Llave foránea `CASCADE`  |
|  `circuito_id`  |   `uuid`   |  no  |                | Llave foránea `RESTRICT` |
|     `orden`     | `smallint` |  no  |      `0`       |                          |

### Unicidad

|            Nombre            |           Definición           |            Propósito            |
| :--------------------------: | :----------------------------: | :-----------------------------: |
| `unq_itinerariocircuito_par` | `(itinerario_id, circuito_id)` | Un circuito no aporta dos veces |

### Notas de diseño

[`RF-T-08`][rf-t-08] permite combinar circuitos de ciudades distintas, así que el
origen no es una llave simple sino esta tabla, por [`D-17`][d-17]. Una sola
referencia obligaría a elegir arbitrariamente un circuito «principal» y perdería
la trazabilidad del resto, que es lo que las métricas de la alcaldía necesitan
contar.

Convive con `circuito_seguido_id` sin duplicarlo: aquella dice qué circuito se
está leyendo en vivo, esta de cuáles se derivó el contenido. Un itinerario
ajustado tiene la primera en nulo y varias filas aquí.

---

## `estado_itinerario`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma dos: `admite_edicion` y `admite_reserva`.

|    Código     | `admite_edicion` | `admite_reserva` | `es_terminal` |
| :-----------: | :--------------: | :--------------: | :-----------: |
| `planificado` |      **sí**      |      **sí**      |      no       |
|  `en_curso`   |      **sí**      |        no        |      no       |
| `completado`  |        no        |        no        |      no       |
|  `eliminado`  |        no        |        no        |    **sí**     |

`en_curso` no tiene salida a `eliminado`: el turista no descarta un recorrido que
está haciendo. Tampoco la tiene si existe una reserva viva sobre él, porque la
llave foránea restringe; primero se cierra o cancela el servicio.

`ajustado` **no** es un estado. Es una bandera de un solo sentido sobre una
dimensión distinta: un itinerario puede estar ajustado en cualquiera de los
cuatro estados.

---

## Fuera de este módulo

|        Cosa         |         Dónde vive         |                       Por qué no aquí                        |
| :-----------------: | :------------------------: | :----------------------------------------------------------: |
| `circuito_oficial`  | [`Territorio`][territorio] | Lo publica la alcaldía; el itinerario solo lo lee o lo copia |
|   `punto_interes`   | [`Territorio`][territorio] |            La parada lo copia y guarda su rastro             |
|      `reserva`      |  [`Servicios`][servicios]  |     Se contrata sobre el itinerario, pero es otro ciclo      |
| `visita_acreditada` |  [`Insignias`][insignias]  |   `visitada_en` marca el paso; la insignia la otorga allí    |

[auditoria]: ../convenciones.md#auditoria
[convenciones-reservadas]: ../convenciones.md#palabras-reservadas
[d-16]: ../decisiones.md#d-16
[d-17]: ../decisiones.md#d-17
[d-33]: ../decisiones.md#d-33
[insignias]: insignias.md
[servicios]: servicios.md
[territorio]: territorio.md
[rf-a-10]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-10
[rf-t-07]: ../../requerimientos/funcionales/app-turista.md#rf-t-07
[rf-t-08]: ../../requerimientos/funcionales/app-turista.md#rf-t-08
[rf-t-28]: ../../requerimientos/funcionales/app-turista.md#rf-t-28
