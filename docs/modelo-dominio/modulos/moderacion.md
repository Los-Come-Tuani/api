---
icon: lucide/gavel
---

# Moderación y sanciones

Lo que el equipo interno revisa y lo que decide. Dos flujos que no se mezclan: la
cola de verificación, por la que pasa todo lo que aspira a existir para el
turista, y el tablero de reportes, por el que pasa lo que la comunidad denuncia.

La sanción es la causa y el estado de la cuenta es su consecuencia, por
[`D-14`][d-14]. Sin la tabla no habría historial de reincidencia y una segunda
suspensión borraría el rastro de la primera.

## Requerimientos cubiertos

- [`RF-B-01`][rf-b-01]
- [`RF-B-02`][rf-b-02]
- [`RF-B-03`][rf-b-03]
- [`RF-B-04`][rf-b-04]
- [`RF-B-05`][rf-b-05]
- [`RF-B-06`][rf-b-06]
- [`RF-B-07`][rf-b-07]
- [`RF-B-08`][rf-b-08]
- [`RF-B-09`][rf-b-09]
- [`RF-B-10`][rf-b-10]

---

## `solicitud_verificacion`

La cola de trabajo del equipo interno. Admite cuatro objetos mutuamente
excluyentes.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una por acreditación y por organización registrada
- **Origen:**
  > - [`RF-B-01`][rf-b-01]
  > - [`RF-B-05`][rf-b-05]

### Columnas

|           Campo           |     Tipo      | Nulo | Predeterminado |              Descripción              |
| :-----------------------: | :-----------: | :--: | :------------: | :-----------------------------------: |
|     `acreditacion_id`     |    `uuid`     |  sí  |                |      Objeto A, uno de los cuatro      |
|       `comercio_id`       |    `uuid`     |  sí  |                |               Objeto B                |
|       `alcaldia_id`       |    `uuid`     |  sí  |                |               Objeto C                |
| `institucion_cultural_id` |    `uuid`     |  sí  |                |               Objeto D                |
|        `estado_id`        |    `uuid`     |  no  |                | Llave foránea a `estado_verificacion` |
|       `tomada_por`        |    `uuid`     |  sí  |                |  Qué moderador la tiene en revisión   |
|       `enviada_en`        | `timestamptz` |  no  |    `now()`     |     Ordena la cola por antigüedad     |
|       `resuelta_en`       | `timestamptz` |  sí  |                |     Nulo mientras está en bandeja     |

### Llaves foráneas

|          Columna          |       Referencia       | `ON DELETE` |                  Notas                  |
| :-----------------------: | :--------------------: | :---------: | :-------------------------------------: |
|     `acreditacion_id`     |     `acreditacion`     |  `CASCADE`  | El expediente muere con lo que verifica |
|       `comercio_id`       |       `comercio`       |  `CASCADE`  |                                         |
|       `alcaldia_id`       |       `alcaldia`       |  `CASCADE`  |                                         |
| `institucion_cultural_id` | `institucion_cultural` |  `CASCADE`  |                                         |
|        `estado_id`        | `estado_verificacion`  | `RESTRICT`  |                                         |
|       `tomada_por`        |       `usuario`        | `RESTRICT`  |                                         |

### Constraints

```postgresql
CONSTRAINT chk_solicitudverificacion_objeto_excluyente
CHECK (
  num_nonnulls(
    acreditacion_id,
    comercio_id,
    alcaldia_id,
    institucion_cultural_id
  ) = 1
)

CONSTRAINT chk_solicitudverificacion_resuelta_coherente
CHECK (
  resuelta_en IS NULL
  OR
  resuelta_en >= enviada_en
)
```

### Índices

|               Nombre                |                Definición                |                Propósito                |
| :---------------------------------: | :--------------------------------------: | :-------------------------------------: |
| `idx_solicitudverificacion_bandeja` | `(enviada_en) WHERE resuelta_en IS NULL` | [Cola por antigüedad de envío][rf-b-01] |
| `idx_solicitudverificacion_tomada`  | `(tomada_por) WHERE resuelta_en IS NULL` |  Qué tiene cada moderador en revisión   |

### Notas de diseño

Cuatro llaves nulables y un `CHECK` que exige exactamente una, en lugar de cuatro
colas. Lo que cambia entre una acreditación y el registro de un comercio es el
documento exigido y la severidad de la revisión, no el ciclo: las cuatro se
registran solas, ninguna existe para el turista antes de la aprobación y todas se
resuelven con aprobación o rechazo motivado.

El orden de llegada es el criterio de atención y por eso `enviada_en` es la clave
del índice de bandeja. [`RF-B-01`][rf-b-01] lo justifica en que ninguna solicitud
quede indefinidamente al final por falta de un criterio explícito.

`tomada_por` es nulo mientras nadie la tiene en revisión, y volver a nulo es lo
que significa devolverla a la cola. El diagrama de estados lo dibuja como la
transición de `en_revision` a `enviada`.

---

## `estado_verificacion`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma una: `en_bandeja`.

|    Código     | `en_bandeja` | `es_terminal` |
| :-----------: | :----------: | :-----------: |
|   `enviada`   |    **sí**    |      no       |
| `en_revision` |    **sí**    |      no       |
|  `aprobada`   |      no      |    **sí**     |
|  `rechazada`  |      no      |    **sí**     |

`rechazada` es terminal **para ese expediente**. Subsanar no lo reabre: el
solicitante carga un documento nuevo y eso genera otra verificación, de modo que
el historial conserva cuántas veces se intentó y por qué se rechazó cada vez.

---

## `resolucion_verificacion`

Cómo se cerró un expediente: quién decidió, cuándo y por qué.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** una por solicitud resuelta
- **Origen:**
  > - [`RF-B-03`][rf-b-03]
  > - [`RF-B-04`][rf-b-04]

### Columnas

|     Campo      |     Tipo      | Nulo | Predeterminado |             Descripción              |
| :------------: | :-----------: | :--: | :------------: | :----------------------------------: |
| `solicitud_id` |    `uuid`     |  no  |                |       Llave foránea `CASCADE`        |
| `resuelta_por` |    `uuid`     |  no  |                | Llave foránea `RESTRICT` a `usuario` |
|   `aprobada`   |   `boolean`   |  no  |                |                                      |
|  `motivo_id`   |    `uuid`     |  sí  |                |       Obligatorio al rechazar        |
|     `nota`     |    `text`     |  no  |      `''`      |  Lo que se comunica al solicitante   |
| `resuelta_en`  | `timestamptz` |  no  |    `now()`     |                                      |

### Constraints

```postgresql
CONSTRAINT chk_resolucionverificacion_motivo_exigido
CHECK (aprobada OR motivo_id IS NOT NULL)
```

### Unicidad

|                 Nombre                 |    Definición    |            Propósito            |
| :------------------------------------: | :--------------: | :-----------------------------: |
| `unq_resolucionverificacion_solicitud` | `(solicitud_id)` | Un expediente se cierra una vez |

### Triggers

|               Nombre                |  Evento  | Momento | Nivel |                      Regla                       |        Origen        |
| :---------------------------------: | :------: | :-----: | :---: | :----------------------------------------------: | :------------------: |
| `trg_resolucionverificacion_aplica` | `INSERT` | `AFTER` | `ROW` | Al aprobar, escribe `verificado_en` en el objeto | [`RF-B-03`][rf-b-03] |

### Notas de diseño

El motivo es obligatorio al rechazar y el `CHECK` lo impone sin condicionales.
[`RF-B-04`][rf-b-04] lo justifica en que un rechazo sin causa explicada obliga a
reintentar a ciegas; como restricción, ninguna vía de escritura puede saltárselo.

Es de solo inserción y la solicitud es mutable protegida. La resolución es un
hecho: quién decidió qué y cuándo. Que el expediente pueda cambiar de estado no
implica que la decisión ya tomada pueda reescribirse.

La aprobación es la única vía por la que un prestador o una organización se hacen
visibles. Por eso el trigger escribe `verificado_en` en el objeto en lugar de
dejarlo al servicio: es la puerta que separa lo que existe para el turista de lo
que no.

---

## `reporte`

Lo que la comunidad denuncia.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** cientos al año
- **Origen:**
  > - [`RF-B-06`][rf-b-06]

### Columnas

|     Campo      |     Tipo      | Nulo | Predeterminado |            Descripción             |
| :------------: | :-----------: | :--: | :------------: | :--------------------------------: |
|  `emisor_id`   |    `uuid`     |  no  |                |           Quién reporta            |
| `reportado_id` |    `uuid`     |  no  |                |            Sobre quién             |
|  `motivo_id`   |    `uuid`     |  no  |                |      Llave foránea `RESTRICT`      |
|  `reserva_id`  |    `uuid`     |  sí  |                | El servicio en disputa, si lo hay  |
| `descripcion`  |    `text`     |  no  |      `''`      |                                    |
|   `gravedad`   |  `smallint`   |  no  |      `1`       |        Prioriza el tablero         |
|  `creado_en`   | `timestamptz` |  no  |    `now()`     |                                    |
| `resuelto_en`  | `timestamptz` |  sí  |                | Nulo mientras el caso está abierto |
| `resuelto_por` |    `uuid`     |  sí  |                |                                    |

### Constraints

```postgresql
CONSTRAINT chk_reporte_partes_distintas
CHECK (emisor_id <> reportado_id)

CONSTRAINT chk_reporte_gravedad_rango
CHECK (gravedad BETWEEN 1 AND 3)

CONSTRAINT chk_reporte_resolucion_completa
CHECK ((resuelto_en IS NULL) = (resuelto_por IS NULL))
```

### Índices

|         Nombre          |                       Definición                       |                  Propósito                   |
| :---------------------: | :----------------------------------------------------: | :------------------------------------------: |
|  `idx_reporte_tablero`  | `(gravedad DESC, creado_en) WHERE resuelto_en IS NULL` | [Tablero por gravedad y antigüedad][rf-b-06] |
| `idx_reporte_reportado` |            `(reportado_id, creado_en DESC)`            |         Antecedentes de una persona          |

### Notas de diseño

Nadie se reporta a sí mismo, y el `CHECK` lo impide. Es la clase de dato basura
que entra por una carga masiva o una prueba mal borrada y luego aparece en el
tablero sin que nadie sepa de dónde salió.

El tablero se ordena por gravedad y después por antigüedad, al revés que la cola
de verificación. La diferencia es deliberada: una verificación tardía retrasa un
alta, mientras que un reporte grave sin atender deja operando a quien acosa.

---

## `sancion`

La causa de que una cuenta deje de operar.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** decenas al año
- **Origen:**
  > - [`RF-B-07`][rf-b-07]
  > - [`RF-B-08`][rf-b-08]
  > - [`RF-B-10`][rf-b-10]

### Columnas

|      Campo       |     Tipo      | Nulo | Predeterminado |             Descripción              |
| :--------------: | :-----------: | :--: | :------------: | :----------------------------------: |
|   `usuario_id`   |    `uuid`     |  no  |                |           Quien la recibe            |
|  `dictada_por`   |    `uuid`     |  no  |                |       Qué supervisor la aplicó       |
|   `reporte_id`   |    `uuid`     |  sí  |                |  El caso que la originó, si lo hay   |
|   `motivo_id`    |    `uuid`     |  no  |                |    **Obligatorio** en ambos tipos    |
| `dispositivo_id` |    `uuid`     |  sí  |                | Solo en expulsión: el aparato vetado |
|   `permanente`   |   `boolean`   |  no  |    `false`     |      Expulsión si es verdadero       |
| `razon_interna`  |    `text`     |  no  |                |   Lo que sostiene la reincidencia    |
|   `dictada_en`   | `timestamptz` |  no  |    `now()`     |                                      |
|    `vence_en`    | `timestamptz` |  sí  |                |        Nulo si es permanente         |

### Constraints

```postgresql
CONSTRAINT chk_sancion_vigencia_coherente
CHECK (permanente = (vence_en IS NULL))

CONSTRAINT chk_sancion_dispositivo_solo_permanente
CHECK (
  dispositivo_id IS NULL
  OR
  permanente
)

CONSTRAINT chk_sancion_vencimiento_posterior
CHECK (
  vence_en IS NULL
  OR
  vence_en > dictada_en
)

CONSTRAINT chk_sancion_razon_no_vacia
CHECK (length(razon_interna) > 0)
```

### Triggers

|             Nombre             |  Evento  | Momento  | Nivel |                      Regla                      |        Origen        |
| :----------------------------: | :------: | :------: | :---: | :---------------------------------------------: | :------------------: |
| `trg_sancion_revoca_sesiones`  | `INSERT` | `AFTER`  | `ROW` |     Revoca de inmediato las sesiones vivas      | [`RF-B-07`][rf-b-07] |
| `trg_sancion_cancela_reservas` | `INSERT` | `AFTER`  | `ROW` | Si es permanente, cancela los servicios futuros | [`RF-B-09`][rf-b-09] |
|    `trg_sancion_no_borrar`     | `DELETE` | `BEFORE` | `ROW` |  Bloquea el borrado; sostiene la reincidencia   | [`RF-B-10`][rf-b-10] |
|     `trg_sancion_readonly`     | `UPDATE` | `BEFORE` | `ROW` |          Ninguna columna se reescribe           | [`RF-B-10`][rf-b-10] |

### Índices

|          Nombre           |                     Definición                      |                   Propósito                   |
| :-----------------------: | :-------------------------------------------------: | :-------------------------------------------: |
|  `idx_sancion_historial`  |           `(usuario_id, dictada_en DESC)`           |       [Historial de sanciones][rf-b-10]       |
|   `idx_sancion_vigente`   |       `(vence_en) WHERE vence_en IS NOT NULL`       |     El barrido que cumple las temporales      |
| `idx_sancion_dispositivo` | `(dispositivo_id) WHERE dispositivo_id IS NOT NULL` | [Veto al registrar desde el aparato][rf-b-08] |

### Notas de diseño

`permanente` y `vence_en` se atan con una equivalencia y no con dos reglas
sueltas. Una expulsión con fecha de vencimiento no es una expulsión, y una
suspensión sin plazo no se cumple nunca: `permanente = (vence_en IS NULL)`
descarta las dos combinaciones de una vez.

El dispositivo solo se veta en la expulsión. [`RF-B-08`][rf-b-08] registra el
aparato desde el que operaba el infractor para impedir que cree cuentas nuevas
desde él; una suspensión temporal no lo hace, y el `CHECK` impide que alguien lo
escriba por descuido en la sanción equivocada.

La sanción no reemplaza al estado de la cuenta, lo causa. El estado refleja la
sanción vigente y es lo que consultan las sesiones, pero sin esta tabla no habría
historial: una segunda suspensión sobrescribiría el rastro de la primera y no
habría cómo justificar por qué dos infracciones parecidas recibieron castigos
distintos.

La contraparte de una reserva cancelada se entera de la cancelación pero no de la
sanción. [`RF-B-09`][rf-b-09] lo pide de forma expresa, y por eso
`trg_sancion_cancela_reservas` escribe la cancelación sin propagar el
`reporte_id` ni la `razon_interna` a la notificación.

!!! warning "Levantar una sanción no está definido"

    Ninguna fuente define cómo se revierte una sanción antes de tiempo. Hoy la
    única salida de `vigente` es que el plazo se cumpla, y por eso la tabla no
    tiene `levantada_en` ni `levantada_por`. Si la operación llega a existir,
    esas dos columnas y su motivo son lo que hay que agregar.

---

## Fuera de este módulo

|         Cosa         |         Dónde vive         |                 Por qué no aquí                 |
| :------------------: | :------------------------: | :---------------------------------------------: |
|   `estado_usuario`   |  [`Identidad`][identidad]  | Es la consecuencia de la sanción, no la sanción |
|    `acreditacion`    |   [`Perfiles`][perfiles]   | Lo que se verifica, con sus fechas de vigencia  |
|    `dispositivo`     |  [`Identidad`][identidad]  |  Sobrevive al usuario porque sostiene el veto   |
| `resena_impugnacion` | [`Reputación`][reputacion] | Llega al tablero, pero su ciclo es de la reseña |
|       `motivo`       |  [`Catálogos`][catalogos]  |  Lista cerrada con `exige_texto` por contexto   |

[auditoria]: ../convenciones.md#auditoria
[catalogos]: catalogos.md
[d-14]: ../decisiones.md#d-14
[identidad]: identidad.md
[perfiles]: perfiles.md
[reputacion]: reputacion.md
[rf-b-01]: ../../requerimientos/funcionales/backoffice.md#rf-b-01
[rf-b-02]: ../../requerimientos/funcionales/backoffice.md#rf-b-02
[rf-b-03]: ../../requerimientos/funcionales/backoffice.md#rf-b-03
[rf-b-04]: ../../requerimientos/funcionales/backoffice.md#rf-b-04
[rf-b-05]: ../../requerimientos/funcionales/backoffice.md#rf-b-05
[rf-b-06]: ../../requerimientos/funcionales/backoffice.md#rf-b-06
[rf-b-07]: ../../requerimientos/funcionales/backoffice.md#rf-b-07
[rf-b-08]: ../../requerimientos/funcionales/backoffice.md#rf-b-08
[rf-b-09]: ../../requerimientos/funcionales/backoffice.md#rf-b-09
[rf-b-10]: ../../requerimientos/funcionales/backoffice.md#rf-b-10
