---
hide:
  - toc
icon: lucide/users-round
---

# Actores del sistema

Un actor no es una persona: es un papel. Lo que separa a un guía de un traductor
no es quién es, sino qué puede publicar; lo que separa a un operador de Granada
de uno de León no es su cargo, sino sobre qué ciudad escribe.

- **Superficies:** 5
- **Actores humanos:** 8
- **Actores no humanos:** 2

---

## Quién es quién

| Actor                                                          | Superficie | En una línea                                                            |
| -------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------- |
| [Turista](app-movil.md#turista)                                | App móvil  | Explora, arma su itinerario, contrata acompañamiento y canjea insignias |
| [Guía turístico](app-movil.md#guia-turistico)                  | App móvil  | Publica recorridos, se postula y presta el servicio en el territorio    |
| [Traductor](app-movil.md#traductor)                            | App móvil  | Se postula a solicitudes de turistas; no publica catálogo propio        |
| [Operador de alcaldía](portales.md#operador-de-alcaldia)       | Portal web | Publica y mantiene los circuitos oficiales de su ciudad                 |
| [Operador de comercio](portales.md#operador-de-comercio)       | Portal web | Mantiene la ficha del negocio, emite cupones y los valida en mostrador  |
| [Operador de institución](portales.md#operador-de-institucion) | Portal web | Programa la agenda cultural que aparece en la app                       |
| [Moderador](backoffice.md#moderador)                           | Backoffice | Verifica acreditaciones y organizaciones antes de que sean visibles     |
| [Supervisor](backoffice.md#supervisor)                         | Backoffice | Resuelve reportes y sanciona                                            |

El reparto entre móvil y web sigue dónde trabaja cada uno. Turista, guía y
traductor operan en la calle: necesitan ubicación, cámara y avisos en segundo
plano. Alcaldías, comercios e instituciones administran desde un escritorio:
formularios largos, carga de archivos y tablas.

---

## Matriz de capacidades

Quién puede ejecutar cada acción. **●** es capacidad plena; **◐** es
capacidad acotada a un ámbito o condicionada a una verificación previa.

| Acción                               | Tur | Guía | Trad | Alc | Com | Inst | Mod | Sup |
| ------------------------------------ | :-: | :--: | :--: | :-: | :-: | :--: | :-: | :-: |
| Publicar circuito oficial            |     |      |      |  ◐  |     |      |     |     |
| Editar o retirar un circuito         |     |      |      |  ◐  |     |      |     |     |
| Crear puntos de interés              |     |      |      |  ◐  |     |      |     |     |
| Consultar circuitos y mapa           |  ●  |  ●   |  ●   |  ●  |     |      |  ●  |  ●  |
| Seguir un circuito tal cual          |  ●  |      |      |     |     |      |     |     |
| Ajustar, combinar o crear itinerario |  ●  |      |      |     |     |      |     |     |
| Publicar solicitud de acompañamiento |  ●  |      |      |     |     |      |     |     |
| Publicar recorrido con tarifa        |     |  ◐   |      |     |     |      |     |     |
| Postularse a una solicitud           |     |  ◐   |  ◐   |     |     |      |     |     |
| Aceptar una postulación              |  ●  |      |      |     |     |      |     |     |
| Reservar un recorrido publicado      |  ●  |      |      |     |     |      |     |     |
| Cerrar el servicio prestado          |     |  ●   |  ●   |     |     |      |     |     |
| Registrar un comercio                |     |      |      |     |  ●  |      |     |     |
| Editar ficha, horarios y platillo    |     |      |      |     |  ◐  |      |     |     |
| Emitir campaña de cupones            |     |      |      |     |  ◐  |      |     |     |
| Validar un cupón en mostrador        |     |      |      |     |  ◐  |      |     |     |
| Contratar visibilidad destacada      |     |      |      |     |  ◐  |      |     |     |
| Programar o cancelar eventos         |     |      |      |     |     |  ◐   |     |     |
| Canjear insignias por cupones        |  ●  |      |      |     |     |      |     |     |
| Emitir reseña al cerrar el servicio  |  ●  |  ●   |  ●   |     |     |      |     |     |
| Impugnar una reseña recibida         |     |  ●   |  ●   |     |     |      |     |     |
| Consultar balance y solicitar retiro |     |  ●   |  ●   |     |     |      |     |     |
| Verificar credenciales y comercios   |     |      |      |     |     |      |  ●  |     |
| Resolver reportes y sancionar        |     |      |      |     |     |      |     |  ●  |
| Consultar métricas de su ámbito      |     |      |      |  ◐  |  ◐  |  ◐   |     |  ●  |

Ninguna casilla vacía es un olvido: es una restricción que el modelo debe
sostener. Que la columna del guía esté vacía en «ajustar itinerario» significa
que un guía **no puede** armar rutas, y que la del traductor lo esté en «publicar
recorrido» significa que su único camino de trabajo es postularse.

---

## Relaciones entre actores

**La alcaldía precede a todos los de su ciudad.** Sin circuitos oficiales no hay
contenido base: el turista no tiene qué recorrer, el comercio no tiene dónde
aparecer y el guía no tiene sobre qué proponer un recorrido. Es el actor ancla, y
por eso su adopción habilita en cadena al resto.

**El moderador precede al guía y al traductor.** Ninguno de los dos existe para
el turista antes de que una persona haya revisado su documento. La verificación
no es un trámite paralelo: es la condición de visibilidad.

**Guía y traductor son complementarios, no alternativas.** Sobre un mismo
itinerario el turista puede contratar a los dos, como servicios independientes.
El guía aporta el territorio; el traductor, el idioma.

**Turista y prestador se evalúan mutuamente.** Es la única relación simétrica del
sistema, y aun así su resultado es asimétrico: la reseña sobre el prestador es
pública y la del turista circula solo entre prestadores.

---

## Actores no humanos

### Proceso programado

> **Trabajos que corren sin que nadie los pida**

Suspende al prestador cuya credencial venció, retira del mapa los eventos cuya
fecha de fin ya pasó, evalúa las geocercas contra la posición de los turistas,
libera los bloqueos de acceso cumplidos, ejecuta la destrucción de las cuentas
dadas de baja hace treinta días y purga las sesiones expiradas.

Sus acciones quedan registradas con actor de tipo sistema, sin persona asociada.
Es lo que impide que una credencial vencida siga recibiendo reservas porque nadie
abrió el portal ese día.

### Proveedor externo

> **Servicios de los que el sistema depende**

Mapas, pasarela de pago, notificaciones push, correo y mensajería de texto. No
inician interacciones: responden a las del sistema. Cada uno es un punto de fallo
cuyo efecto debe ser visible, porque un aviso que no se envió y un cupón que no
se pudo validar no pueden quedar en silencio.

---

## Pendiente de definición

**¿Una misma persona puede ser turista y prestador?** Las tres superficies
móviles conviven en una aplicación, así que un guía que quiere viajar como
turista no tendría por qué abrir otra cuenta. El modelo lo admite —los perfiles
cuelgan del usuario— pero falta decidir si la interfaz permite cambiar de papel y
qué ocurre si alguien se postula a su propia solicitud.

**¿El supervisor puede hacer lo del moderador?** Se documentan como papeles
distintos porque ninguna fuente los jerarquiza. Si en la práctica el supervisor
también resuelve la cola de verificación, es una asignación de dos roles a la
misma persona y no un cambio de modelo.

**¿Quién da de alta a una alcaldía y a una institución cultural?** Ni el
documento de innovación ni la matriz de requisitos lo dicen. Un comercio se
registra solo por la web, pero una alcaldía llega por convenio: lo coherente es
que el backoffice cree la organización y su primer operador. Falta confirmarlo.
