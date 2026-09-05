---
icon: lucide/git-branch
---

# Decisiones transversales

Decisiones de modelado que afectan a más de un módulo y que no son evidentes a
partir del requerimiento que las exige. Cada una enuncia la decisión, el
requerimiento que la origina y, cuando hubo alternativa, por qué se descartó.

- **Total:** 33

---

## Identidad y acceso

### D-01

> **Una sola tabla de usuario para todos los papeles**

La identidad, las credenciales, la sesión y las sanciones son idénticas sea el
titular un turista, un guía o un operador de alcaldía. Separar al usuario por
superficie obligaría a replicar cinco veces la verificación de correo, el bloqueo
por intentos, el segundo factor y la bitácora, y a mantener las cinco copias
sincronizadas.

Los datos propios de cada papel no caben ahí: la nacionalidad y el nivel de
exploración solo aplican al turista, y las acreditaciones del INTUR y la cuenta de
desembolso solo al prestador. Guardarlos todos en la misma fila dejaría la mitad
de las columnas sin sentido para cada persona, así que viven en tablas de perfil
—`perfil_turista` y `perfil_prestador`— que cuelgan de `usuario`, con a lo sumo
una fila de cada una por persona.

La palabra «cuenta» que usan los requerimientos no designa otra entidad: nombra a
esa misma fila vista desde el lado del acceso.

### D-02

> **El papel se asigna con un ámbito, no solo con un nombre**

Saber que una cuenta tiene el rol de operador de circuitos no basta: hay que
saber de qué ciudad. La asignación de rol lleva un ámbito tipado y toda escritura
lo exige. Sin esto, [RF-A-03][rf-a-03] depende de que ninguna consulta olvide filtrar
por ciudad, y basta una sola omisión para que Granada pueda
reescribir el circuito de León.

### D-03

> **Los permisos se otorgan por rol, nunca directamente a la cuenta**

Un permiso concedido de forma individual es invisible en la revisión del rol y
sobrevive a la revocación del rol. Concentrar la concesión en `rol_permiso`
convierte la revocación en una sola operación auditable. El andamiaje actual
admite ambas vías; el modelo de dominio usa solo la primera.

### D-04

> **Segundo factor como entidad, no como bandera**

Una cuenta puede tener más de un factor, cada uno con su tipo, su secreto
cifrado, su fecha de alta y su estado de confirmación. Modelarlo como columna
booleana impediría rotar un factor sin perder el anterior y dejaría sin lugar los
códigos de recuperación. [RF-B-08][rf-b-08] exige el segundo factor para expulsar
a un usuario, que es la acción menos reversible del sistema: una contraseña
filtrada no puede bastar para ejecutarla.

### D-05

> **La sesión se registra para poder revocarse**

Una credencial firmada es autocontenida y no puede borrarse una vez emitida. Para
que [RF-S-07][rf-s-07] y [RF-B-07][rf-b-07] surtan efecto inmediato, cada
credencial emitida deja su identificador en una lista de revocación persistente
con su fecha de expiración natural. La lista se purga cuando las credenciales
vencen por sí solas, de modo que no crece indefinidamente.

### D-06

> **La credencial de renovación es de un solo uso**

Renovar la sesión consume la credencial de renovación y emite un par nuevo. Si la
misma credencial se presenta dos veces, la segunda vez ya está revocada y el
intento falla. Es lo que convierte el robo de una credencial de renovación en un
incidente detectable en lugar de en un acceso permanente.

### D-07

> **El dispositivo es una entidad**

[RF-B-08][rf-b-08] veta la creación de cuentas nuevas desde el dispositivo del
expulsado. Ese veto necesita algo a lo que apuntar: una tabla de dispositivos con
su identificador declarado, vinculada a las sesiones que se abrieron desde él.
Sin ella la expulsión solo alcanza a la cuenta, y crear otra cuesta un minuto.

### D-08

> **Los intentos fallidos se registran por identificador tecleado, no por cuenta**

[RF-S-06][rf-s-06] exige que el sistema no distinga entre correo inexistente y
contraseña incorrecta. Si el intento se asociara a la cuenta, un correo que no
existe no tendría dónde registrarse y el bloqueo por cinco intentos solo
funcionaría para cuentas reales, revelando cuáles lo son. El registro guarda la
cadena tal como llegó.

### D-09

> **Los datos sensibles se cifran en la aplicación**

El secreto del segundo factor y la cuenta bancaria de desembolso se guardan
cifrados junto al identificador de la llave que los cifró, no en claro ni
delegados al cifrado de disco. Un volcado de la base de datos no debe bastar para
desviar un retiro ni para suplantar un segundo factor.

### D-10

> **El cambio de cuenta bancaria es una fila, no una actualización**

[RF-P-07][rf-p-07] impone veinticuatro horas de espera antes de que una cuenta
nueva surta efecto. Modelarlo como fecha en la propia cuenta obligaría a
sobrescribir el dato anterior, y entonces no habría a qué revertir si el cambio
resulta fraudulento. La solicitud de cambio es una entidad con fecha de petición
y de efectividad; la cuenta activa sigue siendo la anterior hasta que vence.

---

## Estados y ciclo de vida

### D-11

> **El estado es una fila de catálogo, no un valor en la columna**

Cada entidad con ciclo de vida referencia una fila de `estado_<entidad>`, y esa
fila lleva como atributos las preguntas que el sistema hace sobre el estado:
si permite operar, si es terminal, si revoca la sesión. Un valor en columna
obligaría a repartir esas preguntas en condicionales por todo el código, y
agregar un estado exigiría migrar un tipo.

### D-12

> **Estado y discriminador estructural son cosas distintas**

La prueba: si agregar un valor nuevo obliga a agregar columnas que solo aplican a
ese valor, no es un estado sino un discriminador, y entonces corresponde una
tabla propia. Guía y traductor comparten columnas y proceso, así que son un
catálogo de tipo de servicio sobre una misma tabla de prestador. Alcaldía,
comercio e institución cultural no comparten casi nada, así que
son tres tablas y no una con banderas.

### D-13

> **Cada cambio de estado deja una fila de transición**

[RF-S-10][rf-s-10] exige registrar fecha, hora, responsable y motivo de cada
cambio. Una tabla `transicion_<entidad>` de solo inserción guarda estado de
origen, estado de destino, quién y por qué. El estado actual sigue viviendo en la
entidad porque las consultas frecuentes no pueden pagar una agregación.

### D-14

> **La sanción es la causa; el estado de la cuenta es su consecuencia**

Suspensión y expulsión se modelan como filas de `sancion` con tipo, vigencia,
motivo y responsable. El estado de la cuenta refleja la sanción vigente pero no
la sustituye: sin la tabla no habría historial de reincidencia
([RF-B-10][rf-b-10]) y una segunda suspensión borraría el rastro de la primera.

---

## Contenido territorial

### D-15

> **El circuito oficial se versiona; el itinerario del turista no**

[RF-A-06][rf-a-06] exige que la aplicación detecte que un circuito cambió. Eso
requiere un número de versión que se incrementa con cada edición de la geometría.
El itinerario no se versiona porque nadie más lo consume: quien lo edita es su
único lector.

### D-16

> **El itinerario ajustado copia la parada en lugar de referenciarla**

Cuando el turista se aparta del circuito oficial, cada parada de su itinerario
guarda su propio nombre y sus propias coordenadas, con una referencia opcional al
punto de interés del que se derivó, usada solo para trazabilidad. Si la
referencia fuera la única fuente, retirar un punto de un circuito oficial dejaría
un hueco en el itinerario que el turista lleva abierto a mitad de recorrido. Es
la aplicación directa de que lo ya otorgado no se destruye, y el precio es una
denormalización deliberada. El caso en que no hay copia está en [D-33](#d-33).

### D-17

> **Un itinerario puede derivarse de varios circuitos**

[RF-T-08][rf-t-08] permite combinar circuitos de ciudades distintas, de modo que
el origen de un itinerario no es una llave foránea simple sino una relación de
varios a varios. Modelarlo como una sola referencia obligaría a elegir
arbitrariamente un circuito «principal» y perdería la trazabilidad del resto,
que es justamente lo que las métricas de la alcaldía necesitan contar
([RF-A-10][rf-a-10]).

### D-18

> **El punto de interés es independiente del circuito que lo usa**

Un mismo lugar puede aparecer en más de un circuito y además otorgar insignias
por sí mismo. Por eso el punto existe como entidad de la ciudad y el circuito lo
incorpora mediante una tabla de paradas que aporta el orden. Retirar un punto de
un circuito no lo elimina del territorio ni cancela lo que ya otorgó.

### D-33

> **El itinerario materializa paradas propias solo cuando se aparta del circuito**

[RF-T-28][rf-t-28] permite al turista recorrer un circuito oficial tal como la
alcaldía lo publicó, sin modificar nada. Ese caso también produce un itinerario
—hace falta para acreditar visitas, contratar un guía y alimentar las métricas
del circuito—, pero el
itinerario no copia las paradas: guarda la referencia al circuito y las lee de su
versión vigente.

Las paradas propias aparecen en el momento en que el turista edita: agregar,
quitar o reordenar convierte al itinerario en una copia congelada, y a partir de
ahí [D-16](#d-16) rige sin excepción. La transición ocurre una sola vez y no se
revierte.

De ahí sale la diferencia que [RF-A-10][rf-a-10] pide medir por separado. Quien
sigue el circuito tal cual recibe las correcciones que publique la alcaldía y
cuenta como «inició»; quien lo ajustó queda aislado de ellas y cuenta como
«modificó». Si ambos casos copiaran las paradas, la corrección de una parada mal
ubicada no alcanzaría a nadie que ya hubiera empezado, y las dos cifras serían
indistinguibles.

---

## Servicios y transacciones

### D-19

> **La reserva es la unidad de servicio y admite dos orígenes**

Una reserva nace de una postulación aceptada o de la contratación directa de un
recorrido publicado. Todo lo posterior —sala de chat, cierre, evaluación mutua,
pago y comisión— es idéntico, así que es una sola tabla con dos referencias
mutuamente excluyentes. Dos tablas duplicarían el ciclo completo y obligarían a
unirlas en cada consulta de historial.

### D-20

> **La tarifa se congela en la reserva**

[RF-P-10][rf-p-10] prohíbe que un cambio de tarifa afecte reservas ya creadas. La
reserva copia tarifa, moneda y cantidad en el momento de crearse. Si leyera el
precio del recorrido, un ajuste del prestador cambiaría retroactivamente lo que
el turista aceptó pagar.

### D-21

> **La conversación cuelga del objeto que la origina**

La sala existe porque hay una solicitud o una reserva de por medio, nunca por sí
sola. Los participantes viven en una tabla propia, que es donde reside la bandera
de archivado: [RF-S-21][rf-s-21] exige que archivar sea independiente por
persona, y una columna en la conversación afectaría a ambas partes.

### D-22

> **Una sola tabla de reseña con dirección explícita**

Emisor, receptor y reserva. La visibilidad no es una columna configurable: se
deriva del papel del receptor, tal como impone [RF-S-23][rf-s-23]. Dos tablas
—una pública y otra privada— duplicarían la ventana de corrección, la
impugnación y el recálculo del promedio, con el riesgo de que las dos copias
diverjan.

### D-23

> **El promedio de reputación se materializa**

Se consulta en cada listado de prestadores y en cada tablero de postulaciones.
Recalcularlo por agregación en cada búsqueda es el cálculo más caro y más
repetido del sistema. Se mantiene actualizado desde la propia base cada vez que
una reseña se inserta o se corrige, no desde la aplicación, para que ninguna vía
de escritura pueda dejarlo obsoleto.

---

## Saldos y economía interna

### D-24

> **Los saldos son libros de movimientos, no columnas**

Insignias del turista y saldo del prestador se derivan de filas de solo
inserción, cada una con su signo, su motivo y su origen. Si el saldo fuera una
columna, dos canjes simultáneos podrían leer el mismo valor, ambos superar la
comprobación de suficiencia y dejar el saldo en negativo. Con el libro, el
segundo ve el movimiento del primero.

### D-25

> **El cupón canjeado guarda su beneficio, no lo consulta**

[RF-C-08][rf-c-08] permite al comercio retirar una campaña sin invalidar los
cupones ya entregados. Si el cupón leyera el descuento de la campaña, retirarla
cambiaría el valor de lo ya canjeado. El cupón copia beneficio, comercio y fecha
límite en el momento del canje.

### D-26

> **El código del cupón se guarda legible, no cifrado**

El turista debe poder verlo en su billetera y dictarlo en el mostrador, así que
el sistema tiene que poder mostrarlo. Se descartó guardar solo su huella porque
haría imposible esa lectura. El riesgo se acota por otra vía: un solo uso,
vigencia acotada y pertenencia a un único comercio, de modo que un código
filtrado no vale nada fuera de su contexto. El alfabeto excluye caracteres que se
confunden al dictarse.

### D-27

> **La visita acreditada es un hecho inmutable**

El registro de proximidad no se corrige ni se borra: es lo que justifica el
movimiento de insignias que lo acompaña. La regla de una visita por
establecimiento cada veinticuatro horas ([RF-S-15][rf-s-15]) se resuelve contra
esa tabla, comparando con la última visita registrada.

### D-28

> **La presión de notificaciones se mide sobre lo emitido**

El límite de tres avisos promocionales por hora ([RF-S-16][rf-s-16]) es una
ventana deslizante, no un cupo que se reinicia. Un contador por hora dejaría
pasar seis avisos entre las 10:59 y las 11:01. Cada aviso emitido deja fila con
su instante, y el límite se evalúa contando las de los últimos sesenta minutos.

---

## Integridad, validación y auditoría

### D-29

> **La validación ocurre en tres capas y la base tiene la última palabra**

El formato se valida al recibir la petición, la regla de negocio en el servicio y
el invariante en la base de datos. La base no confía en la aplicación: un precio
negativo o una capacidad de sesenta personas se rechazan por restricción aunque
el servicio los deje pasar. La razón es concreta: una carga masiva, una
corrección manual o una migración no atraviesan el servicio, y son exactamente
las situaciones en las que un dato inválido entra sin que nadie lo vea.

### D-30

> **El error de integridad se traduce al campo que lo causó**

Las restricciones diferidas se evalúan de forma anticipada dentro de la
transacción para que el fallo pueda atribuirse a una columna concreta y
devolverse como un error de validación con su ubicación —cuerpo, ruta, consulta
o archivo— en lugar de como un fallo genérico. Esto convierte a la restricción de
base de datos en una fuente de mensajes útiles y no en un último recurso opaco.

### D-31

> **Tres regímenes de auditoría, declarados por tabla**

Cada tabla del modelo declara a cuál pertenece. **De solo inserción**: nada se
actualiza ni se borra —movimientos, visitas, transiciones, bitácora—. **Mutable
rastreada**: se puede modificar y cada versión anterior queda registrada —
perfiles, fichas, circuitos, eventos—. **Mutable protegida**: se puede modificar
salvo columnas congeladas por disparador, como el identificador y la fecha de
creación. Declararlo por tabla evita la pregunta caso por caso.

### D-32

> **El registro de auditoría guarda el contexto, no solo el dato**

Además del valor anterior y el nuevo, cada evento conserva quién lo provocó,
desde qué dirección y sobre qué recurso. Sin el contexto, el historial responde
qué cambió pero no quién ni por qué, que es justamente lo que hay que responder
cuando se disputa una sanción o una reseña.

[rf-a-03]: ../requerimientos/funcionales/portal-alcaldias.md#rf-a-03
[rf-a-06]: ../requerimientos/funcionales/portal-alcaldias.md#rf-a-06
[rf-a-10]: ../requerimientos/funcionales/portal-alcaldias.md#rf-a-10
[rf-b-07]: ../requerimientos/funcionales/backoffice.md#rf-b-07
[rf-b-08]: ../requerimientos/funcionales/backoffice.md#rf-b-08
[rf-b-10]: ../requerimientos/funcionales/backoffice.md#rf-b-10
[rf-c-08]: ../requerimientos/funcionales/portal-comercios.md#rf-c-08
[rf-p-07]: ../requerimientos/funcionales/app-prestadores.md#rf-p-07
[rf-p-10]: ../requerimientos/funcionales/app-prestadores.md#rf-p-10
[rf-s-06]: ../requerimientos/funcionales/plataforma.md#rf-s-06
[rf-s-07]: ../requerimientos/funcionales/plataforma.md#rf-s-07
[rf-s-10]: ../requerimientos/funcionales/plataforma.md#rf-s-10
[rf-s-15]: ../requerimientos/funcionales/plataforma.md#rf-s-15
[rf-s-16]: ../requerimientos/funcionales/plataforma.md#rf-s-16
[rf-s-21]: ../requerimientos/funcionales/plataforma.md#rf-s-21
[rf-s-23]: ../requerimientos/funcionales/plataforma.md#rf-s-23
[rf-t-08]: ../requerimientos/funcionales/app-turista.md#rf-t-08
[rf-t-28]: ../requerimientos/funcionales/app-turista.md#rf-t-28
