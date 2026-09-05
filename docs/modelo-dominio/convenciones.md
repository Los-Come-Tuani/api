---
icon: lucide/ruler
---

# Convenciones

Reglas que aplican a todas las tablas. Existen para que una tabla nueva se
escriba sin volver a discutir cómo se nombra, qué tipo lleva una columna o cuándo
corresponde un disparador.

---

## Idioma

Tablas y columnas en **español**, en minúsculas y con guion bajo. El negocio se
habla en español: circuito, parada, insignia y canje son las palabras que usan
las alcaldías y los comercios, y traducirlas obliga a convertir en cada
conversación.

!!! warning "Consecuencia sobre el andamiaje"

    El código actual está en inglés: `ApiUser`, `first_name`, `created_at`,
    `is_active`. Con esta convención, `ApiUser` pasa a ser `usuario` y sus
    columnas se traducen. Es una migración de renombrado que hay que hacer antes
    de escribir la primera tabla del dominio, no después.

---

## Cómo se nombra una tabla

| Caso                                    | Regla                   | Ejemplo                                                |
| --------------------------------------- | ----------------------- | ------------------------------------------------------ |
| Entidad con nombre propio en el negocio | Ese nombre, en singular | `circuito_oficial`, `insignia`, `cupon`                |
| Tabla que solo une dos entidades        | `<padre>_<hijo>`        | `rol_permiso`, `punto_pilar`, `itinerario_circuito`    |
| Tabla hija con datos propios            | `<padre>_<que_guarda>`  | `comercio_horario`, `mensaje_adjunto`, `recorrido_dia` |
| Catálogo de clasificación               | `tipo_<que_clasifica>`  | `tipo_negocio`, `tipo_acreditacion`, `tipo_aviso`      |
| Catálogo de estados                     | `estado_<entidad>`      | `estado_usuario`, `estado_reserva`                     |
| Historial de cambios                    | `<entidad>_cambio`      | `parametro_cambio`, `cuenta_bancaria_cambio`           |

Los nombres de entidad no se abrevian. El ahorro de teclas se paga cada vez que
alguien nuevo lee el esquema.

### _¿Por qué `<padre>_<hijo>` y no al revés?\_

Porque ordena alfabéticamente por dueño. En un esquema de noventa tablas,
`circuito_oficial`, `circuito_parada` y `circuito_foto` quedan juntas con su
padre. Con el orden inverso quedan dispersas por todo el esquema
y nadie encuentra qué cuelga de qué.

---

## Palabras reservadas

Tres palabras significan una sola cosa en todo el documento. Se reservan porque
antes designaban dos y eso hacía ilegible el modelo.

| Palabra        | Significa                                           | No significa                                               |
| -------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| **credencial** | El par de tokens firmados que sostienen una sesión  | El documento del INTUR: eso es una **acreditación**        |
| **cambio**     | Una modificación registrada de un valor anterior    | La conversión entre monedas: eso es una **tasa de cambio** |
| **recorrido**  | El producto que publica un guía, con tarifa y cupos | Lo que el turista arma: eso es un **itinerario**           |

---

## Tipos

| Naturaleza     | Tipo                                       | Regla                                                                          |
| -------------- | ------------------------------------------ | ------------------------------------------------------------------------------ |
| Identificador  | `uuid`                                     | Ordenable por tiempo de generación, inmutable                                  |
| Texto          | `varchar` sin límite, `text` para párrafos | El límite se declara como restricción solo si es regla de negocio              |
| Correo         | `citext`                                   | La comparación es insensible a mayúsculas por definición                       |
| Dinero         | `numeric(12,2)`                            | Nunca coma flotante                                                            |
| Instante       | `timestamptz`                              | Almacenamiento en tiempo universal coordinado                                  |
| Fecha sin hora | `date`                                     | Solo cuando la hora carece de sentido, como el vencimiento de una acreditación |
| Coordenada     | `numeric(9,6)`                             | Latitud y longitud separadas, con rango verificado                             |
| Clasificación  | `uuid` a catálogo                          | Nunca cadena libre                                                             |

### _¿Por qué `numeric` y no coma flotante para el dinero?_

Porque el saldo de un prestador se construye sumando movimientos. Con coma
flotante, sumar veinte comisiones y restar un retiro deja un residuo que no es
cero, y el prestador ve fracciones de centavo que no puede retirar ni explicar.

---

## Nulabilidad

Un valor nulo significa **no aplica**, nunca «vacío» ni «todavía no». El texto
opcional usa cadena vacía con valor por defecto, que es lo que ya hace el
andamiaje, porque permite indexar y comparar sin arrastrar lógica de tres estados
a cada consulta.

Las fechas son la excepción deliberada: `verificado_en`, `revocada_en` y
`consumido_en` son nulas mientras el hecho no ocurrió, y esa nulidad **es** la
información.

---

## Llaves foráneas

| Relación                                                | ON DELETE  | Ejemplo                                           |
| ------------------------------------------------------- | ---------- | ------------------------------------------------- |
| El hijo no tiene sentido sin el padre y no es histórico | `CASCADE`  | `circuito_parada` respecto del circuito           |
| El hijo es histórico o contable                         | `RESTRICT` | `reserva` respecto del prestador                  |
| El hijo sobrevive y la referencia era trazabilidad      | `SET NULL` | `itinerario_parada` respecto del punto de interés |
| Catálogo referenciado por operación                     | `RESTRICT` | `ciudad` respecto de `comercio`                   |

---

## Invariantes

| Forma de la regla                          | Mecanismo            | Ejemplo                                                 |
| ------------------------------------------ | -------------------- | ------------------------------------------------------- |
| Depende de una sola fila                   | `CHECK`              | La tarifa es mayor que cero                             |
| Unicidad incondicional                     | `UNIQUE`             | El código del cupón no se repite                        |
| Unicidad bajo condición                    | Índice único parcial | Un solo segundo factor confirmado por usuario           |
| Dos filas no pueden solaparse en el tiempo | `EXCLUDE`            | Dos reservas del mismo guía en el mismo horario         |
| La regla cruza filas o tablas              | Disparador           | El canje no deja el saldo en negativo                   |
| La regla depende del futuro                | No es invariante     | La fecha del evento debe ser futura **solo al crearlo** |

La última fila es la más olvidada. «La fecha debe ser futura» no puede ser una
restricción permanente: mañana el evento de hoy la violaría y la fila dejaría de
poder actualizarse.

Todo disparador cita el requerimiento que lo exige. Un disparador sin origen
citado es un disparador que hay que justificar o borrar.

---

## Auditoría

Cada ficha de tabla declara su régimen.

| Régimen               | Qué permite                                   | Tablas                                                                            |
| --------------------- | --------------------------------------------- | --------------------------------------------------------------------------------- |
| **De solo inserción** | Insertar. No actualizar ni eliminar           | Movimientos, visitas, transiciones, intentos de acceso, avisos emitidos, bitácora |
| **Mutable rastreada** | Todo, con historial completo de versiones     | Usuario, perfiles, comercios, circuitos, eventos, recorridos                      |
| **Mutable protegida** | Todo salvo columnas congeladas por disparador | Reserva y cupón, cuya tarifa y beneficio no se reescriben                         |

Ninguna tabla admite vaciado masivo: un disparador lo impide en la tabla base de
la que heredan todas.

---

## Formato de una ficha de tabla

Cada tabla del modelo físico se documenta con la misma estructura, en este orden:
propósito en una frase, régimen de auditoría y volumen estimado, columnas,
llaves foráneas, restricciones, disparadores e índices. Lo que no aplica se
omite; lo que aplica no se resume.
