---
icon: lucide/list-tree
---

# Catálogos y parámetros

Las listas que el resto del modelo referencia y los umbrales que gobiernan su
comportamiento. Es el módulo del que todos dependen y que no depende de ninguno:
por eso no aparece en el mapa de módulos, donde sus aristas convertirían el
diagrama en una malla ilegible.

Toda clasificación es una llave a una de estas tablas y nunca una cadena libre,
por [`Convenciones`][convenciones-tipos]. El código de un catálogo no cambia
aunque cambie el texto que se muestra: es lo que referencian las reglas.

## Requerimientos cubiertos

- [`RF-S-04`][rf-s-04]
- [`RF-S-16`][rf-s-16]

---

## `parametro`

Los umbrales configurables del sistema.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** decenas de filas
- **Origen:**
  > - [`RF-S-16`][rf-s-16]

### Columnas

|      Campo       |     Tipo      | Nulo | Predeterminado |                Descripción                |
| :--------------: | :-----------: | :--: | :------------: | :---------------------------------------: |
|     `clave`      |   `varchar`   |  no  |                |       Cómo lo referencia el código        |
|     `grupo`      |   `varchar`   |  no  |      `''`      |    Permite cargar un dominio completo     |
|     `valor`      |   `varchar`   |  no  |                |    Siempre texto, se convierte al leer    |
|     `unidad`     |   `varchar`   |  no  |      `''`      | `metros`, `minutos`, `dias`, `porcentaje` |
|  `descripcion`   |    `text`     |  no  |      `''`      |                                           |
|    `editable`    |   `boolean`   |  no  |     `true`     |       Falso en los que no se tocan        |
| `actualizado_en` | `timestamptz` |  no  |    `now()`     |                                           |

### Unicidad

|        Nombre         | Definición |      Propósito      |
| :-------------------: | :--------: | :-----------------: |
| `unq_parametro_clave` | `(clave)`  | La clave identifica |

### Triggers

|           Nombre            |      Evento       | Momento  | Nivel |                  Regla                   |        Origen        |
| :-------------------------: | :---------------: | :------: | :---: | :--------------------------------------: | :------------------: |
| `trg_parametro_no_editable` | `UPDATE OF valor` | `BEFORE` | `ROW` | Rechaza el cambio si `editable` es falso | [`RF-S-16`][rf-s-16] |
|  `trg_parametro_historial`  | `UPDATE OF valor` | `AFTER`  | `ROW` |  Inserta la fila en `parametro_cambio`   | [`RF-S-10`][rf-s-10] |

### Índices

|        Nombre         | Definición |                Propósito                |
| :-------------------: | :--------: | :-------------------------------------: |
| `idx_parametro_grupo` | `(grupo)`  | Cargar todos los umbrales de un dominio |

### Notas de diseño

El valor se guarda como texto con la unidad aparte porque el conjunto mezcla
metros, minutos, días y porcentajes. Convertir al tipo correcto es
responsabilidad de quien lo lee; una columna por tipo dejaría todas nulas menos
una en cada fila.

`editable` protege lo que no se toca desde el portal: las vigencias de sesión y
el umbral de edad. Es un trigger y no un permiso porque la regla acompaña al
dato, no al operador.

Aquí viven los umbrales que otros módulos citan: el radio de partida de
[`Geocerca`][notificaciones], el mínimo de retiro de
[`Finanzas`][finanzas] y —cuando se definan— el porcentaje de comisión y el plazo
de pago de una reserva.

---

## `parametro_cambio`

El historial de un umbral. Revertir es insertar el cambio inverso, no borrar la
fila.

- **Régimen:** [De solo inserción][auditoria]
- **Volumen estimado:** unas pocas por parámetro
- **Origen:**
  > - [`RF-S-10`][rf-s-10]

### Columnas

|      Campo       |     Tipo      | Nulo | Predeterminado |             Descripción              |
| :--------------: | :-----------: | :--: | :------------: | :----------------------------------: |
|  `parametro_id`  |    `uuid`     |  no  |                |       Llave foránea `RESTRICT`       |
| `valor_anterior` |   `varchar`   |  no  |                |                                      |
|  `valor_nuevo`   |   `varchar`   |  no  |                |                                      |
|  `cambiado_por`  |    `uuid`     |  no  |                | Llave foránea `RESTRICT` a `usuario` |
|     `motivo`     |    `text`     |  no  |      `''`      |                                      |
| `vigente_desde`  | `timestamptz` |  no  |    `now()`     |                                      |

### Constraints

```postgresql
CONSTRAINT chk_parametrocambio_valores_distintos
CHECK (valor_anterior <> valor_nuevo)
```

---

## `motivo` y `motivo_contexto`

La lista compartida de causas: rechazos, reportes, sanciones, cancelaciones e
impugnaciones.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** decenas de filas

### Columnas de `motivo`

|     Campo     |   Tipo    | Nulo | Predeterminado |         Descripción         |
| :-----------: | :-------: | :--: | :------------: | :-------------------------: |
|   `codigo`    | `varchar` |  no  |                |                             |
|  `etiqueta`   | `varchar` |  no  |                |                             |
| `exige_texto` | `boolean` |  no  |    `false`     | Obliga a acompañar con nota |
|   `activo`    | `boolean` |  no  |     `true`     |                             |

### Columnas de `motivo_contexto`

|    Campo    |    Tipo    | Nulo | Predeterminado |        Descripción         |
| :---------: | :--------: | :--: | :------------: | :------------------------: |
| `motivo_id` |   `uuid`   |  no  |                |  Llave foránea `CASCADE`   |
| `contexto`  | `varchar`  |  no  |                | Dónde se ofrece esta causa |
|   `orden`   | `smallint` |  no  |      `0`       | Cómo se ordena en la lista |

### Unicidad

|          Nombre          |       Definición        |                    Propósito                     |
| :----------------------: | :---------------------: | :----------------------------------------------: |
|   `unq_motivo_codigo`    |       `(codigo)`        |                                                  |
| `unq_motivocontexto_par` | `(motivo_id, contexto)` | Un motivo no aparece dos veces en la misma lista |

### Notas de diseño

Un motivo se ofrece en varios contextos y por eso la relación es una tabla
aparte. «Conducta inapropiada» sirve para un reporte y para una sanción, pero no
para rechazar una acreditación; con una columna de contexto en `motivo` habría
que duplicar la fila por cada sitio donde aplica.

`exige_texto` es lo que distingue una causa que se explica sola de una que no.
«Otro» la exige; «documento vencido», no.

---

## `moneda` y `tasa_cambio`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** pocas monedas, una tasa por par y fecha

### Columnas de `moneda`

|    Campo    |    Tipo    | Nulo | Predeterminado | Descripción |
| :---------: | :--------: | :--: | :------------: | :---------: |
|  `codigo`   | `char(3)`  |  no  |                |  ISO 4217   |
|  `nombre`   | `varchar`  |  no  |                |             |
| `decimales` | `smallint` |  no  |      `2`       |             |

### Columnas de `tasa_cambio`

|        Campo        |      Tipo       | Nulo | Predeterminado |       Descripción        |
| :-----------------: | :-------------: | :--: | :------------: | :----------------------: |
| `moneda_origen_id`  |     `uuid`      |  no  |                | Llave foránea `RESTRICT` |
| `moneda_destino_id` |     `uuid`      |  no  |                | Llave foránea `RESTRICT` |
|       `tasa`        | `numeric(18,8)` |  no  |                |                          |
|   `vigente_desde`   |  `timestamptz`  |  no  |                |                          |

### Constraints

```postgresql
CONSTRAINT chk_tasacambio_positiva
CHECK (tasa > 0)

CONSTRAINT chk_tasacambio_monedas_distintas
CHECK (moneda_origen_id <> moneda_destino_id)
```

### Unicidad

|           Nombre           |                       Definición                       |           Propósito           |
| :------------------------: | :----------------------------------------------------: | :---------------------------: |
|    `unq_moneda_codigo`     |                       `(codigo)`                       |                               |
| `unq_tasacambio_par_fecha` | `(moneda_origen_id, moneda_destino_id, vigente_desde)` | Una sola tasa por par y fecha |

### Notas de diseño

Una tasa nula o negativa rompe todo cálculo de conversión, y convertir una moneda
a sí misma no significa nada: las dos restricciones descartan los errores de
carga que producirían cifras sin sentido en un balance.

La palabra **cambio** está reservada en este modelo para una modificación
registrada de un valor anterior, por [`Convenciones`][convenciones-reservadas].
`tasa_cambio` es la excepción histórica del nombre y designa la conversión entre
monedas, no un historial.

---

## `tipo_servicio` y `tipo_acreditacion`

Qué ofrece un prestador y qué documento lo acredita.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** pocas filas cada uno

### Columnas de `tipo_acreditacion`

|        Campo        |   Tipo    | Nulo | Predeterminado |         Descripción         |
| :-----------------: | :-------: | :--: | :------------: | :-------------------------: |
|      `codigo`       | `varchar` |  no  |                |                             |
|     `etiqueta`      | `varchar` |  no  |                |                             |
| `tipo_servicio_id`  |  `uuid`   |  no  |                |    Qué servicio acredita    |
| `exige_vencimiento` | `boolean` |  no  |     `true`     | Falso en los que no caducan |

### Notas de diseño

Guía y traductor comparten columnas y proceso, así que son un catálogo de tipo de
servicio sobre una misma tabla de prestador y no dos tablas, por
[`D-12`][d-12]. Lo que los diferencia —que solo el guía publica catálogo— es una
regla, no una estructura.

`exige_vencimiento` existe porque un certificado de idioma no caduca y una
licencia del INTUR sí. Sin la columna, [`Perfiles`][perfiles] tendría que
enumerar qué tipos exigen fecha.

---

## Listas cerradas

Seis catálogos comparten la misma forma: `codigo` único, `etiqueta` y poco más.
Se documentan juntos porque dibujarlos por separado ocuparía el triple de espacio
sin decir nada.

|       Tabla        |                              Columnas propias                              |
| :----------------: | :------------------------------------------------------------------------: |
|      `idioma`      |             `char codigo UK`, `varchar nombre`, `bool activo`              |
|       `pais`       |                     `char codigo UK`, `varchar nombre`                     |
|   `tipo_negocio`   |           `varchar codigo UK`, `varchar etiqueta`, `bool activo`           |
| `tipo_institucion` |           `varchar codigo UK`, `varchar etiqueta`, `bool activo`           |
|  `tipo_beneficio`  |        `varchar codigo UK`, `varchar etiqueta`, `bool exige_monto`         |
|    `tipo_aviso`    |        `varchar codigo UK`, `varchar etiqueta`, `bool desactivable`        |
|  `pilar_cultural`  | `varchar codigo UK`, `varchar etiqueta`, `varchar icono`, `smallint orden` |

Tres de esos booleanos son reglas y no adornos:

- `tipo_aviso.desactivable` impide que un usuario apague los avisos
  transaccionales, en [`Notificaciones`][notificaciones].
- `tipo_beneficio.exige_monto` distingue el descuento porcentual, que necesita
  una cifra, del producto gratis, que no, en [`Insignias`][insignias].
- `tipo_institucion.activo` gobierna qué figuras admite el alta en
  [`Organizaciones`][organizaciones].

!!! note "`tipo_institucion` se agregó con el módulo de organizaciones"

    No formaba parte de la lista original de catálogos. Lo exige
    [`RF-I-07`][rf-i-07] al pedir que la institución declare su tipo, y su sitio
    natural es este módulo y no el de organizaciones.

---

## Fuera de este módulo

|          Cosa           |         Dónde vive         |                     Por qué no aquí                      |
| :---------------------: | :------------------------: | :------------------------------------------------------: |
|   `estado_<entidad>`    | El módulo de cada entidad  |      Son catálogos, pero sus preguntas son propias       |
| `pilar_cultural` en uso | [`Territorio`][territorio] | La lista es de aquí; la clasificación del punto, de allí |

[auditoria]: ../convenciones.md#auditoria
[convenciones-reservadas]: ../convenciones.md#palabras-reservadas
[convenciones-tipos]: ../convenciones.md#tipos
[d-12]: ../decisiones.md#d-12
[finanzas]: finanzas.md
[insignias]: insignias.md
[notificaciones]: notificaciones.md
[organizaciones]: organizaciones.md
[perfiles]: perfiles.md
[territorio]: territorio.md
[rf-i-07]: ../../requerimientos/funcionales/portal-instituciones.md#rf-i-07
[rf-s-04]: ../../requerimientos/funcionales/plataforma.md#rf-s-04
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
[rf-s-16]: ../../requerimientos/funcionales/plataforma.md#rf-s-16
