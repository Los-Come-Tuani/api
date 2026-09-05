---
icon: lucide/key-round
---

# Identidad y acceso

Once tablas. `usuario` es la de más referencias entrantes del esquema y `sesion`
la que más se escribe. Lo que aquí se decida mal se paga en producción: una
sesión que no se puede revocar deja dentro a un expulsado, y un intento fallido
atado al usuario delata qué correos existen.

Una sola tabla de usuario para todos los papeles, por [`D-01`][d-01]. La
identidad, las credenciales, la sesión y las sanciones son idénticas sea el
titular un turista, un guía o un operador de alcaldía; lo que los diferencia vive
en [`Perfiles`][perfiles].

## Requerimientos cubiertos

- [`RF-S-05`][rf-s-05]
- [`RF-S-06`][rf-s-06]
- [`RF-S-07`][rf-s-07]
- [`RF-S-10`][rf-s-10]
- [`RF-S-11`][rf-s-11]
- [`RF-S-26`][rf-s-26]
- [`RF-B-08`][rf-b-08]

---

## `usuario`

La persona registrada, sea cual sea su papel. Sustituye al `ApiUser` del
andamiaje.

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** decenas de miles en el piloto
- **Origen:**
  > - [`RF-S-05`][rf-s-05]
  > - [`RF-S-10`][rf-s-10]

### Columnas

|       Campo        |     Tipo      | Nulo | Predeterminado |                    Descripción                     |
| :----------------: | :-----------: | :--: | :------------: | :------------------------------------------------: |
|      `nombre`      |   `varchar`   |  no  |                |    Nombre de pila; es lo único que ven terceros    |
|     `apellido`     |   `varchar`   |  no  |      `''`      |  Vacío cuando el proveedor federado no lo entrega  |
|      `correo`      |   `citext`    |  no  |                | Identificador de acceso; inmutable desde el perfil |
| `hash_contrasena`  |   `varchar`   |  no  |      `''`      |      Vacío cuando la cuenta es solo federada       |
| `fecha_nacimiento` |    `date`     |  no  |                |       Solo para comprobar la mayoría de edad       |
|    `estado_id`     |    `uuid`     |  no  |                |          Llave foránea a `estado_usuario`          |
|  `verificado_en`   | `timestamptz` |  sí  |                |       Nulo mientras el correo no se confirma       |
|    `creado_en`     | `timestamptz` |  no  |    `now()`     |              Congelada por disparador              |

### Llaves foráneas

|   Columna   |    Referencia    | `ON DELETE` |            Notas             |
| :---------: | :--------------: | :---------: | :--------------------------: |
| `estado_id` | `estado_usuario` | `RESTRICT`  | Un estado en uso no se borra |

### Constraints

```postgresql
CONSTRAINT chk_usuario_mayoredad
CHECK (fecha_nacimiento <= CURRENT_DATE - INTERVAL '18 years')
```

### Unicidad

|        Nombre        | Definición |      Propósito       |
| :------------------: | :--------: | :------------------: |
| `unq_usuario_correo` | `(correo)` | El correo identifica |

### Triggers

|             Nombre              |        Evento         |      Momento      | Nivel |                        Regla                         |        Origen        |
| :-----------------------------: | :-------------------: | :---------------: | :---: | :--------------------------------------------------: | :------------------: |
| `trg_usuario_readonly_creadoen` |       `UPDATE`        |     `BEFORE`      | `ROW` |             `creado_en` no se reescribe              |      Convención      |
|    `trg_usuario_credencial`     |  `INSERT`, `UPDATE`   | `AFTER`, diferido | `ROW` | Tiene contraseña o identidad federada, nunca ninguna | [`RF-S-05`][rf-s-05] |
|     `trg_usuario_unperfil`      | `INSERT` en perfiles  |     `BEFORE`      | `ROW` |     No acumula perfil de turista y de prestador      | [`RF-S-26`][rf-s-26] |
|   `trg_usuario_revocasesion`    | `UPDATE OF estado_id` |      `AFTER`      | `ROW` | Si el estado nuevo revoca, marca sus sesiones vivas  | [`RF-S-10`][rf-s-10] |

### Índices

|        Nombre        |                                  Definición                                   |             Propósito              |
| :------------------: | :---------------------------------------------------------------------------: | :--------------------------------: |
| `idx_usuario_estado` |                                 `(estado_id)`                                 | Listados del backoffice por estado |
| `gin_usuario_nombre` | `GIN (upper(immutable_unaccent(nombre \|\| ' ' \|\| apellido)) gin_trgm_ops)` |    Búsqueda por nombre parcial     |

### Notas de diseño

«Tiene contraseña o identidad federada» es un disparador diferido y no un
`CHECK` porque mira otra tabla: al insertar el usuario todavía no existe la fila
de `identidad_externa`, y la comprobación tiene que esperar al cierre de la
transacción.

La palabra «cuenta» que usan los requerimientos no designa otra entidad: nombra a
esta misma fila vista desde el lado del acceso.

La mayoría de edad sí es un `CHECK` aunque dependa de la fecha actual, y es la
excepción que confirma la regla de [`Convenciones`][convenciones-invariantes]:
quien cumple dieciocho años nunca vuelve a incumplirla, así que la restricción no
puede invalidar una fila que antes era válida.

---

## `estado_usuario`

Catálogo del ciclo de vida de la cuenta. Los booleanos son las preguntas que el
sistema hace sobre el estado, por [`D-11`][d-11].

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** 5 filas

A las cinco columnas comunes suma dos: `permite_operar` y `revoca_sesion`.

|    Código    | `permite_operar` | `revoca_sesion` | `es_terminal` |
| :----------: | :--------------: | :-------------: | :-----------: |
| `pendiente`  |        no        |       no        |      no       |
|   `activa`   |      **sí**      |       no        |      no       |
| `suspendida` |        no        |     **sí**      |      no       |
| `expulsada`  |        no        |     **sí**      |    **sí**     |
|  `en_baja`   |        no        |     **sí**      |      no       |

---

## `sesion`

Una fila por par de credenciales emitido. Es a la vez el registro de sesión y la
lista de revocación: no hay tabla aparte.

- **Régimen:** [Mutable protegida][auditoria]
- **Volumen estimado:** cientos de miles al mes, se purga
- **Origen:**
  > - [`RF-S-07`][rf-s-07]

### Columnas

|        Campo        |     Tipo      | Nulo | Predeterminado |               Descripción                |
| :-----------------: | :-----------: | :--: | :------------: | :--------------------------------------: |
|    `usuario_id`     |    `uuid`     |  no  |                |         Llave foránea `CASCADE`          |
|  `dispositivo_id`   |    `uuid`     |  no  |                |         Llave foránea `RESTRICT`         |
|   `token_acceso`    |    `uuid`     |  no  |                | Identificador de la credencial de acceso |
| `token_renovacion`  |    `uuid`     |  no  |                |    Identificador de la de renovación     |
|     `ip_origen`     |    `inet`     |  no  |                |     Dirección desde la que se emitió     |
|    `emitida_en`     | `timestamptz` |  no  |    `now()`     |                                          |
|     `expira_en`     | `timestamptz` |  no  |                |   Expiración natural de la renovación    |
|    `revocada_en`    | `timestamptz` |  sí  |                |      Nulo mientras la sesión sirve       |
| `motivo_revocacion` |   `varchar`   |  no  |      `''`      | `cierre`, `rotacion`, `sancion` o `baja` |

### Constraints

```postgresql
CONSTRAINT chk_sesion_expira
CHECK (expira_en > emitida_en)

CONSTRAINT chk_sesion_revocada
CHECK (
  revocada_en IS NULL
  OR
  revocada_en >= emitida_en
)

CONSTRAINT chk_sesion_motivo
CHECK ((revocada_en IS NULL) = (motivo_revocacion = ''))
```

### Unicidad

|         Nombre          |      Definición      |               Propósito                |
| :---------------------: | :------------------: | :------------------------------------: |
|   `unq_sesion_acceso`   |   `(token_acceso)`   | Validar la credencial en cada petición |
| `unq_sesion_renovacion` | `(token_renovacion)` |      Detectar el reuso al renovar      |

### Triggers

|            Nombre            |         Evento          | Momento  | Nivel |                  Regla                   |        Origen        |
| :--------------------------: | :---------------------: | :------: | :---: | :--------------------------------------: | :------------------: |
| `trg_sesion_readonly_tokens` |        `UPDATE`         | `BEFORE` | `ROW` | Los dos identificadores no se reescriben | [`RF-S-07`][rf-s-07] |
|    `trg_sesion_norevive`     | `UPDATE OF revocada_en` | `BEFORE` | `ROW` |      `revocada_en` no vuelve a nulo      | [`RF-S-07`][rf-s-07] |

### Índices

|        Nombre        |                Definición                |                   Propósito                    |
| :------------------: | :--------------------------------------: | :--------------------------------------------: |
|  `idx_sesion_vivas`  | `(usuario_id) WHERE revocada_en IS NULL` | Revocar de golpe las de una persona sancionada |
| `brin_sesion_expira` |            `BRIN (expira_en)`            |   La purga recorre rangos, no filas sueltas    |

### Notas de diseño

Una credencial firmada es autocontenida y no puede borrarse una vez emitida. Para
que [`RF-S-07`][rf-s-07] surta efecto inmediato, cada credencial deja su
identificador en esta lista con su fecha de expiración natural, y la lista se
purga cuando las credenciales vencen por sí solas.

La tercera restricción ata revocación y motivo: no existe una sesión revocada sin
causa ni un motivo escrito sobre una sesión viva.

Renovar consume la fila —escribe `revocada_en` con motivo `rotacion`— e inserta
otra. Presentar dos veces la misma credencial de renovación falla la segunda, y
eso convierte el robo en un incidente detectable en lugar de en un acceso
permanente ([`D-06`][d-06]).

---

## `intento_acceso` y `bloqueo_acceso`

Cada intento de autenticación, exitoso o no. **No referencian a `usuario`.**

- **Régimen:** [De solo inserción][auditoria] y [mutable protegida][auditoria]
- **Volumen estimado:** millones al año
- **Origen:**
  > - [`RF-S-06`][rf-s-06]

### Columnas de `intento_acceso`

|      Campo       |     Tipo      | Nulo | Predeterminado |                  Descripción                  |
| :--------------: | :-----------: | :--: | :------------: | :-------------------------------------------: |
| `identificador`  |   `varchar`   |  no  |                | El correo **tal como se tecleó**, exista o no |
| `dispositivo_id` |    `uuid`     |  sí  |                |     Nulo si el cliente no declara huella      |
|   `ip_origen`    |    `inet`     |  no  |                |                                               |
|    `exitoso`     |   `boolean`   |  no  |                |                                               |
|  `ocurrido_en`   | `timestamptz` |  no  |    `now()`     |                                               |

### Columnas de `bloqueo_acceso`

|        Campo        |     Tipo      | Nulo | Predeterminado |               Descripción               |
| :-----------------: | :-----------: | :--: | :------------: | :-------------------------------------: |
|   `identificador`   |   `varchar`   |  no  |                | **Único**: un bloqueo por identificador |
|    `intento_id`     |    `uuid`     |  no  |                |        El intento que lo disparó        |
| `intentos_contados` |  `smallint`   |  no  |                |                                         |
|  `bloqueado_hasta`  | `timestamptz` |  no  |                |                                         |

### Índices

|           Nombre            |                      Definición                       |                     Propósito                     |
| :-------------------------: | :---------------------------------------------------: | :-----------------------------------------------: |
| `idx_intento_identificador` | `(identificador, ocurrido_en DESC) WHERE NOT exitoso` | Contar los fallidos de los últimos quince minutos |
|   `brin_intento_ocurrido`   |                 `BRIN (ocurrido_en)`                  |              La purga por antigüedad              |
| `unq_bloqueo_identificador` |               `UNIQUE (identificador)`                |    Un solo bloqueo por identificador tecleado     |

### Notas de diseño

Si `identificador` fuera llave foránea, un correo inexistente no tendría dónde
registrarse: el bloqueo por cinco intentos solo funcionaría para cuentas reales y
eso **revelaría cuáles existen**, que es justo lo que [`RF-S-06`][rf-s-06]
prohíbe. El registro guarda la cadena tal como llegó ([`D-08`][d-08]).

---

## `segundo_factor` y `codigo_recuperacion`

- **Régimen:** [Mutable rastreada][auditoria]
- **Volumen estimado:** una o dos filas por cuenta con factor
- **Origen:**
  > - [`RF-B-08`][rf-b-08]

### Columnas de `segundo_factor`

|       Campo       |     Tipo      | Nulo | Predeterminado |                 Descripción                  |
| :---------------: | :-----------: | :--: | :------------: | :------------------------------------------: |
|   `usuario_id`    |    `uuid`     |  no  |                |           Llave foránea `CASCADE`            |
|      `tipo`       |   `varchar`   |  no  |                |           `totp`, `sms` o `correo`           |
| `secreto_cifrado` |    `bytea`    |  no  |                | Cifrado en la aplicación, **nunca en claro** |
|  `llave_cifrado`  |   `varchar`   |  no  |                |   Qué llave lo cifró, para poder rotarlas    |
|  `confirmado_en`  | `timestamptz` |  sí  |                | Nulo mientras no se valida el primer código  |
|   `revocado_en`   | `timestamptz` |  sí  |                |          Nulo mientras está en uso           |

### Columnas de `codigo_recuperacion`

|        Campo        |     Tipo      | Nulo | Predeterminado |       Descripción       |
| :-----------------: | :-----------: | :--: | :------------: | :---------------------: |
| `segundo_factor_id` |    `uuid`     |  no  |                | Llave foránea `CASCADE` |
|    `hash_codigo`    |   `varchar`   |  no  |                | **Hash**, no el código  |
|   `consumido_en`    | `timestamptz` |  sí  |                | Nulo mientras no se usa |

### Unicidad

|       Nombre        |                               Definición                               |                   Propósito                    |
| :-----------------: | :--------------------------------------------------------------------: | :--------------------------------------------: |
| `unq_factor_activo` | `(usuario_id) WHERE confirmado_en IS NOT NULL AND revocado_en IS NULL` | Un solo factor activo, conservando los rotados |

### Notas de diseño

Es una entidad y no una bandera booleana, por [`D-04`][d-04]. Una cuenta puede
tener más de un factor, cada uno con su tipo, su secreto y su estado de
confirmación; una columna impediría rotar un factor sin perder el anterior y
dejaría sin lugar los códigos de recuperación.

`secreto_cifrado` es lo único reversible del módulo —hay que poder generar el
código de seis dígitos— y por eso lleva `llave_cifrado`: un volcado de la base no
basta para suplantar el factor si la llave vive fuera ([`D-09`][d-09]).

`codigo_recuperacion` guarda hash y no el código. Se emiten diez de un solo uso
al confirmar el factor y son la única salida cuando el usuario pierde el
dispositivo.

[`RF-B-08`][rf-b-08] exige el segundo factor para expulsar a un usuario, que es
la acción menos reversible del sistema: una contraseña filtrada no puede bastar
para ejecutarla.

---

## Resto del módulo

|         Tabla         |                     Propósito                     |      Régimen      |                                   Regla que la define                                   |
| :-------------------: | :-----------------------------------------------: | :---------------: | :-------------------------------------------------------------------------------------: |
|  `identidad_externa`  |         Vínculo con el proveedor federado         | Mutable rastreada |  `UNIQUE (proveedor, sujeto_externo)`: una cuenta externa no se vincula a dos usuarios  |
| `codigo_verificacion` | Códigos de un solo uso para correo y recuperación | De solo inserción |            Guarda hash y `destino` congelado; `intentos` bloquea a los cinco            |
|     `dispositivo`     |           Aparato desde el que se opera           | Mutable rastreada | `UNIQUE (huella)`; sobrevive al usuario porque sostiene el veto de [`RF-B-08`][rf-b-08] |
|   `solicitud_baja`    |  Los treinta días entre la petición y el borrado  | Mutable rastreada |     `efectiva_en = solicitada_en + 30 días`; se cancela escribiendo `cancelada_en`      |

`dispositivo` es una entidad y no una columna por [`D-07`][d-07]:
[`RF-B-08`][rf-b-08] veta la creación de cuentas nuevas desde el aparato del
expulsado, y ese veto necesita algo a lo que apuntar. Sin él la expulsión solo
alcanza a la cuenta, y crear otra cuesta un minuto.

---

## Fuera de este módulo

|                 Cosa                  |             Dónde vive             |                    Por qué no aquí                     |
| :-----------------------------------: | :--------------------------------: | :----------------------------------------------------: |
| `perfil_turista` y `perfil_prestador` |       [`Perfiles`][perfiles]       |         Los datos que solo aplican a un papel          |
|           `asignacion_rol`            |          [`Roles`][roles]          |         Qué puede hacer la cuenta y sobre qué          |
|               `sancion`               |     [`Moderación`][moderacion]     | Es la causa; el estado de la cuenta es su consecuencia |
|         `token_notificacion`          | [`Notificaciones`][notificaciones] |   Cuelga del dispositivo, pero es un canal de envío    |

[auditoria]: ../convenciones.md#auditoria
[convenciones-invariantes]: ../convenciones.md#invariantes
[d-01]: ../decisiones.md#d-01
[d-04]: ../decisiones.md#d-04
[d-06]: ../decisiones.md#d-06
[d-07]: ../decisiones.md#d-07
[d-08]: ../decisiones.md#d-08
[d-09]: ../decisiones.md#d-09
[d-11]: ../decisiones.md#d-11
[moderacion]: moderacion.md
[notificaciones]: notificaciones.md
[perfiles]: perfiles.md
[roles]: roles.md
[rf-b-08]: ../../requerimientos/funcionales/backoffice.md#rf-b-08
[rf-s-05]: ../../requerimientos/funcionales/plataforma.md#rf-s-05
[rf-s-06]: ../../requerimientos/funcionales/plataforma.md#rf-s-06
[rf-s-07]: ../../requerimientos/funcionales/plataforma.md#rf-s-07
[rf-s-10]: ../../requerimientos/funcionales/plataforma.md#rf-s-10
[rf-s-11]: ../../requerimientos/funcionales/plataforma.md#rf-s-11
[rf-s-26]: ../../requerimientos/funcionales/plataforma.md#rf-s-26
