---
icon: lucide/layers
---

# Plataforma

- **Módulos:** 6
- **Total:** 26

Comportamientos que ninguna superficie posee en exclusiva. La identidad, el
tiempo, la mensajería, las valoraciones y los avisos por cercanía atraviesan la
aplicación móvil y los portales por igual, y varios de ellos son bilaterales por
naturaleza: la misma sala de chat pertenece al turista y al prestador, y la
evaluación de un servicio se emite en dos direcciones. Documentarlos una sola vez
evita que dos superficies mantengan copias divergentes de la misma regla.

---

## Superficies

### RF-S-01

> **Superficies del sistema**

El sistema se compone de una aplicación móvil y cuatro superficies web. La
aplicación móvil atiende a los tres papeles que operan en la calle: el turista,
el guía turístico y el traductor. Las superficies web atienden a los que
administran una organización desde un escritorio: portal de alcaldías, portal de
comercios, portal de instituciones culturales y backoffice de administración.

El reparto no es arbitrario. Quien recorre la ciudad necesita ubicación, cámara y
avisos en segundo plano; quien administra una ficha o publica una agenda trabaja
con formularios largos, carga de archivos y tablas. Una credencial habilita
exactamente la superficie que corresponde a su rol: el sistema no ofrece una
vista única con secciones ocultas por permisos.

### RF-S-02

> **Operación desde teléfono en los portales web**

Los portales son responsivos y deben ser operables desde el teléfono del propio
usuario, sin aplicación nativa. La pantalla de validación de cupones del comercio
es el caso límite: se usa de pie, frente al cliente y con una sola mano, de modo
que el campo de código y el botón de confirmación deben quedar alcanzables sin
recolocar el dispositivo.

### RF-S-03

> **Zona horaria y reloj autoritativo**

Toda la lógica de vigencias, canjes, publicación de eventos y expiraciones se
resuelve en la zona `America/Managua`. El almacenamiento es en tiempo universal
coordinado. El reloj del servidor es la única fuente de verdad: la hora del
dispositivo se conserva como dato declarado cuando la aplicación opera sin
conexión, pero nunca determina si un cupón sigue vigente ni si un evento ya
venció.

### RF-S-04

> **Idioma de la interfaz**

El español es el idioma base del sistema. El turista declara un idioma preferido
mediante su código ISO y la interfaz lo respeta cuando existe traducción
disponible. El conjunto exacto de idiomas soportados no está definido: la
necesidad se deduce de que el segmento extranjero prioritario proviene de
Norteamérica y Europa, pero ninguna fuente los enumera.

---

## Identidad

### RF-S-05

> **Registro de cuenta**

Alta mediante correo electrónico y contraseña, o mediante identidad federada de
Google. Datos obligatorios: nombre, correo, nacionalidad y fecha de nacimiento.
La contraseña exige al menos ocho caracteres, una mayúscula y un número. Solo se
admiten personas mayores de dieciocho años, y la fecha de nacimiento se valida
contra esa condición en el momento del alta. El registro nativo exige verificar
el correo con un código de un solo uso antes de habilitar la cuenta; el alta
federada omite ese paso porque el proveedor ya entrega el correo verificado.

### RF-S-06

> **Inicio de sesión y bloqueo por intentos**

Tras cinco intentos fallidos consecutivos sobre el mismo identificador, el acceso
queda bloqueado durante quince minutos. El mensaje de error no distingue entre
correo inexistente y contraseña incorrecta, para no confirmar la existencia de
una cuenta a quien la está tanteando. Cada intento, exitoso o no, queda
registrado con el identificador tal como se tecleó.

### RF-S-07

> **Sesión y vigencia**

La sesión se sostiene con un par de credenciales firmadas: una de acceso, de vida
corta, y una de renovación, de vida más larga. Las vigencias vigentes son de tres
horas y de un día respectivamente. El sistema puede revocar ambas de forma
inmediata sin esperar su expiración natural, que es lo que permite expulsar a un
usuario sancionado del dispositivo en el que ya estaba dentro.

### RF-S-08

> **Enrutamiento por rol**

Al autenticarse, el sistema evalúa el rol de la cuenta y la conduce a la
superficie que le corresponde. Una cuenta no alcanza por dirección directa una
superficie ajena a su rol: el intento se resuelve como recurso inexistente y no
como acceso denegado, para no revelar qué superficies existen a quien las tantea.

### RF-S-09

> **Inmutabilidad del correo de registro**

El correo con el que se creó la cuenta no se modifica desde la pantalla de
perfil. Cambiarlo exige un procedimiento separado de verificación de identidad,
porque ese correo es el canal por el que se recuperan las credenciales y se
notifican las resoluciones de moderación.

### RF-S-10

> **Estados de la cuenta**

Pendiente de verificación, Activa, Suspendida temporalmente, Expulsada de forma
permanente y En proceso de baja. Solo Activa permite operar. Suspendida y
Expulsada revocan la sesión en curso e impiden autenticarse de nuevo; el intento
devuelve el motivo y, cuando la sanción es temporal, los días que restan. Cada
cambio de estado registra fecha, hora, responsable y motivo.

### RF-S-11

> **Baja de la cuenta**

El titular solicita la eliminación definitiva confirmando de forma explícita y
autenticándose de nuevo con su contraseña. La cuenta pasa a inactiva durante
treinta días antes de la destrucción de la información, plazo en el que la sesión
queda revocada y se envía confirmación por correo. La baja se rechaza mientras
existan servicios contratados y pagados que aún no se hayan prestado: primero hay
que concluirlos o cancelarlos.

### RF-S-26

> **Un solo papel por cuenta**

Una cuenta ejerce exactamente un papel. Quien se acredita como guía o traductor
no puede además viajar como turista con la misma cuenta, y quien opera un
comercio no acumula ningún otro perfil. Para ejercer dos papeles hacen falta dos
cuentas con correos distintos.

La restricción evita el conflicto de interés más obvio y mantiene una sola respuesta
a la pregunta «¿desde qué papel hizo esto esta persona?» en cada registro de auditoría.

---

## Contenido

### RF-S-12

> **Carga de imágenes**

Las imágenes que aporta el usuario se admiten en formato JPG o PNG con un tamaño
máximo de cinco megabytes por archivo. El sistema deriva una versión reducida
para los listados y conserva la original para la vista de detalle.

### RF-S-13

> **Carga de documentos de acreditación**

Las licencias del INTUR, los certificados de idiomas y los permisos que acompañan
a una solicitud se cargan en PDF legible de hasta diez megabytes. El documento
queda asociado a las fechas de emisión y de vencimiento declaradas, que son los
datos que gobiernan la vigencia del perfil al que acredita.

---

## Geolocalización

### RF-S-14

> **Permiso de ubicación**

Los avisos por cercanía y el registro de visita exigen que el dispositivo conceda
acceso a la ubicación incluso con la aplicación en segundo plano. Sin ese
permiso, la aplicación sigue siendo utilizable para explorar, planificar y
contratar, pero deja de emitir avisos y deja de acreditar visitas; el sistema
informa esa degradación en lugar de fallar en silencio.

### RF-S-15

> **Registro de visita por proximidad**

El sistema acredita la visita del turista a un comercio aliado o a un punto de
interés cuando el dispositivo reporta una distancia menor a cincuenta metros del
punto, y la visita acreditada otorga la insignia asociada. Un mismo
establecimiento no acredita más de una visita del mismo turista en veinticuatro
horas, de modo que la insignia mida exploración y no permanencia.

### RF-S-16

> **Avisos por cercanía**

Cuando el turista cruza la geocerca de un comercio aliado o de un evento vigente,
el sistema le entrega un aviso en el dispositivo. El radio es configurable y su
valor de partida es de quinientos metros. Los avisos de carácter promocional
están limitados a tres por hora y por usuario, para que la cercanía no se
convierta en saturación; el límite no alcanza a los avisos derivados de algo que
el turista ya contrató o siguió, como la cancelación de un evento al que se había
vinculado.

---

## Mensajería

### RF-S-17

> **Sala de negociación**

Toda coordinación entre el turista y el prestador ocurre en una sala de chat
cifrada, creada a partir de la solicitud o de la reserva que la origina. Admite
texto, imágenes y documentos PDF, y cada mensaje de texto está limitado a dos mil
caracteres. El historial permanece asociado al servicio, de modo que lo acordado
siga siendo consultable cuando surge una discrepancia posterior.

### RF-S-18

> **Restricción de contacto directo**

Mientras la reserva no esté confirmada, el sistema impide el envío de números de
teléfono y direcciones de correo dentro de la sala. La restricción existe para
que la negociación no se desplace fuera del sistema. El envío se bloquea y
se informa el motivo al remitente.

### RF-S-19

> **Bandeja de conversaciones**

Cada usuario dispone de una bandeja que reúne sus salas activas e históricas,
ordenadas por la fecha del último mensaje y con su vista previa junto a la
identidad de la contraparte. Una misma bandeja atiende al turista en la
aplicación móvil y al prestador en su portal.

### RF-S-20

> **Búsqueda dentro de la conversación**

Dentro de una sala, el usuario localiza mensajes por coincidencia de texto. La
búsqueda se habilita a partir de tres caracteres y resalta las coincidencias sin
alterar el orden cronológico del historial.

### RF-S-21

> **Archivado de conversaciones**

El usuario retira de su bandeja principal una sala cuyo servicio ya concluyó. El
archivado es independiente por participante: que el turista archive no afecta la
bandeja del prestador, y en ningún caso destruye el historial.

---

## Reputación

### RF-S-22

> **Evaluación mutua al cierre del servicio**

Al concluir un servicio contratado, el sistema solicita al turista y al prestador
que se evalúen mutuamente con una puntuación de una a cinco estrellas y un
comentario. La puntuación es obligatoria: el servicio no se da por cerrado en el
flujo operativo mientras falte. El comentario acompaña a la puntuación, y la
condición bajo la cual pasa a ser obligatorio no está definida.

### RF-S-23

> **Visibilidad asimétrica de las reseñas**

Las reseñas sobre guías y traductores son públicas y las consulta cualquier
usuario que explore su perfil. Las reseñas sobre el turista son privadas: solo
las ven otros prestadores cuando ese turista les envía una solicitud. La
asimetría es deliberada, porque la reseña pública sostiene la decisión de
contratación mientras que la privada protege al profesional frente a un cliente
conflictivo sin exponerlo públicamente.

### RF-S-24

> **Ventana de corrección**

El autor de una reseña modifica su puntuación y su texto durante las
veinticuatro horas siguientes a la publicación. Transcurrido el plazo, la reseña
queda inmutable para su autor y solo puede retirarse mediante moderación. Cada
corrección recalcula el promedio del evaluado.

### RF-S-25

> **Impugnación de una reseña**

El prestador que recibe una reseña con lenguaje ofensivo o con afirmaciones
falsas la marca indicando la categoría del reporte. La marca no oculta la reseña:
abre un caso de disputa que el equipo de moderación resuelve, y el autor no es
notificado de la impugnación mientras no exista resolución.
