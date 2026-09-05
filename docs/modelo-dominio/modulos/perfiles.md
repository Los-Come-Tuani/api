---
icon: lucide/id-card
---

# Perfiles y acreditaciones

Lo que distingue a un turista de un prestador. La identidad, las credenciales y
la sesión son idénticas para ambos y viven en [`Identidad`][identidad]; aquí
están los datos que solo aplican a un papel, por [`D-01`][d-01].

Una persona tiene a lo sumo un perfil de cada tipo, y esa unicidad es lo que hace
que la relación sea de cero o uno y no de varios.

## Requerimientos cubiertos

- [`RF-P-01`][rf-p-01]
- [`RF-P-02`][rf-p-02]
- [`RF-P-20`][rf-p-20]
- [`RF-T-23`][rf-t-23]
- [`RF-T-24`][rf-t-24]
- [`RF-T-25`][rf-t-25]
- [`RF-S-13`][rf-s-13]

---

## `perfil_turista`

Quién viaja: su nacionalidad, su idioma y su nivel de exploración.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** decenas de miles en el piloto
- **Origen:**
  > - [`RF-T-23`][rf-t-23]
  > - [`RF-T-24`][rf-t-24]

### Columnas

|        Campo        |     Tipo      | Nulo | Predeterminado |            Descripción             |
| :-----------------: | :-----------: | :--: | :------------: | :--------------------------------: |
|    `usuario_id`     |    `uuid`     |  no  |                | Llave foránea `CASCADE`, **única** |
|      `pais_id`      |    `uuid`     |  sí  |                |       Nacionalidad declarada       |
|     `idioma_id`     |    `uuid`     |  no  |                |  Idioma preferido de la interfaz   |
|     `telefono`      |   `varchar`   |  no  |      `''`      |                                    |
|     `biografia`     |    `text`     |  no  |      `''`      |                                    |
|      `foto_id`      |    `uuid`     |  sí  |                | Llave foránea `SET NULL` a `foto`  |
| `nivel_exploracion` |   `integer`   |  no  |      `1`       |  Derivado del saldo de insignias   |
|     `creado_en`     | `timestamptz` |  no  |    `now()`     |                                    |

### Constraints

```postgresql
CONSTRAINT chk_perfilturista_nivel_positivo
CHECK (nivel_exploracion >= 1)

CONSTRAINT chk_perfilturista_biografia_longitud
CHECK (length(biografia) <= 500)
```

### Unicidad

|           Nombre            |   Definición   |            Propósito             |
| :-------------------------: | :------------: | :------------------------------: |
| `unq_perfilturista_usuario` | `(usuario_id)` | Un perfil de turista por persona |

### Notas de diseño

Solo se expone el nombre de pila y la fotografía. [`RF-T-25`][rf-t-25] hace
privados los datos demográficos, así que `pais_id`, `telefono` y `biografia` no
salen del titular: la restricción vive en la proyección que sirve a las
contrapartes, no en el esquema, porque la fila sí necesita guardarlos.

`nivel_exploracion` es dato derivado del saldo de
[`movimiento_insignia`][insignias] y se materializa aquí porque
[`RF-T-23`][rf-t-23] lo muestra junto al perfil en una sola pantalla. Recalcular
el saldo completo para pintar un número en cada carga sería el mismo error que
[`D-23`][d-23] evita con el promedio del prestador.

El correo no está aquí. Es el identificador de acceso y vive en `usuario`; la
edición del perfil no lo toca, tal como [`RF-T-24`][rf-t-24] establece.

---

## `perfil_prestador`

El perfil profesional del guía o del traductor.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** cientos en el piloto
- **Origen:**
  > - [`RF-P-01`][rf-p-01]
  > - [`RF-P-02`][rf-p-02]

### Columnas

|         Campo         |      Tipo      | Nulo | Predeterminado |            Descripción             |
| :-------------------: | :------------: | :--: | :------------: | :--------------------------------: |
|     `usuario_id`      |     `uuid`     |  no  |                | Llave foránea `CASCADE`, **única** |
|      `estado_id`      |     `uuid`     |  no  |                | Llave foránea a `estado_prestador` |
|    `presentacion`     |     `text`     |  no  |      `''`      |                                    |
|       `foto_id`       |     `uuid`     |  sí  |                | Llave foránea `SET NULL` a `foto`  |
| `promedio_valoracion` | `numeric(3,2)` |  sí  |                |   Nulo mientras no tiene reseñas   |
|    `total_resenas`    |   `integer`    |  no  |      `0`       |                                    |
|     `aprobado_en`     | `timestamptz`  |  sí  |                |  Nulo hasta la primera aprobación  |

### Constraints

```postgresql
CONSTRAINT chk_perfilprestador_promedio_rango
CHECK (
  promedio_valoracion IS NULL
  OR
  promedio_valoracion BETWEEN 1.00 AND 5.00
)

CONSTRAINT chk_perfilprestador_promedio_coherente
CHECK ((total_resenas = 0) = (promedio_valoracion IS NULL))
```

### Unicidad

|            Nombre             |   Definición   |             Propósito              |
| :---------------------------: | :------------: | :--------------------------------: |
| `unq_perfilprestador_usuario` | `(usuario_id)` | Un perfil de prestador por persona |

### Triggers

|             Nombre              |        Evento         | Momento  | Nivel |                         Regla                          |        Origen        |
| :-----------------------------: | :-------------------: | :------: | :---: | :----------------------------------------------------: | :------------------: |
| `trg_perfilprestador_un_perfil` |       `INSERT`        | `BEFORE` | `ROW` | La persona no acumula perfil de turista y de prestador | [`RF-S-26`][rf-s-26] |
| `trg_perfilprestador_historial` | `UPDATE OF estado_id` | `AFTER`  | `ROW` |       Inserta la fila en `transicion_prestador`        | [`RF-S-10`][rf-s-10] |

### Índices

|             Nombre             |                     Definición                     |            Propósito            |
| :----------------------------: | :------------------------------------------------: | :-----------------------------: |
| `idx_perfilprestador_busqueda` | `(estado_id, promedio_valoracion DESC NULLS LAST)` | Listado ordenado por reputación |

### Notas de diseño

`promedio_valoracion` admite nulo y `total_resenas` no. Un prestador sin
valoraciones no tiene promedio cero: no tiene promedio. La diferencia importa en
el listado, donde `NULLS LAST` deja abajo a los prestadores nuevos en lugar de
hundirlos como si tuvieran la peor nota.

Los dos son datos derivados que mantiene un disparador sobre `resena`, por
[`D-23`][d-23]. Se aceptan como denormalización porque se consultan en cada
búsqueda de prestadores y en cada tablero de postulaciones; mantenerlos desde la
base garantiza que ninguna vía de escritura los deje obsoletos. El `CHECK` de
coherencia es lo que delata un disparador roto.

---

## `estado_prestador`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma dos: `es_visible` y `acepta_reservas`.

|     Código      | `es_visible` | `acepta_reservas` |
| :-------------: | :----------: | :---------------: |
| `sin_acreditar` |      no      |        no         |
|  `en_revision`  |      no      |        no         |
|    `activo`     |    **sí**    |      **sí**       |
|  `suspendido`   |      no      |        no         |

`suspendido` conserva el acceso a la aplicación. El prestador entra para
regularizar sus papeles y consultar su historial, pero no aparece en búsquedas ni
recibe contrataciones nuevas. Por eso el estado del prestador no es el estado de
su cuenta: son dos máquinas distintas sobre la misma persona.

---

## `acreditacion`

El documento que habilita a un prestador, con sus fechas de vigencia.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** una o dos por prestador
- **Origen:**
  > - [`RF-P-02`][rf-p-02]
  > - [`RF-S-13`][rf-s-13]

### Columnas

|         Campo          |     Tipo      | Nulo | Predeterminado |              Descripción              |
| :--------------------: | :-----------: | :--: | :------------: | :-----------------------------------: |
| `perfil_prestador_id`  |    `uuid`     |  no  |                |        Llave foránea `CASCADE`        |
| `tipo_acreditacion_id` |    `uuid`     |  no  |                |       Llave foránea `RESTRICT`        |
|      `estado_id`       |    `uuid`     |  no  |                | Llave foránea a `estado_acreditacion` |
|        `numero`        |   `varchar`   |  no  |      `''`      |     Folio declarado del documento     |
|      `archivo_id`      |   `varchar`   |  no  |                |    Referencia en el almacenamiento    |
|      `emitida_el`      |    `date`     |  no  |                |                                       |
|       `vence_el`       |    `date`     |  sí  |                | Nulo si el tipo no exige vencimiento  |
|      `cargada_en`      | `timestamptz` |  no  |    `now()`     |      Ordena la cola de revisión       |

### Constraints

```postgresql
CONSTRAINT chk_acreditacion_vigencia_orden
CHECK (
  vence_el IS NULL
  OR
  vence_el > emitida_el
)
```

### Unicidad

|           Nombre           |                             Definición                              |             Propósito             |
| :------------------------: | :-----------------------------------------------------------------: | :-------------------------------: |
| `unq_acreditacion_vigente` | `(perfil_prestador_id, tipo_acreditacion_id) WHERE estado acredita` | Una acreditación vigente por tipo |

### Triggers

|                 Nombre                 |        Evento         | Momento  | Nivel |                          Regla                          |        Origen        |
| :------------------------------------: | :-------------------: | :------: | :---: | :-----------------------------------------------------: | :------------------: |
| `trg_acreditacion_vencimiento_exigido` |  `INSERT`, `UPDATE`   | `BEFORE` | `ROW` | Exige `vence_el` si el tipo declara `exige_vencimiento` | [`RF-S-13`][rf-s-13] |
|      `trg_acreditacion_suspende`       | `UPDATE OF estado_id` | `AFTER`  | `ROW` |     Al vencer la última vigente, suspende el perfil     | [`RF-P-02`][rf-p-02] |

### Índices

|             Nombre             |               Definición                |                   Propósito                    |
| :----------------------------: | :-------------------------------------: | :--------------------------------------------: |
| `idx_acreditacion_vencimiento` | `(vence_el) WHERE vence_el IS NOT NULL` |     El barrido diario que vence documentos     |
|    `idx_acreditacion_cola`     |             `(cargada_en)`              | [Cola de verificación por antigüedad][rf-b-01] |

### Notas de diseño

`archivo_id` es la referencia al documento en el almacenamiento, no el documento.
La base guarda metadatos y el archivo vive fuera: un PDF de diez megabytes por
prestador convertiría cualquier respaldo en un problema.

El paso a suspensión cuando vence la última acreditación no lo hace la
aplicación. Un proceso programado compara `vence_el` contra la fecha del
servidor y escribe la transición; si dependiera de que alguien abra el portal, un
prestador con licencia vencida seguiría recibiendo reservas.

Toda la carga ocurre desde el dispositivo. [`RF-P-20`][rf-p-20] es explícito en
que no existe un portal web alternativo, lo que hace que `archivo_id` provenga
casi siempre de una fotografía del documento y no de un escaneo.

---

## `estado_acreditacion`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 4 filas

A las cinco columnas comunes suma una: `acredita`.

|    Código     | `acredita` | `es_terminal` |
| :-----------: | :--------: | :-----------: |
|   `cargada`   |     no     |      no       |
| `en_revision` |     no     |      no       |
|  `aprobada`   |   **sí**   |      no       |
|  `rechazada`  |     no     |    **sí**     |
|   `vencida`   |     no     |    **sí**     |

Solo `aprobada` acredita, y ni `vencida` ni `rechazada` se reabren: en ambos
casos el prestador carga un documento nuevo, que genera otra fila y otra
verificación. Es lo que conserva cuántas veces se intentó y por qué falló cada
vez.

---

## `prestador_idioma` y `prestador_servicio`

Qué habla y qué ofrece.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** unas pocas filas por prestador
- **Origen:**
  > - [`RF-P-01`][rf-p-01]

### Columnas

|        Tabla         |               Campos propios                |
| :------------------: | :-----------------------------------------: |
|  `prestador_idioma`  | `perfil_prestador_id`, `idioma_id`, `nivel` |
| `prestador_servicio` |  `perfil_prestador_id`, `tipo_servicio_id`  |

### Unicidad

|           Nombre            |                Definición                 |              Propósito              |
| :-------------------------: | :---------------------------------------: | :---------------------------------: |
|  `unq_prestadoridioma_par`  |    `(perfil_prestador_id, idioma_id)`     |  Un idioma no se declara dos veces  |
| `unq_prestadorservicio_par` | `(perfil_prestador_id, tipo_servicio_id)` | Un servicio no se declara dos veces |

### Notas de diseño

`prestador_servicio` es lo que consulta [`Servicios`][servicios] para impedir que
un traductor publique catálogo. La regla no vive en el perfil como un booleano
porque una misma persona puede ofrecer ambos servicios, y entonces la pregunta
«¿es guía?» no tiene respuesta única.

El idioma del prestador se compara contra el que exige la convocatoria, y por eso
es una tabla y no una cadena: el tablero filtra por él.

---

## Fuera de este módulo

|           Cosa           |         Dónde vive         |                        Por qué no aquí                         |
| :----------------------: | :------------------------: | :------------------------------------------------------------: |
|        `usuario`         |  [`Identidad`][identidad]  |          El acceso es idéntico para todos los papeles          |
| `solicitud_verificacion` | [`Moderación`][moderacion] | La acreditación entra a su cola, pero el expediente es de allí |
|         `resena`         | [`Reputación`][reputacion] |          Alimenta el promedio que se materializa aquí          |
|    `cuenta_bancaria`     |   [`Finanzas`][finanzas]   |              Cuelga del prestador, pero es dinero              |
|  `movimiento_insignia`   |  [`Insignias`][insignias]  |           Alimenta el nivel que se materializa aquí            |

[auditoria]: ../convenciones.md#auditoria
[d-01]: ../decisiones.md#d-01
[d-23]: ../decisiones.md#d-23
[finanzas]: finanzas.md
[identidad]: identidad.md
[insignias]: insignias.md
[moderacion]: moderacion.md
[reputacion]: reputacion.md
[servicios]: servicios.md
[rf-b-01]: ../../requerimientos/funcionales/backoffice.md#rf-b-01
[rf-p-01]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-01
[rf-p-02]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-02
[rf-p-20]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-20
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
[rf-s-13]: ../../requerimientos/funcionales/plataforma.md#rf-s-13
[rf-s-26]: ../../requerimientos/funcionales/plataforma.md#rf-s-26
[rf-t-23]: ../../requerimientos/funcionales/app-turista.md#rf-t-23
[rf-t-24]: ../../requerimientos/funcionales/app-turista.md#rf-t-24
[rf-t-25]: ../../requerimientos/funcionales/app-turista.md#rf-t-25
