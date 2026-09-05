---
icon: lucide/landmark
---

# Portal de alcaldías

- **Módulos:** 3
- **Total:** 11

La superficie del actor ancla del ecosistema. Las alcaldías de las Ciudades
Creativas son las únicas autorizadas a publicar circuitos oficiales, y sin ese
contenido base la aplicación no tiene qué mostrar: cada ciudad que adopta el
portal habilita, en cadena, a los comercios, prestadores e instituciones de su
territorio.

---

## Publicación

### RF-A-01

> **Exclusividad de la publicación oficial**

Solo las alcaldías crean y publican circuitos oficiales. Ningún otro actor puede
producir contenido con esa condición, que es precisamente lo que hace confiable
la oferta base frente a las rutas que arma el turista.

### RF-A-11

> **Alta de la alcaldía**

La alcaldía se registra por un formulario público declarando su ciudad, su nombre
oficial, el correo y teléfono de contacto, y adjuntando el documento que acredita
la representación de quien solicita. El alta no publica nada: deja la
organización y su primer operador en espera, y solo la aprobación del moderador
habilita la potestad de publicar circuitos.

La verificación es más estricta que la de un comercio porque de ella depende
[RF-A-01][rf-a-01]: quien apruebe una alcaldía falsa entrega el sello de
contenido oficial de una ciudad entera.

### RF-A-02

> **Creación de un circuito**

La alcaldía dibuja el circuito sobre el mapa indicando su nombre, su descripción,
las paradas geolocalizadas en su orden de recorrido y las fotografías asociadas.
Las coordenadas deben caer dentro del territorio nicaragüense y los campos
descriptivos son obligatorios. Publicado el circuito, queda visible para los
turistas en la aplicación con el distintivo de oficial.

### RF-A-03

> **Restricción de dominio territorial**

Una alcaldía consulta y modifica exclusivamente los circuitos de su propia
ciudad. Los circuitos de otra Ciudad Creativa no son visibles ni alcanzables
desde su portal, ni siquiera por identificador directo.

---

## Edición

### RF-A-04

> **Edición de la información descriptiva**

La alcaldía reescribe el título y la descripción turística del circuito y
reemplaza su imagen de portada. Estos cambios no alteran la geometría del
recorrido: modifican cómo se presenta, no por dónde pasa.

### RF-A-05

> **Edición de la geometría del recorrido**

La alcaldía agrega paradas, elimina paradas y reordena la secuencia del circuito
sobre el mapa. El circuito resultante debe conservar al menos dos paradas válidas
para poder trazarse; una edición que dejaría menos se rechaza antes de guardarse.

### RF-A-06

> **Propagación de los cambios**

Modificado un circuito, la aplicación móvil debe redibujar el recorrido al
detectar que existe una versión más reciente, sin exigir al turista que
reinstale ni que vacíe datos locales.

### RF-A-07

> **Preservación de lo ya otorgado**

Eliminar una parada de un circuito no reduce el saldo de insignias que esa parada
había otorgado a los turistas que la visitaron. Lo acreditado pertenece al
turista y es independiente de que el punto siga formando parte del recorrido
oficial.

---

## Operación

### RF-A-08

> **Visibilidad temporal**

La alcaldía suspende y reactiva la visibilidad de un circuito mediante un
conmutador, para atender obras viales, condiciones climáticas o fuerza mayor. El
circuito suspendido desaparece de la exploración de forma inmediata, pero las
copias que los turistas ya habían clonado siguen existiendo en sus colecciones.

### RF-A-09

> **Eliminación definitiva**

La alcaldía retira de forma permanente un circuito descatalogado. Por tratarse de
una acción irreversible, exige una confirmación reforzada en la que el operador
teclee el nombre exacto del circuito. El alcance de esa eliminación sobre el
historial derivado no está resuelto y se documenta como contradicción entre fuentes.

### RF-A-10

> **Métricas del circuito**

El portal presenta, para un rango de fechas, cuántos turistas iniciaron el
circuito, cuántos lo modificaron y cuántos lo completaron. Es la evidencia con la
que la alcaldía justifica el esfuerzo de digitalización de su ciudad; las
métricas describen comportamiento agregado y no identifican turistas
individuales.
