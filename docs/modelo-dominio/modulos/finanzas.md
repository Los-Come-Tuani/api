---
icon: lucide/wallet
---

# Finanzas

El dinero del servicio: qué cobró el turista, cuánto retuvo la plataforma, qué
saldo le queda al prestador y cómo lo retira. El módulo se apoya en el mismo
principio que las insignias —el saldo es un libro de movimientos y no una
columna, por [`D-24`][d-24]— y en que todo importe se guarda con la cifra que se
usó, no con la vigente al consultarlo.

Es el módulo con más huecos del análisis. El momento en que se captura el pago y
el porcentaje de comisión no están definidos en ninguna fuente, y ambos quedan
señalados donde corresponde.

## Requerimientos cubiertos

- [`RF-P-07`][rf-p-07]
- [`RF-P-16`][rf-p-16]
- [`RF-P-17`][rf-p-17]
- [`RF-P-18`][rf-p-18]
- [`RF-T-27`][rf-t-27]

---

## `pago`

Lo que el turista pagó por una reserva.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** uno por reserva cobrada
- **Origen:**
  > - [`RF-T-27`][rf-t-27]

### Columnas

|         Campo         |      Tipo       | Nulo | Predeterminado |              Descripción              |
| :-------------------: | :-------------: | :--: | :------------: | :-----------------------------------: |
|     `reserva_id`      |     `uuid`      |  no  |                |       Llave foránea `RESTRICT`        |
|     `monto_bruto`     | `numeric(12,2)` |  no  |                |      Lo que se cobró al turista       |
|      `moneda_id`      |     `uuid`      |  no  |                |  Llave foránea `RESTRICT` a `moneda`  |
| `referencia_pasarela` |    `varchar`    |  no  |                |    Identificador externo del cobro    |
|    `capturado_en`     |  `timestamptz`  |  sí  |                | Nulo mientras la pasarela no confirma |
|   `reembolsado_en`    |  `timestamptz`  |  sí  |                |        Nulo salvo cancelación         |
|      `creado_en`      |  `timestamptz`  |  no  |    `now()`     |                                       |

### Constraints

```postgresql
CONSTRAINT chk_pago_monto_positivo
CHECK (monto_bruto > 0)

CONSTRAINT chk_pago_reembolso_coherente
CHECK (
  reembolsado_en IS NULL
  OR
  capturado_en IS NOT NULL
)
```

### Unicidad

|        Nombre         |       Definición        |                 Propósito                 |
| :-------------------: | :---------------------: | :---------------------------------------: |
|  `unq_pago_reserva`   |     `(reserva_id)`      |     Una reserva se cobra una sola vez     |
| `unq_pago_referencia` | `(referencia_pasarela)` | Un cobro externo no se registra dos veces |

### Triggers

|          Nombre           |  Evento  | Momento  | Nivel |                    Regla                    |        Origen        |
| :-----------------------: | :------: | :------: | :---: | :-----------------------------------------: | :------------------: |
| `trg_pago_readonly_monto` | `UPDATE` | `BEFORE` | `ROW` | Monto, moneda y referencia no se reescriben | [`RF-P-16`][rf-p-16] |
|   `trg_pago_no_borrar`    | `DELETE` | `BEFORE` | `ROW` | Bloquea el borrado; es un registro contable | [`RF-T-27`][rf-t-27] |

### Índices

|        Nombre         |            Definición             |                 Propósito                 |
| :-------------------: | :-------------------------------: | :---------------------------------------: |
| `idx_pago_historial`  | `(reserva_id, capturado_en DESC)` | [Historial de pagos del turista][rf-t-27] |
| `brin_pago_capturado` |       `BRIN (capturado_en)`       |      [Exportación mensual][rf-p-17]       |

### Notas de diseño

No se puede reembolsar lo que nunca se capturó, y el `CHECK` lo impone. Una
reserva `expirada` no llega a tener captura, así que tampoco puede tener
reembolso; sin la restricción, un error de proceso podría registrar la devolución
de un dinero que nadie cobró.

`unq_pago_referencia` es la defensa contra el reintento de la pasarela. Los
proveedores de cobro reenvían la confirmación cuando no reciben respuesta, y sin
unicidad sobre la referencia externa un reenvío crearía un segundo pago sobre la
misma reserva.

!!! warning "Momento de captura sin definir"

    Cuándo se captura el pago —al reservar, al iniciar el servicio o al
    cerrarlo— **no está definido** en ninguna fuente del análisis, y de esa
    definición depende el ciclo de vida completo de `pago` y de `reserva`.
    [`RF-T-27`][rf-t-27] lo señala como condicionante de qué registros aparecen
    en el historial del turista. `capturado_en` admite nulo justamente para no
    prejuzgarlo.

---

## `comision`

Lo que la plataforma retuvo de un pago. Es una entidad y no un porcentaje
aplicado al vuelo.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una por pago liberado
- **Origen:**
  > - [`RF-P-16`][rf-p-16]

### Columnas

|      Campo       |      Tipo       | Nulo | Predeterminado |          Descripción          |
| :--------------: | :-------------: | :--: | :------------: | :---------------------------: |
|    `pago_id`     |     `uuid`      |  no  |                |   Llave foránea `RESTRICT`    |
|  `monto_bruto`   | `numeric(12,2)` |  no  |                |  Del que salió la retención   |
|   `porcentaje`   | `numeric(5,2)`  |  no  |                |    El vigente al liquidar     |
| `monto_retenido` | `numeric(12,2)` |  no  |                | Lo que se quedó la plataforma |
|   `monto_neto`   | `numeric(12,2)` |  no  |                | Lo que le queda al prestador  |
|  `liquidada_en`  |  `timestamptz`  |  no  |    `now()`     |                               |

### Constraints

```postgresql
CONSTRAINT chk_comision_porcentaje_rango
CHECK (porcentaje BETWEEN 0 AND 100)

CONSTRAINT chk_comision_montos_positivos
CHECK (
  monto_bruto > 0
  AND
  monto_retenido >= 0
  AND
  monto_neto >= 0
)

CONSTRAINT chk_comision_resta_cuadra
CHECK (monto_bruto = monto_retenido + monto_neto)
```

### Unicidad

|       Nombre        | Definición  |            Propósito            |
| :-----------------: | :---------: | :-----------------------------: |
| `unq_comision_pago` | `(pago_id)` | Un pago se liquida una sola vez |

### Triggers

|         Nombre          |  Evento  | Momento  | Nivel |                 Regla                  |        Origen        |
| :---------------------: | :------: | :------: | :---: | :------------------------------------: | :------------------: |
| `trg_comision_readonly` | `UPDATE` | `BEFORE` | `ROW` |      Ninguna columna se reescribe      | [`RF-P-16`][rf-p-16] |
|  `trg_comision_abona`   | `INSERT` | `AFTER`  | `ROW` | Inserta el `movimiento_saldo` del neto | [`RF-P-16`][rf-p-16] |

### Notas de diseño

Las cuatro cifras se guardan aunque tres bastarían para deducir la cuarta.
[`RF-P-16`][rf-p-16] exige que el prestador pueda **verificar la resta y no solo
el resultado**, y `chk_comision_resta_cuadra` convierte esa verificación en un
invariante de la base: una fila que no cuadre no entra.

`porcentaje` se copia y no se lee del parámetro vigente. Cambiar la comisión
después no altera nada ya liquidado, que es la misma razón por la que la reserva
congela su tarifa. Sin la copia, el balance de un mes cerrado cambiaría al
ajustar el porcentaje.

!!! warning "Porcentaje sin definir"

    El porcentaje de comisión aplicable **no está definido** en ninguna fuente;
    [`RF-P-16`][rf-p-16] lo señala de forma explícita. Cuando exista, su sitio
    es [`Parametro`][catalogos] y esta columna seguirá copiando el valor vigente
    al liquidar.

---

## `movimiento_saldo`

El libro del saldo del prestador. Mismo principio que
[`movimiento_insignia`][insignias].

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** dos por servicio cerrado
- **Origen:**
  > - [`RF-P-16`][rf-p-16]
  > - [`RF-P-18`][rf-p-18]

### Columnas

|         Campo         |      Tipo       | Nulo | Predeterminado |               Descripción               |
| :-------------------: | :-------------: | :--: | :------------: | :-------------------------------------: |
| `perfil_prestador_id` |     `uuid`      |  no  |                |        Llave foránea `RESTRICT`         |
|        `monto`        | `numeric(12,2)` |  no  |                | Positivo al abonar, negativo al retirar |
|      `moneda_id`      |     `uuid`      |  no  |                |   Llave foránea `RESTRICT` a `moneda`   |
|     `comision_id`     |     `uuid`      |  sí  |                |    Origen A, excluyente con el otro     |
| `solicitud_retiro_id` |     `uuid`      |  sí  |                |    Origen B, excluyente con el otro     |
|    `registrado_en`    |  `timestamptz`  |  no  |    `now()`     |                                         |

### Constraints

```postgresql
CONSTRAINT chk_movimientosaldo_origen_excluyente
CHECK (num_nonnulls(comision_id, solicitud_retiro_id) = 1)

CONSTRAINT chk_movimientosaldo_signo_coherente
CHECK (
  (comision_id IS NOT NULL AND monto > 0)
  OR
  (solicitud_retiro_id IS NOT NULL AND monto < 0)
)
```

### Unicidad

|             Nombre             |                          Definición                           |            Propósito             |
| :----------------------------: | :-----------------------------------------------------------: | :------------------------------: |
| `unq_movimientosaldo_comision` |         `(comision_id) WHERE comision_id IS NOT NULL`         | Una comisión abona una sola vez  |
|  `unq_movimientosaldo_retiro`  | `(solicitud_retiro_id) WHERE solicitud_retiro_id IS NOT NULL` | Un retiro descuenta una sola vez |

### Triggers

|              Nombre              |  Evento  | Momento  | Nivel |                 Regla                 |        Origen        |
| :------------------------------: | :------: | :------: | :---: | :-----------------------------------: | :------------------: |
| `trg_movimientosaldo_suficiente` | `INSERT` | `BEFORE` | `ROW` | El saldo resultante no queda negativo | [`RF-P-18`][rf-p-18] |

### Índices

|            Nombre             |                 Definición                  |           Propósito            |
| :---------------------------: | :-----------------------------------------: | :----------------------------: |
| `idx_movimientosaldo_balance` | `(perfil_prestador_id, registrado_en DESC)` | [Balance de ingresos][rf-p-16] |

### Notas de diseño

Cada movimiento nace de un hecho concreto —una comisión liquidada o un retiro
solicitado— y guarda su referencia, de modo que todo saldo es explicable
movimiento por movimiento. El `CHECK` de signo ata el sentido al origen: una
comisión solo abona, un retiro solo descuenta.

---

## `cuenta_bancaria` y `cuenta_bancaria_cambio`

Dónde cobra el prestador y el periodo de espera que protege ese dato.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una activa por prestador
- **Origen:**
  > - [`RF-P-07`][rf-p-07]

### Columnas de `cuenta_bancaria`

|         Campo         |     Tipo      | Nulo | Predeterminado |                 Descripción                  |
| :-------------------: | :-----------: | :--: | :------------: | :------------------------------------------: |
| `perfil_prestador_id` |    `uuid`     |  no  |                |           Llave foránea `RESTRICT`           |
|        `banco`        |   `varchar`   |  no  |                |                                              |
|       `titular`       |   `varchar`   |  no  |                |                                              |
|   `numero_cifrado`    |    `bytea`    |  no  |                | Cifrado en la aplicación, **nunca en claro** |
|    `llave_cifrado`    |   `varchar`   |  no  |                |   Qué llave lo cifró, para poder rotarlas    |
|   `ultimos_cuatro`    |   `varchar`   |  no  |                |     Lo único que se muestra al prestador     |
|    `vigente_desde`    | `timestamptz` |  no  |                |    Cuándo empezó a poder recibir retiros     |
|   `reemplazada_en`    | `timestamptz` |  sí  |                |      Nulo mientras es la cuenta activa       |

### Columnas de `cuenta_bancaria_cambio`

|        Campo         |     Tipo      | Nulo | Predeterminado |              Descripción               |
| :------------------: | :-----------: | :--: | :------------: | :------------------------------------: |
| `cuenta_anterior_id` |    `uuid`     |  sí  |                |        Nulo en el alta inicial         |
|  `cuenta_nueva_id`   |    `uuid`     |  no  |                |        Llave foránea `RESTRICT`        |
|   `solicitado_en`    | `timestamptz` |  no  |    `now()`     |                                        |
|    `efectivo_en`     | `timestamptz` |  no  |                | `solicitado_en` más veinticuatro horas |
|    `cancelado_en`    | `timestamptz` |  sí  |                |       Nulo salvo que se revierta       |

### Constraints

```postgresql
CONSTRAINT chk_cuentabancaria_ultimoscuatro
CHECK (ultimos_cuatro ~ '^[0-9]{4}$')

CONSTRAINT chk_cuentabancariacambio_espera
CHECK (efectivo_en > solicitado_en)

CONSTRAINT chk_cuentabancariacambio_distintas
CHECK (cuenta_anterior_id IS DISTINCT FROM cuenta_nueva_id)
```

### Unicidad

|           Nombre            |                      Definición                      |              Propósito               |
| :-------------------------: | :--------------------------------------------------: | :----------------------------------: |
| `unq_cuentabancaria_activa` | `(perfil_prestador_id) WHERE reemplazada_en IS NULL` | Una sola cuenta activa por prestador |

### Notas de diseño

El cambio es una fila y no una actualización, por [`D-10`][d-10].
[`RF-P-07`][rf-p-07] impone veinticuatro horas de espera antes de que una cuenta
nueva surta efecto; modelarlo como fecha en la propia cuenta obligaría a
sobrescribir el dato anterior, y entonces no habría a qué revertir si el cambio
resulta fraudulento. La cuenta activa sigue siendo la anterior hasta que vence.

El número va cifrado en la aplicación con su llave identificada, por
[`D-09`][d-09]. Un volcado de la base de datos no debe bastar para desviar un
retiro. `ultimos_cuatro` existe para que el prestador reconozca su cuenta sin que
el sistema tenga que descifrar nada en una pantalla de consulta.

---

## `solicitud_retiro`

La petición de transferir el saldo neto a la cuenta registrada.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** unas pocas por prestador al año
- **Origen:**
  > - [`RF-P-18`][rf-p-18]

### Columnas

|         Campo         |      Tipo       | Nulo | Predeterminado |             Descripción             |
| :-------------------: | :-------------: | :--: | :------------: | :---------------------------------: |
| `perfil_prestador_id` |     `uuid`      |  no  |                |      Llave foránea `RESTRICT`       |
| `cuenta_bancaria_id`  |     `uuid`      |  no  |                |       La vigente al solicitar       |
|        `monto`        | `numeric(12,2)` |  no  |                |           Mayor que cero            |
|      `moneda_id`      |     `uuid`      |  no  |                | Llave foránea `RESTRICT` a `moneda` |
|    `solicitado_en`    |  `timestamptz`  |  no  |    `now()`     |                                     |
|      `pagado_en`      |  `timestamptz`  |  sí  |                |    Nulo mientras está en proceso    |
|    `rechazado_en`     |  `timestamptz`  |  sí  |                |         Nulo salvo rechazo          |
|      `motivo_id`      |     `uuid`      |  sí  |                |       Obligatorio al rechazar       |

### Constraints

```postgresql
CONSTRAINT chk_solicitudretiro_monto_positivo
CHECK (monto > 0)

CONSTRAINT chk_solicitudretiro_resolucion_excluyente
CHECK (num_nonnulls(pagado_en, rechazado_en) <= 1)

CONSTRAINT chk_solicitudretiro_motivo_exigido
CHECK ((rechazado_en IS NULL) = (motivo_id IS NULL))
```

### Unicidad

|              Nombre              |                               Definición                                |           Propósito           |
| :------------------------------: | :---------------------------------------------------------------------: | :---------------------------: |
| `unq_solicitudretiro_en_proceso` | `(perfil_prestador_id) WHERE num_nonnulls(pagado_en, rechazado_en) = 0` | Una sola solicitud en proceso |

### Triggers

|                Nombre                |  Evento  | Momento  | Nivel |                   Regla                    |        Origen        |
| :----------------------------------: | :------: | :------: | :---: | :----------------------------------------: | :------------------: |
|     `trg_solicitudretiro_minimo`     | `INSERT` | `BEFORE` | `ROW` | Exige el mínimo de veinte dólares de saldo | [`RF-P-18`][rf-p-18] |
| `trg_solicitudretiro_cuenta_vigente` | `INSERT` | `BEFORE` | `ROW` |   La cuenta ya cumplió su espera de 24 h   | [`RF-P-07`][rf-p-07] |
|   `trg_solicitudretiro_descuenta`    | `INSERT` | `AFTER`  | `ROW` |   Inserta el `movimiento_saldo` negativo   | [`RF-P-18`][rf-p-18] |

### Notas de diseño

`unq_solicitudretiro_en_proceso` es lo que impone que el portal no deje iniciar
otra mientras una esté en curso. [`RF-P-18`][rf-p-18] lo pide como regla de
interfaz, pero dos peticiones simultáneas la saltarían si viviera solo ahí: el
índice único parcial la convierte en una garantía.

El mínimo de veinte dólares es un trigger y no un `CHECK` porque no depende de
esta fila sino del saldo acumulado, que es la suma de otra tabla. Es la forma de
regla que [`Convenciones`][convenciones-invariantes] asigna al disparador.

El descuento ocurre al solicitar y no al pagar. Si el saldo solo bajara con la
transferencia efectiva, el prestador podría solicitar dos veces el mismo dinero
mientras la primera está en proceso, y la unicidad no lo impediría si una de las
dos fuera rechazada.

---

## Fuera de este módulo

|            Cosa            |             Dónde vive             |                  Por qué no aquí                   |
| :------------------------: | :--------------------------------: | :------------------------------------------------: |
|   `reserva` y su estado    |      [`Servicios`][servicios]      | `retiene_fondos` dice cuándo liberar, pero es suyo |
|     `perfil_prestador`     |       [`Perfiles`][perfiles]       |         La cuenta y el saldo cuelgan de él         |
|  `moneda` y `tasa_cambio`  |      [`Catálogos`][catalogos]      |   La conversión es un catálogo, no un movimiento   |
| `suscripcion` del comercio | [`Organizaciones`][organizaciones] |  Es un cobro, pero no toca el saldo del prestador  |

[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[convenciones-invariantes]: ../convenciones.md#invariantes
[d-09]: ../decisiones.md#d-09
[d-10]: ../decisiones.md#d-10
[d-24]: ../decisiones.md#d-24
[insignias]: insignias.md
[organizaciones]: organizaciones.md
[perfiles]: perfiles.md
[servicios]: servicios.md
[rf-p-07]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-07
[rf-p-16]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-16
[rf-p-17]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-17
[rf-p-18]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-18
[rf-t-27]: ../../requerimientos/funcionales/app-turista.md#rf-t-27
