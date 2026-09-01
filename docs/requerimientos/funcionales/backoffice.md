---
icon: lucide/shield-check
---

# Backoffice

La superficie del equipo interno de K'plan. Concentra las dos funciones que
sostienen la confianza del ecosistema: verificar que quien se presenta como guía
o traductor lo es de verdad, y sancionar a quien rompe las reglas. Ambas son
decisiones humanas y ninguna se automatiza, porque las dos determinan si un
turista puede confiar en la persona con la que va a recorrer una ciudad.

- **Módulos:** 2
- **Total:** 10

---

## Verificación

### RF-B-01

> **Cola de verificación**

El backoffice presenta la lista de prestadores que cargaron credenciales y
esperan resolución, ordenada por antigüedad de envío. El orden de llegada es el
criterio de atención, de modo que ninguna solicitud quede indefinidamente al
final por falta de un criterio explícito.

### RF-B-02

> **Visor de credenciales**

El moderador abre el documento cargado dentro del propio panel, junto a los datos
declarados por el prestador, para contrastarlos sin descargar el archivo ni salir
de la herramienta.

### RF-B-03

> **Aprobación del prestador**

Verificado el documento, el moderador aprueba el perfil. La aprobación lo hace
visible en las búsquedas, habilita su catálogo y le permite recibir solicitudes,
y dispara la notificación de bienvenida. Es la única vía por la que un prestador
pasa a ser contratable.

### RF-B-04

> **Rechazo con motivo**

Si el documento está ilegible, vencido o no corresponde, el moderador lo rechaza
indicando el motivo. El motivo es obligatorio y se comunica al prestador, porque
un rechazo sin causa explicada obliga a reintentar a ciegas. El perfil permanece
oculto hasta que se subsane.

### RF-B-05

> **Verificación de organizaciones**

Comercios, alcaldías e instituciones culturales se registran por su cuenta y
llegan a la misma cola, con la misma mecánica de aprobación o rechazo motivado.
Ninguna existe para el turista antes de la aprobación: el comercio no aparece en
el mapa, la institución no puede programar eventos y la alcaldía no puede
publicar circuitos.

Lo que cambia entre las tres es el documento que se exige y la severidad de la
revisión. Aprobar una alcaldía falsa entrega el sello de contenido oficial de una
ciudad entera, así que su verificación no se resuelve solo con los datos del
formulario.

---

## Moderación

### RF-B-06

> **Tablero de reportes**

Un tablero reúne los reportes emitidos por la comunidad: quejas de un turista
sobre un prestador, de un prestador sobre un turista, reseñas impugnadas y
alertas de conducta en las salas de chat. Cada caso muestra su gravedad, su
estado de atención y el material que lo respalda.

### RF-B-07

> **Suspensión temporal**

Ante una infracción leve verificada, el supervisor suspende el acceso del usuario
por una cantidad determinada de días, dejando registrado el motivo interno, que
es obligatorio. La suspensión revoca de inmediato las sesiones activas del
infractor y sus intentos de acceso posteriores devuelven los días restantes.

### RF-B-08

> **Expulsión permanente**

Ante fraude, acoso o reincidencia en la evasión de la plataforma, el supervisor
expulsa al usuario de forma definitiva. Por su carácter irreversible, la acción
exige una confirmación adicional y una razón detallada, y registra el dispositivo
de origen para impedir que la misma persona vuelva a crear una cuenta desde él.

### RF-B-09

> **Efecto de la expulsión sobre los servicios comprometidos**

La expulsión cancela de forma inmediata los servicios futuros que el usuario
tuviera acordados y abre los reembolsos que correspondan. La contraparte es
notificada de la cancelación sin conocer la sanción que la originó.

### RF-B-10

> **Historial de sanciones**

Cada usuario acumula un historial consultable de sanciones con su fecha, tipo,
duración, motivo y responsable. Es la base sobre la que se evalúa la reincidencia
y la única forma de justificar por qué una infracción similar recibió una sanción
distinta en dos momentos.
