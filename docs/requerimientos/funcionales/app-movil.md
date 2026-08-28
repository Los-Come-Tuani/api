---
icon: lucide/smartphone
---

# Aplicación móvil

La superficie del turista nacional y extranjero. Es el único punto donde la
oferta dispersa —circuitos oficiales, comercios, agenda cultural y talento
local— se presenta como una sola experiencia, y el orden de sus módulos refleja
el recorrido real del visitante: primero descubre, luego arma su ruta, después
contrata acompañamiento y finalmente convierte lo explorado en un beneficio
tangible.

- **Módulos:** 5
- **Total:** 27

---

## Descubrimiento

### RF-T-01

> **Mapa de exploración**

Un mapa interactivo presenta, para la ciudad seleccionada, los circuitos
oficiales publicados, los comercios registrados y los eventos culturales
vigentes. Los circuitos oficiales se distinguen visualmente del resto porque son
el contenido que la alcaldía respalda; los eventos usan un marcador propio que
los separa de la oferta permanente.

### RF-T-02

> **Consulta de circuito oficial**

La ficha de un circuito muestra su título, su descripción turística, su imagen de
portada y la secuencia ordenada de paradas con su ubicación y sus fotografías. La
consulta no exige haber iniciado el recorrido ni haber clonado el circuito.

### RF-T-03

> **Recomendación de rutas**

El sistema propone al turista rutas ya armadas a partir de los circuitos
disponibles, de modo que quien no quiere planificar pueda partir de una
sugerencia. El criterio de ordenamiento de esas recomendaciones no está definido;
lo único establecido es que la emisión de cupones por parte de un comercio mejora
su posición en el ordenamiento de la oferta comercial.

### RF-T-04

> **Perfil público de prestador**

El turista consulta el perfil de un guía o traductor para revisar su fotografía,
su promedio de valoración, las credenciales validadas y su catálogo de
recorridos. Solo son consultables los perfiles cuya revisión concluyó en
aprobación: el acceso por identificador a un perfil en revisión o rechazado se
resuelve como recurso inexistente.

### RF-T-05

> **Ficha de comercio**

La ficha de una MiPyme muestra su nombre, ubicación, contacto, fotografías, el
platillo estrella con su precio de referencia y el horario declarado. A partir de
ese horario y del reloj autoritativo, la aplicación indica si el local está
abierto o cerrado en ese instante, para no enviar al turista a un negocio que ya
cerró.

### RF-T-06

> **Agenda de eventos**

Los eventos culturales aparecen en el mapa y en un listado por fecha, con
horario y precio de entrada. Un evento desaparece del mapa de forma automática
cuando su fecha de finalización queda atrás, y un evento cancelado se muestra
señalado como tal en lugar de desaparecer, para que quien ya lo había visto
entienda qué ocurrió.

---

## Rutas personalizadas

### RF-T-07

> **Clonación de un circuito oficial**

El turista toma un circuito oficial y obtiene una copia propia sobre la que puede
agregar o eliminar paradas. La copia es independiente: ninguna modificación del
turista altera el circuito oficial publicado por la alcaldía, y toda ruta
resultante debe conservar al menos dos paradas geolocalizadas para ser válida.

### RF-T-08

> **Combinación de circuitos**

Varias rutas, incluidas las clonadas de ciudades distintas, se unen en una sola
ruta personalizada. Es el mecanismo con el que el turista arma un itinerario de
varios días o de varias ciudades sin depender de que exista un circuito oficial
que las conecte.

### RF-T-09

> **Creación de ruta desde cero**

El turista crea una ruta propia seleccionando puntos sobre el mapa sin partir de
ningún circuito oficial. Aplica la misma condición de validez: al menos dos
paradas geolocalizadas.

### RF-T-10

> **Colección de rutas**

Una sección de la aplicación reúne todas las rutas que el turista ha clonado,
combinado o creado, presentadas como tarjetas con una previsualización de su
trazado. Es el punto de partida de cualquier operación sobre una ruta propia.

### RF-T-11

> **Renombrado de una ruta**

El turista cambia el título de cualquiera de sus rutas. El nuevo título debe
tener al menos tres caracteres y no puede quedar vacío, de modo que la colección
no acumule tarjetas indistinguibles entre sí.

### RF-T-12

> **Duplicación de una ruta propia**

El turista crea una copia exacta de una de sus rutas, incluidas todas sus
paradas, para ensayar una variante sin perder la original. La copia se identifica
de forma que se distinga del original y aparece en la colección como una ruta
independiente.

### RF-T-13

> **Eliminación de una ruta**

El turista descarta una ruta de su colección. La eliminación se rechaza mientras
esa ruta esté vinculada a un servicio contratado con un prestador que aún no ha
concluido ni ha sido cancelado formalmente, porque la ruta es el objeto sobre el
que se acordó el servicio.

### RF-T-14

> **Persistencia de la copia frente a cambios en el origen**

Que una alcaldía oculte, modifique o retire un circuito oficial no altera las
rutas que los turistas ya habían clonado a partir de él: la copia sobrevive al
original. De igual forma, la eliminación de un punto de interés no reduce el
saldo de insignias que ese punto ya había otorgado.

---

## Contratación

### RF-T-15

> **Publicación de una solicitud de acompañamiento**

El turista publica su ruta planificada indicando el rango de fechas, un
presupuesto estimado y el idioma requerido, y el sistema la ofrece a los
prestadores verificados que operan en esa zona y cumplen esos criterios. Las
fechas deben ser futuras y el presupuesto un valor positivo.

### RF-T-16

> **Anonimato de la solicitud**

La solicitud se muestra a los prestadores sin revelar la identidad del turista.
Los datos personales quedan visibles únicamente cuando se abre la sala de chat
formal con el prestador elegido, de modo que publicar una ruta no exponga a quien
la publica.

### RF-T-17

> **Comparación de postulaciones**

Frente a las postulaciones recibidas, el turista compara perfiles, credenciales
verificadas, tarifas y valoraciones públicas antes de elegir. La comparación
ocurre sobre la información validada del perfil y no sobre lo que el prestador
declare en el chat.

### RF-T-18

> **Reserva directa de un recorrido publicado**

Como alternativa a publicar una solicitud, el turista reserva directamente un
recorrido que el guía ya tiene cargado en su catálogo, con la tarifa y los cupos
publicados en ese momento. Los cambios de tarifa posteriores no afectan a una
reserva ya creada.

---

## Insignias y billetera

### RF-T-19

> **Saldo de insignias**

La aplicación muestra el saldo de insignias acumuladas por el turista y el nivel
de exploración alcanzado. El saldo se incrementa con cada visita acreditada y se
reduce con cada canje.

### RF-T-20

> **Tienda de recompensas**

Un catálogo reúne los cupones vigentes que los comercios aliados ofrecen,
indicando el beneficio, el comercio emisor, la fecha límite de la campaña y
cuántas insignias cuesta obtenerlo.

### RF-T-21

> **Canje de insignias**

El turista intercambia insignias por un cupón cuando su saldo es igual o mayor al
costo publicado. El sistema descuenta el saldo y genera un código de validación
único de ocho caracteres alfanuméricos que queda guardado en la billetera del
turista. El descuento del saldo y la emisión del código son inseparables: no
existe un estado en el que se haya cobrado el saldo sin entregar el código.

### RF-T-22

> **Vigencia del cupón canjeado**

Un cupón ya canjeado conserva su validez hasta la fecha límite original de la
campaña, aunque el comercio retire la campaña antes de tiempo. El retiro impide
nuevos canjes, nunca invalida los códigos ya entregados.

---

## Perfil e historial

### RF-T-23

> **Consulta del perfil**

El turista consulta su información personal, su saldo de insignias y su nivel de
exploración en una sola pantalla.

### RF-T-24

> **Edición del perfil**

El turista modifica su fotografía, su biografía breve, su idioma preferido y su
número de teléfono. El teléfono exige un código de área válido. El correo de
registro no se edita desde esta pantalla.

### RF-T-25

> **Privacidad del perfil**

Los datos demográficos del turista son privados y solo los ve su titular. Hacia
las contrapartes con las que interactúa, la aplicación expone únicamente el
nombre de pila y la fotografía.

### RF-T-26

> **Historial de viajes**

Un listado cronológico descendente reúne las rutas recorridas y los servicios
contratados, con filtros por rango de fechas y por ciudad. El rango exige que la
fecha inicial no sea posterior a la final.

### RF-T-27

> **Historial de pagos**

El turista consulta los pagos realizados a través de la plataforma y descarga el
comprobante de cada uno. El momento exacto en que se captura el pago del servicio
no está definido y condiciona qué registros aparecen en este historial.
