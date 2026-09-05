---
icon: lucide/shield-check
---

# Roles y permisos

Quién puede hacer qué y **sobre qué objeto**. Saber que una cuenta tiene el rol de
operador de circuitos no basta: hay que saber de qué ciudad, y por eso toda
asignación lleva un ámbito tipado, por [`D-02`][d-02].

El permiso se otorga siempre por rol y nunca directamente a la cuenta, por
[`D-03`][d-03]. No existe tabla `usuario_permiso`.

## Requerimientos cubiertos

- [`RF-S-08`][rf-s-08]
- [`RF-A-03`][rf-a-03]

---

## `rol`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** una docena de filas
- **Origen:**
  > - [`RF-S-08`][rf-s-08]

### Columnas

|       Campo        |   Tipo    | Nulo | Predeterminado |          Descripción           |
| :----------------: | :-------: | :--: | :------------: | :----------------------------: |
|      `codigo`      | `varchar` |  no  |                |  Cómo lo referencia el código  |
|     `etiqueta`     | `varchar` |  no  |                |                                |
| `ambito_requerido` | `varchar` |  no  |   `'global'`   | Qué llave exige la asignación  |
|    `asignable`     | `boolean` |  no  |     `true`     | Falso en los roles del sistema |

### Constraints

```postgresql
CONSTRAINT chk_rol_ambito_requerido
CHECK (
  ambito_requerido IN ('global', 'alcaldia', 'comercio', 'institucion')
)
```

### Unicidad

|      Nombre      | Definición |      Propósito       |
| :--------------: | :--------: | :------------------: |
| `unq_rol_codigo` | `(codigo)` | El código identifica |

### Notas de diseño

`ambito_requerido` es lo que convierte el ámbito en una regla verificable y no en
una convención. Declara cuál de las tres llaves exige cada rol, y el trigger de
`asignacion_rol` comprueba que la asignación la traiga: sin él, un operador de
comercio podría asignarse a una ciudad y nada lo detectaría.

---

## `permiso`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** decenas de filas

### Columnas

|   Campo   |   Tipo    | Nulo | Predeterminado |            Descripción             |
| :-------: | :-------: | :--: | :------------: | :--------------------------------: |
| `codigo`  | `varchar` |  no  |                |    Derivado de recurso y acción    |
| `recurso` | `varchar` |  no  |                |          Sobre qué actúa           |
| `accion`  | `varchar` |  no  |                | `add`, `change`, `delete` o `view` |

### Unicidad

|            Nombre            |     Definición      |                   Propósito                   |
| :--------------------------: | :-----------------: | :-------------------------------------------: |
|     `unq_permiso_codigo`     |     `(codigo)`      |                                               |
| `unq_permiso_recurso_accion` | `(recurso, accion)` | El código es derivable, no una segunda fuente |

### Notas de diseño

Las dos unicidades no sobran. El código se deriva del par, así que sin la segunda
podrían existir dos filas con el mismo recurso y la misma acción bajo códigos
distintos, y entonces revocar una dejaría la otra en pie.

---

## `rol_permiso`

Qué permisos agrupa cada rol. Es la única vía de concesión.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** cientos de filas
- **Origen:**
  > - [`RF-S-08`][rf-s-08]

### Columnas

|     Campo      |     Tipo      | Nulo | Predeterminado |       Descripción        |
| :------------: | :-----------: | :--: | :------------: | :----------------------: |
|    `rol_id`    |    `uuid`     |  no  |                | Llave foránea `CASCADE`  |
|  `permiso_id`  |    `uuid`     |  no  |                | Llave foránea `RESTRICT` |
| `concedido_en` | `timestamptz` |  no  |    `now()`     |                          |

### Unicidad

|        Nombre        |       Definición       |                    Propósito                    |
| :------------------: | :--------------------: | :---------------------------------------------: |
| `unq_rolpermiso_par` | `(rol_id, permiso_id)` | Un permiso no se concede dos veces al mismo rol |

### Notas de diseño

Concentrar la concesión aquí convierte la revocación en una sola operación
auditable. Un permiso concedido de forma individual sería invisible en la
revisión del rol y sobreviviría a su revocación; el andamiaje de Django admite
ambas vías, y el modelo de dominio usa solo esta.

---

## `asignacion_rol`

Quién desempeña qué rol y sobre qué objeto.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una o dos por cuenta con papel interno
- **Origen:**
  > - [`RF-A-03`][rf-a-03]

### Columnas

|      Campo       |     Tipo      | Nulo | Predeterminado |         Descripción          |
| :--------------: | :-----------: | :--: | :------------: | :--------------------------: |
|   `usuario_id`   |    `uuid`     |  no  |                |   Llave foránea `RESTRICT`   |
|     `rol_id`     |    `uuid`     |  no  |                |   Llave foránea `RESTRICT`   |
|  `alcaldia_id`   |    `uuid`     |  sí  |                |           Ámbito A           |
|  `comercio_id`   |    `uuid`     |  sí  |                |           Ámbito B           |
| `institucion_id` |    `uuid`     |  sí  |                |           Ámbito C           |
|  `otorgada_por`  |    `uuid`     |  no  |                |      Quién la concedió       |
|  `otorgada_en`   | `timestamptz` |  no  |    `now()`     |                              |
|  `revocada_en`   | `timestamptz` |  sí  |                | Nulo mientras el acceso vive |

### Constraints

```postgresql
CONSTRAINT chk_asignacionrol_ambito_unico
CHECK (num_nonnulls(alcaldia_id, comercio_id, institucion_id) <= 1)

CONSTRAINT chk_asignacionrol_revocada_coherente
CHECK (
  revocada_en IS NULL
  OR
  revocada_en >= otorgada_en
)
```

### Unicidad

|           Nombre            |                                         Definición                                         |              Propósito               |
| :-------------------------: | :----------------------------------------------------------------------------------------: | :----------------------------------: |
| `unq_asignacionrol_vigente` | `(usuario_id, rol_id, alcaldia_id, comercio_id, institucion_id) WHERE revocada_en IS NULL` | No se acumula el mismo rol dos veces |

### Triggers

|               Nombre                |         Evento          | Momento  | Nivel |                         Regla                          |        Origen        |
| :---------------------------------: | :---------------------: | :------: | :---: | :----------------------------------------------------: | :------------------: |
| `trg_asignacionrol_ambito_coincide` |   `INSERT`, `UPDATE`    | `BEFORE` | `ROW` | El ámbito presente coincide con `rol.ambito_requerido` | [`RF-A-03`][rf-a-03] |
|    `trg_asignacionrol_norevive`     | `UPDATE OF revocada_en` | `BEFORE` | `ROW` |             `revocada_en` no vuelve a nulo             | [`RF-S-08`][rf-s-08] |
|    `trg_asignacionrol_no_borrar`    |        `DELETE`         | `BEFORE` | `ROW` |        Revocar es escribir la fecha, no borrar         | [`RF-S-10`][rf-s-10] |

### Índices

|            Nombre            |                Definición                 |             Propósito              |
| :--------------------------: | :---------------------------------------: | :--------------------------------: |
| `idx_asignacionrol_vigentes` | `(usuario_id) WHERE revocada_en IS NULL`  | Resolver permisos en cada petición |
| `idx_asignacionrol_alcaldia` | `(alcaldia_id) WHERE revocada_en IS NULL` |      Quién opera una alcaldía      |
| `idx_asignacionrol_comercio` | `(comercio_id) WHERE revocada_en IS NULL` |       Equipo de un comercio        |

### Notas de diseño

Tres llaves nulables y no un par genérico de tipo e identificador. Así cada
referencia conserva su llave foránea real: con un par genérico nada impide
apuntar a un comercio que ya no existe, y la base no podría detectarlo.

Las tres nulas significan alcance global, que es el caso del personal interno. Es
por eso que el `CHECK` usa `<= 1` y no `= 1`: el ámbito global no es la ausencia
de dato sino un valor legítimo, declarado en `rol.ambito_requerido`.

La asignación no se borra. Revocar es escribir `revocada_en`, y eso es lo que
permite responder quién tenía qué acceso el día en que ocurrió algo, que es
justamente lo que se pregunta después de un incidente.

Sin el ámbito, [`RF-A-03`][rf-a-03] dependería de que ninguna consulta olvide
filtrar por ciudad, y basta una sola omisión para que Granada pueda reescribir el
circuito de León.

---

## Fuera de este módulo

|                Cosa                 |             Dónde vive             |               Por qué no aquí               |
| :---------------------------------: | :--------------------------------: | :-----------------------------------------: |
|              `usuario`              |      [`Identidad`][identidad]      | Desempeña roles, pero la identidad es suya  |
|             `alcaldia`              |     [`Territorio`][territorio]     | Es uno de los ámbitos, no parte del permiso |
| `comercio` e `institucion_cultural` | [`Organizaciones`][organizaciones] |                    Ídem                     |

[auditoria]: ../convenciones.md#auditoria
[d-02]: ../decisiones.md#d-02
[d-03]: ../decisiones.md#d-03
[identidad]: identidad.md
[organizaciones]: organizaciones.md
[territorio]: territorio.md
[rf-a-03]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-03
[rf-s-08]: ../../requerimientos/funcionales/plataforma.md#rf-s-08
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
