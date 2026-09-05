---
icon: lucide/award
---

# Insignias y cupones

El circuito de recompensa: el turista explora, acredita visitas, acumula
insignias y las canjea por cupones que consume en los comercios aliados. Es el
mecanismo por el que un negocio que no puede pagar visibilidad accede a ella
entregando beneficio.

Dos decisiones gobiernan el módulo. El saldo no es una columna sino la suma de un
libro de movimientos, por [`D-24`][d-24]; y el cupón copia su beneficio en lugar
de leerlo de la campaña, por [`D-25`][d-25].

## Requerimientos cubiertos

- [`RF-S-15`][rf-s-15]
- [`RF-C-06`][rf-c-06]
- [`RF-C-08`][rf-c-08]
- [`RF-C-09`][rf-c-09]
- [`RF-C-10`][rf-c-10]
- [`RF-T-19`][rf-t-19]
- [`RF-T-20`][rf-t-20]
- [`RF-T-21`][rf-t-21]
- [`RF-T-22`][rf-t-22]

---

## `insignia`

Lo que otorga un lugar al ser visitado. Cuelga de un punto de interés o de un
comercio, con dos llaves excluyentes.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** una por punto o comercio que la ofrezca
- **Origen:**
  > - [`RF-S-15`][rf-s-15]

### Columnas

|       Campo        |    Tipo    | Nulo | Predeterminado |            Descripción             |
| :----------------: | :--------: | :--: | :------------: | :--------------------------------: |
| `punto_interes_id` |   `uuid`   |  sí  |                |  Dueño A, excluyente con el otro   |
|   `comercio_id`    |   `uuid`   |  sí  |                |  Dueño B, excluyente con el otro   |
|      `nombre`      | `varchar`  |  no  |                |                                    |
|   `descripcion`    |   `text`   |  no  |      `''`      |                                    |
|      `icono`       | `varchar`  |  no  |      `''`      |                                    |
|      `valor`       | `smallint` |  no  |      `1`       | Cuántas insignias otorga la visita |
|      `activa`      | `boolean`  |  no  |     `true`     |   Deja de otorgarse sin borrarse   |

### Constraints

```postgresql
CONSTRAINT chk_insignia_dueno_excluyente
CHECK (num_nonnulls(punto_interes_id, comercio_id) = 1)

CONSTRAINT chk_insignia_valor_positivo
CHECK (valor > 0)
```

### Unicidad

|         Nombre          |                       Definición                        |         Propósito         |
| :---------------------: | :-----------------------------------------------------: | :-----------------------: |
|  `unq_insignia_punto`   | `(punto_interes_id) WHERE punto_interes_id IS NOT NULL` |  Una insignia por lugar   |
| `unq_insignia_comercio` |      `(comercio_id) WHERE comercio_id IS NOT NULL`      | Una insignia por comercio |

### Notas de diseño

Es el mismo patrón de referencias excluyentes que `foto` en
[`Territorio`][territorio]: dos llaves nulables y un `CHECK` que exige
exactamente una. Una tabla por tipo de dueño habría duplicado las mismas cinco
columnas para distinguir dos casos que se comportan igual.

`activa` en lugar de borrado. Desactivar una insignia corta las visitas futuras y
no toca las ya acreditadas, que es lo que exige que la visita sea un hecho
inmutable.

---

## `visita_acreditada`

El hecho de que un turista estuvo a menos de cincuenta metros de un lugar. No se
corrige ni se borra.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** millones al año
- **Origen:**
  > - [`RF-S-15`][rf-s-15]

### Columnas

|        Campo        |      Tipo      | Nulo | Predeterminado |               Descripción               |
| :-----------------: | :------------: | :--: | :------------: | :-------------------------------------: |
| `perfil_turista_id` |     `uuid`     |  no  |                |        Llave foránea `RESTRICT`         |
|    `insignia_id`    |     `uuid`     |  no  |                |        Llave foránea `RESTRICT`         |
|      `latitud`      | `numeric(9,6)` |  no  |                |       Dónde estaba el dispositivo       |
|     `longitud`      | `numeric(9,6)` |  no  |                |                                         |
| `distancia_metros`  |   `smallint`   |  no  |                | La medida que justificó la acreditación |
|   `acreditada_en`   | `timestamptz`  |  no  |    `now()`     |                                         |

### Constraints

```postgresql
CONSTRAINT chk_visitaacreditada_distancia
CHECK (distancia_metros BETWEEN 0 AND 50)

CONSTRAINT chk_visitaacreditada_latitud_rango
CHECK (latitud BETWEEN 10.7 AND 15.1)

CONSTRAINT chk_visitaacreditada_longitud_rango
CHECK (longitud BETWEEN -87.7 AND -82.6)
```

### Triggers

|             Nombre             |  Evento  | Momento  | Nivel |                      Regla                       |        Origen        |
| :----------------------------: | :------: | :------: | :---: | :----------------------------------------------: | :------------------: |
| `trg_visitaacreditada_ventana` | `INSERT` | `BEFORE` | `ROW` | Rechaza si hay otra visita del mismo par en 24 h | [`RF-S-15`][rf-s-15] |
|  `trg_visitaacreditada_abona`  | `INSERT` | `AFTER`  | `ROW` | Inserta el `movimiento_insignia` correspondiente | [`RF-S-15`][rf-s-15] |

### Índices

|             Nombre             |                       Definición                       |              Propósito               |
| :----------------------------: | :----------------------------------------------------: | :----------------------------------: |
| `idx_visitaacreditada_ventana` | `(perfil_turista_id, insignia_id, acreditada_en DESC)` |     Resolver la ventana de 24 h      |
| `brin_visitaacreditada_fecha`  |                 `BRIN (acreditada_en)`                 | Métricas por periodo recorren rangos |

### Notas de diseño

La regla de una visita cada veinticuatro horas es un trigger y no un `EXCLUDE`.
No es un solapamiento de rangos sino una distancia mínima entre dos instantes del
mismo par turista-insignia, y eso no se expresa como operador de exclusión. El
índice compuesto hace que la comprobación lea una sola fila: la última.

`distancia_metros` se guarda aunque el `CHECK` ya la acote. Es la evidencia de
por qué se acreditó: si alguien disputa una insignia, la fila responde a qué
distancia estaba el dispositivo y no solo que estaba cerca.

La visita es inmutable porque justifica el movimiento que la acompaña. Corregirla
dejaría un abono sin causa, y el saldo dejaría de ser explicable movimiento por
movimiento.

---

## `movimiento_insignia`

El libro del saldo del turista. Cada fila tiene signo, motivo y origen.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** millones al año
- **Origen:**
  > - [`RF-T-19`][rf-t-19]
  > - [`RF-T-21`][rf-t-21]

### Columnas

|        Campo        |     Tipo      | Nulo | Predeterminado |              Descripción               |
| :-----------------: | :-----------: | :--: | :------------: | :------------------------------------: |
| `perfil_turista_id` |    `uuid`     |  no  |                |        Llave foránea `RESTRICT`        |
|     `cantidad`      |  `smallint`   |  no  |                | Positiva al abonar, negativa al cargar |
|     `visita_id`     |    `uuid`     |  sí  |                |    Origen A, excluyente con el otro    |
|     `cupon_id`      |    `uuid`     |  sí  |                |    Origen B, excluyente con el otro    |
|   `registrado_en`   | `timestamptz` |  no  |    `now()`     |                                        |

### Constraints

```postgresql
CONSTRAINT chk_movimientoinsignia_origen_excluyente
CHECK (num_nonnulls(visita_id, cupon_id) = 1)

CONSTRAINT chk_movimientoinsignia_signo_coherente
CHECK (
  (visita_id IS NOT NULL AND cantidad > 0)
  OR
  (cupon_id IS NOT NULL AND cantidad < 0)
)
```

### Unicidad

|             Nombre              |                Definición                 |           Propósito           |
| :-----------------------------: | :---------------------------------------: | :---------------------------: |
| `unq_movimientoinsignia_visita` | `(visita_id) WHERE visita_id IS NOT NULL` | Una visita abona una sola vez |
| `unq_movimientoinsignia_cupon`  |  `(cupon_id) WHERE cupon_id IS NOT NULL`  |  Un canje carga una sola vez  |

### Triggers

|                  Nombre                   |  Evento  | Momento  | Nivel |                 Regla                 |        Origen        |
| :---------------------------------------: | :------: | :------: | :---: | :-----------------------------------: | :------------------: |
| `trg_movimientoinsignia_saldo_suficiente` | `INSERT` | `BEFORE` | `ROW` | El saldo resultante no queda negativo | [`RF-T-21`][rf-t-21] |

### Índices

|             Nombre             |                Definición                 |            Propósito            |
| :----------------------------: | :---------------------------------------: | :-----------------------------: |
| `idx_movimientoinsignia_saldo` | `(perfil_turista_id, registrado_en DESC)` | [Saldo y su historial][rf-t-19] |

### Notas de diseño

El saldo es la suma de esta tabla y no una columna del perfil, por
[`D-24`][d-24]. Con una columna, dos canjes simultáneos del mismo turista podrían
leer el mismo valor, ambos superar la comprobación de suficiencia y dejar el
saldo en negativo. Con el libro, el segundo ve el movimiento del primero.

El signo lo ata el `CHECK` al origen: una visita solo abona y un cupón solo
carga. Sin esa restricción, un error de signo convertiría un canje en un regalo
de insignias y nada en el esquema lo impediría.

El trigger de suficiencia es lo que hace que [`RF-T-21`][rf-t-21] sea una
garantía y no una aspiración. La regla cruza filas —hay que sumar el libro— y por
[`Convenciones`][convenciones-invariantes] esa forma corresponde a un disparador,
no a un `CHECK`.

---

## `campania_cupon`

La promoción que publica un comercio: qué beneficio, cuántos cupones y a qué
costo en insignias.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** unas pocas por comercio
- **Origen:**
  > - [`RF-C-06`][rf-c-06]
  > - [`RF-C-08`][rf-c-08]

### Columnas

|        Campo        |      Tipo       | Nulo | Predeterminado |            Descripción             |
| :-----------------: | :-------------: | :--: | :------------: | :--------------------------------: |
|    `comercio_id`    |     `uuid`      |  no  |                |      Llave foránea `RESTRICT`      |
| `tipo_beneficio_id` |     `uuid`      |  no  |                |      Llave foránea `RESTRICT`      |
|     `estado_id`     |     `uuid`      |  no  |                | Llave foránea a `estado_campania`  |
|      `titulo`       |    `varchar`    |  no  |                |                                    |
|    `descripcion`    |     `text`      |  no  |      `''`      |                                    |
|  `monto_beneficio`  | `numeric(12,2)` |  sí  |                |   Nulo si el tipo no exige monto   |
|     `moneda_id`     |     `uuid`      |  sí  |                | Nulo si el beneficio es porcentual |
|  `costo_insignias`  |   `smallint`    |  no  |                |           Mayor que cero           |
|    `stock_total`    |    `integer`    |  no  |                |           Mayor que cero           |
|  `stock_entregado`  |    `integer`    |  no  |      `0`       |        Cuántos se canjearon        |
|     `expira_en`     |  `timestamptz`  |  no  |                |       Fecha límite original        |
|    `retirada_en`    |  `timestamptz`  |  sí  |                |    Nulo salvo retiro anticipado    |

### Constraints

```postgresql
CONSTRAINT chk_campaniacupon_costo_positivo
CHECK (costo_insignias > 0)

CONSTRAINT chk_campaniacupon_stock_positivo
CHECK (stock_total > 0)

CONSTRAINT chk_campaniacupon_stock_coherente
CHECK (stock_entregado BETWEEN 0 AND stock_total)

CONSTRAINT chk_campaniacupon_monto_coherente
CHECK (num_nonnulls(monto_beneficio, moneda_id) IN (0, 2))
```

### Triggers

|              Nombre               |           Evento            | Momento  | Nivel |                          Regla                           |        Origen        |
| :-------------------------------: | :-------------------------: | :------: | :---: | :------------------------------------------------------: | :------------------: |
| `trg_campaniacupon_monto_exigido` |     `INSERT`, `UPDATE`      | `BEFORE` | `ROW` | Exige `monto_beneficio` si el tipo declara `exige_monto` | [`RF-C-06`][rf-c-06] |
|     `trg_campaniacupon_agota`     | `UPDATE OF stock_entregado` | `AFTER`  | `ROW` |        Pasa a `agotada` al alcanzar `stock_total`        | [`RF-C-09`][rf-c-09] |

### Índices

|            Nombre            |           Definición            |            Propósito             |
| :--------------------------: | :-----------------------------: | :------------------------------: |
|  `idx_campaniacupon_tienda`  |    `(estado_id, expira_en)`     | [Tienda de recompensas][rf-t-20] |
| `idx_campaniacupon_comercio` | `(comercio_id, expira_en DESC)` | [Métricas por campaña][rf-c-09]  |

### Notas de diseño

`stock_entregado` es un contador denormalizado con `CHECK` de coherencia, no una
agregación sobre `cupon`. La tienda consulta la disponibilidad en cada carga, y
`stock_entregado <= stock_total` combinado con el incremento dentro de la misma
transacción que crea el cupón convierte la sobreemisión en un error de
transacción, sin ventana de carrera entre leer y escribir.

El estado y `retirada_en` conviven porque responden cosas distintas: el estado
dice si admite canje —y lo comparten agotada, retirada y expirada—, mientras que
`retirada_en` dice cuándo el comercio cortó la emisión, que es el dato que
[`RF-C-08`][rf-c-08] necesita para distinguir un retiro de un agotamiento.

`monto_beneficio` y `moneda_id` van juntos o ninguno. Un descuento porcentual no
tiene moneda y un monto fijo sin moneda no significa nada; el `CHECK` con
`num_nonnulls` impide las dos combinaciones incoherentes de una vez.

---

## `estado_campania`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma una: `admite_canje`.

|   Código   | `admite_canje` | `es_terminal` |
| :--------: | :------------: | :-----------: |
|  `activa`  |     **sí**     |      no       |
| `agotada`  |       no       |    **sí**     |
| `retirada` |       no       |    **sí**     |
| `expirada` |       no       |    **sí**     |

---

## `cupon`

El código concreto que obtuvo un turista. Copia su beneficio en lugar de leerlo.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** decenas de miles al año
- **Origen:**
  > - [`RF-T-21`][rf-t-21]
  > - [`RF-T-22`][rf-t-22]
  > - [`RF-C-10`][rf-c-10]

### Columnas

|        Campo        |      Tipo       | Nulo | Predeterminado |              Descripción              |
| :-----------------: | :-------------: | :--: | :------------: | :-----------------------------------: |
|    `campania_id`    |     `uuid`      |  no  |                |       Llave foránea `RESTRICT`        |
| `perfil_turista_id` |     `uuid`      |  no  |                |       Llave foránea `RESTRICT`        |
|    `comercio_id`    |     `uuid`      |  no  |                |       **Copiado** de la campaña       |
|     `estado_id`     |     `uuid`      |  no  |                |    Llave foránea a `estado_cupon`     |
|      `codigo`       |    `varchar`    |  no  |                |       Ocho caracteres, legible        |
| `tipo_beneficio_id` |     `uuid`      |  no  |                |       **Copiado** de la campaña       |
|  `monto_beneficio`  | `numeric(12,2)` |  sí  |                |       **Copiado** de la campaña       |
|     `moneda_id`     |     `uuid`      |  sí  |                |       **Copiado** de la campaña       |
|  `costo_insignias`  |   `smallint`    |  no  |                |       **Copiado**: lo que costó       |
|     `expira_en`     |  `timestamptz`  |  no  |                | **Copiada**: la fecha límite original |
|    `canjeado_en`    |  `timestamptz`  |  no  |    `now()`     |                                       |
|   `consumido_en`    |  `timestamptz`  |  sí  |                |      Nulo mientras no se valida       |
|   `consumido_por`   |     `uuid`      |  sí  |                |  Qué usuario del comercio lo validó   |

### Constraints

```postgresql
CONSTRAINT chk_cupon_codigo_formato
CHECK (codigo ~ '^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$')

CONSTRAINT chk_cupon_consumo_completo
CHECK (num_nonnulls(consumido_en, consumido_por) IN (0, 2))

CONSTRAINT chk_cupon_consumo_coherente
CHECK (
  consumido_en IS NULL
  OR
  consumido_en >= canjeado_en
)
```

### Unicidad

|       Nombre       | Definición |                 Propósito                 |
| :----------------: | :--------: | :---------------------------------------: |
| `unq_cupon_codigo` | `(codigo)` | El código no se repite en todo el sistema |

### Triggers

|             Nombre             |          Evento          | Momento  | Nivel |                           Regla                            |        Origen        |
| :----------------------------: | :----------------------: | :------: | :---: | :--------------------------------------------------------: | :------------------: |
| `trg_cupon_readonly_beneficio` |         `UPDATE`         | `BEFORE` | `ROW` | Beneficio, comercio, costo y fecha límite no se reescriben | [`RF-C-08`][rf-c-08] |
|  `trg_cupon_valida_comercio`   | `UPDATE OF consumido_en` | `BEFORE` | `ROW` |     Quien valida pertenece al `comercio_id` del cupón      | [`RF-C-10`][rf-c-10] |
|      `trg_cupon_norevive`      | `UPDATE OF consumido_en` | `BEFORE` | `ROW` |              `consumido_en` no vuelve a nulo               | [`RF-C-10`][rf-c-10] |

### Índices

|         Nombre         |                   Definición                   |               Propósito                |
| :--------------------: | :--------------------------------------------: | :------------------------------------: |
| `idx_cupon_billetera`  |     `(perfil_turista_id, expira_en DESC)`      |        La billetera del turista        |
| `idx_cupon_validacion` |            `(comercio_id, codigo)`             |   [Validación en mostrador][rf-c-10]   |
|  `idx_cupon_campania`  | `(campania_id) WHERE consumido_en IS NOT NULL` | [Obtenidos contra consumidos][rf-c-09] |

### Notas de diseño

Siete columnas están copiadas de la campaña y un trigger las congela. Es
[`D-25`][d-25]: [`RF-C-08`][rf-c-08] permite al comercio retirar una campaña sin
invalidar los cupones ya entregados, y [`RF-T-22`][rf-t-22] conserva la validez
hasta la fecha límite original. Si el cupón leyera el beneficio de la campaña,
retirarla cambiaría el valor de lo ya entregado.

El código se guarda legible y no cifrado, por [`D-26`][d-26]. El turista debe
poder verlo en su billetera y dictarlo en el mostrador, así que el sistema tiene
que poder mostrarlo. El riesgo se acota por otra vía: un solo uso, vigencia
acotada y pertenencia a un único comercio, de modo que un código filtrado no vale
nada fuera de su contexto.

El alfabeto del `CHECK` excluye `I`, `O`, `0` y `1`. Se dictan en voz alta frente
al cliente y en segundos, y esas cuatro son las que se confunden entre sí.

El canje y el cargo son inseparables. [`RF-T-21`][rf-t-21] lo exige de forma
explícita: no existe un estado en el que se haya cobrado el saldo sin entregar el
código. Insertar el cupón y su `movimiento_insignia` ocurre en la misma
transacción, y `unq_movimientoinsignia_cupon` impide que un reintento cobre dos
veces.

---

## `estado_cupon`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 3 filas

A las cinco columnas comunes suma una: `admite_validacion`.

|   Código    | `admite_validacion` | `es_terminal` |
| :---------: | :-----------------: | :-----------: |
|  `vigente`  |       **sí**        |      no       |
| `consumido` |         no          |    **sí**     |
| `expirado`  |         no          |    **sí**     |

Retirar la campaña no toca al cupón: por eso `estado_cupon` no tiene un código
`retirado`. La campaña se retira, el cupón sigue vigente hasta su fecha límite.

---

## Fuera de este módulo

|        Cosa         |             Dónde vive             |                Por qué no aquí                |
| :-----------------: | :--------------------------------: | :-------------------------------------------: |
|     `comercio`      | [`Organizaciones`][organizaciones] |    Emite campañas, pero es la organización    |
|   `punto_interes`   |     [`Territorio`][territorio]     |   Otorga insignias, pero es del territorio    |
| `nivel_exploracion` |       [`Perfiles`][perfiles]       | Se deriva del saldo, pero vive con el turista |
|  `tipo_beneficio`   |      [`Catálogos`][catalogos]      |        Lista cerrada con `exige_monto`        |
|     `geocerca`      | [`Notificaciones`][notificaciones] | La proximidad que avisa no es la que acredita |

[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[convenciones-invariantes]: ../convenciones.md#invariantes
[d-24]: ../decisiones.md#d-24
[d-25]: ../decisiones.md#d-25
[d-26]: ../decisiones.md#d-26
[notificaciones]: notificaciones.md
[organizaciones]: organizaciones.md
[perfiles]: perfiles.md
[territorio]: territorio.md
[rf-c-06]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-06
[rf-c-08]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-08
[rf-c-09]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-09
[rf-c-10]: ../../requerimientos/funcionales/portal-comercios.md#rf-c-10
[rf-s-15]: ../../requerimientos/funcionales/plataforma.md#rf-s-15
[rf-t-19]: ../../requerimientos/funcionales/app-turista.md#rf-t-19
[rf-t-20]: ../../requerimientos/funcionales/app-turista.md#rf-t-20
[rf-t-21]: ../../requerimientos/funcionales/app-turista.md#rf-t-21
[rf-t-22]: ../../requerimientos/funcionales/app-turista.md#rf-t-22
