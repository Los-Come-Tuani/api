---
icon: lucide/gauge
title: No funcionales
---

# Requerimientos no funcionales

Restricciones de calidad que el sistema debe satisfacer con independencia de la
superficie desde la que se opere. A diferencia de los funcionales, no describen
un comportamiento que un actor ejecuta, sino la condición bajo la cual ese
comportamiento es aceptable.

Solo se registran los que tienen respaldo en las fuentes. Cuando la necesidad
existe pero el valor concreto nunca fue definido, el requerimiento la enuncia y
declara el vacío en lugar de rellenarlo con una cifra plausible: un umbral
inventado aquí termina codificado como una restricción de base de datos que nadie
decidió. La sección final los reúne para que la decisión sea explícita.

- **Categorías:** 7
- **Total:** 25
- **Pendientes de definición:** 9

---

## Plataforma y compatibilidad

### RNF-01

> **Composición tecnológica**

Aplicación móvil para Android e iOS, portales web y una interfaz de servicios
sobre PostgreSQL. Las versiones mínimas de sistema operativo móvil y de navegador
que el sistema se compromete a soportar no están definidas.

### RNF-02

> **Diseño responsivo de los portales**

Los portales deben ser plenamente operables desde el teléfono del propio usuario,
sin aplicación nativa. El caso límite es la validación de cupones en mostrador,
que ocurre de pie y con una sola mano.

### RNF-03

> **Dependencias externas**

El sistema depende de servicios de mapas, pasarela de pago, notificaciones push,
correo y mensajería de texto. Cada dependencia es un punto de fallo cuyo efecto
debe ser visible: el sistema informa la degradación en lugar de fallar en
silencio. La política de reintento y el comportamiento de respaldo de cada
servicio no están definidos.

---

## Localización

### RNF-04

> **Idioma base y zona horaria**

El idioma base del sistema es el español de Nicaragua y toda la lógica temporal
se resuelve en `America/Managua`, con almacenamiento en tiempo universal
coordinado. Es una decisión ya tomada y verificable en la configuración del
repositorio.

### RNF-05

> **Contenido multilingüe**

El turista declara un idioma preferido y la interfaz lo respeta cuando existe
traducción. El catálogo de idiomas soportados y el alcance de
la traducción no están definidos.

### RNF-06

> **Moneda**

Las tarifas se expresan en córdobas y en dólares, y el umbral mínimo de retiro
está fijado en dólares. La moneda de referencia contable, la fuente del tipo de
cambio y el momento en que se congela para una transacción no están definidos.

---

## Seguridad

### RNF-07

> **Custodia de credenciales**

Las contraseñas se almacenan cifradas de forma irreversible y nunca se
transportan ni se registran en claro. La política de composición vigente exige al
menos ocho caracteres, una mayúscula y un número.

### RNF-08

> **Sesión y revocación**

Las sesiones se sostienen con credenciales firmadas y de vigencia acotada y el sistema
puede revocarlas antes de su expiración natural. Sin esa capacidad, una suspensión
no tendría efecto sobre el dispositivo en el que el infractor ya estaba dentro.

### RNF-09

> **Resistencia a la fuerza bruta**

Cinco intentos fallidos consecutivos sobre el mismo identificador bloquean el
acceso durante quince minutos, y los mensajes de error no distinguen entre
identificador inexistente y credencial incorrecta.

### RNF-10

> **Cifrado de datos sensibles**

El historial de las salas de chat, los documentos de credencial y los datos
bancarios de desembolso se almacenan cifrados. El cambio de cuenta bancaria
además observa un periodo de espera de veinticuatro horas antes de surtir efecto.

### RNF-11

> **Confirmación reforzada de acciones irreversibles**

La expulsión permanente de un usuario y la eliminación definitiva de un circuito
oficial exigen una confirmación adicional distinta del clic que las inicia:
tecleo del nombre exacto en un caso, segunda validación del supervisor en el
otro.

---

## Privacidad

### RNF-12

> **Minimización de la exposición**

Los datos demográficos del turista son privados y hacia terceros solo se expone
su nombre de pila y su fotografía. Las solicitudes de acompañamiento circulan
anonimizadas hasta que se abre la sala de chat formal.

### RNF-13

> **Asimetría de la reputación**

Las reseñas sobre prestadores son públicas y las reseñas sobre turistas circulan
únicamente entre prestadores. La visibilidad no es una preferencia configurable:
es una propiedad del tipo de reseña.

### RNF-14

> **Derecho a la baja**

El titular puede solicitar la eliminación definitiva de su cuenta, que se ejecuta
tras treinta días de inactividad. El marco normativo de protección de datos que
el sistema declara cumplir no está definido, y de él dependen los plazos, el
alcance del borrado y las excepciones por obligación contable.

---

## Disponibilidad y desempeño

### RNF-15

> **Continuidad del servicio**

El sistema opera de forma continua porque el turista lo usa en desplazamiento y
el comercio valida cupones en horario de atención. El objetivo de disponibilidad
y la ventana de mantenimiento aceptable no están definidos.

### RNF-16

> **Tiempos de respuesta**

El mapa, la búsqueda de oferta y la validación de cupones en mostrador son las
interacciones sensibles a la latencia, esta última porque ocurre frente al
cliente. Ningún tiempo de respuesta objetivo está definido.

### RNF-17

> **Comportamiento sin conectividad**

La colección de rutas del turista se consulta sin conexión y se sincroniza con el
servidor cuando esta se restablece. El alcance del modo sin conexión para el
resto de la aplicación no está definido.

---

## Capacidad y límites

### RNF-18

> **Límites del contenido aportado**

Imágenes en JPG o PNG de hasta cinco megabytes, documentos en PDF de hasta diez
megabytes, mensajes de chat de hasta dos mil caracteres y recorridos de hasta
cincuenta personas.

### RNF-19

> **Presión de notificaciones**

Un máximo de tres avisos promocionales por hora y por usuario, sobre geocercas
cuyo radio de partida es de quinientos metros. El límite protege la utilidad del
canal: un turista saturado desactiva los avisos y deja de recibir también los
que le importan.

### RNF-20

> **Precisión geográfica**

La acreditación de una visita exige una distancia menor a cincuenta metros
respecto del punto de interés. La precisión mínima que debe reportar el
dispositivo para que esa medición se acepte no está definida.

### RNF-21

> **Volumen esperado**

El piloto se concentra en las ciudades con circuitos más avanzados. El número
esperado de turistas, comercios, prestadores y circuitos por ciudad no está
definido, y de él dependen las decisiones de indexación y de estrategia de
consulta geoespacial.

---

## Operación y trazabilidad

### RNF-22

> **Bitácora de acciones sensibles**

Las aprobaciones, los rechazos, las sanciones, los cambios de estado de cuenta y
las exportaciones quedan registrados con fecha, hora, responsable y motivo. El
motivo es obligatorio en toda acción de moderación.

### RNF-23

> **Integridad del historial derivado**

La retirada de un elemento publicado no destruye lo que ese elemento ya generó:
las insignias otorgadas, las copias de rutas que hicieron los turistas y los
cupones ya canjeados sobreviven a la desaparición de su origen. Es la regla que
hace segura la edición del contenido oficial.

### RNF-24

> **Transparencia de la comisión**

El desglose financiero del prestador muestra el bruto cobrado, el porcentaje y el
monto de comisión retenida y el neto resultante, de forma separada. El prestador
debe poder verificar la operación, no solo su resultado.

### RNF-25

> **Retención del historial**

Los historiales de viajes, pagos, reseñas y sanciones se conservan como registro
consultable. El periodo de retención de cada uno y la política de purga no están
definidos.
