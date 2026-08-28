---
icon: lucide/drama
---

# Portal de instituciones

La superficie de las casas de cultura, fundaciones, ticketeras y teatros que
organizan ferias, funciones, talleres y festivales. Es lo que da dinamismo a un
circuito: los comercios y las paradas son oferta permanente, mientras que la
agenda cultural cambia por temporada y es la razón por la que una misma ciudad
resulta distinta según la semana en que se visita.

- **Módulos:** 2
- **Total:** 6

---

## Programación

### RF-I-01

> **Alta de un evento**

La institución registra el evento con su nombre, descripción, ubicación
geolocalizada del recinto, fecha de inicio, fecha de finalización, horario y
precio de entrada. Las fechas deben ser futuras y la de finalización no puede ser
anterior a la de inicio.

### RF-I-02

> **Vigencia automática**

El evento aparece en el mapa y en la agenda durante su rango de fechas, y el
sistema lo retira de forma automática cuando esa fecha de finalización queda
atrás. La institución no necesita despublicar nada: la vigencia la gobierna el
propio calendario del evento.

### RF-I-03

> **Calendario mensual**

El portal presenta los eventos de la institución en un calendario navegable por
mes, diferenciando visualmente los ya ocurridos, los vigentes y los futuros. Cada
evento del calendario da acceso directo a su ficha.

---

## Modificación

### RF-I-04

> **Edición de un evento**

La institución corrige la descripción, el horario y el precio de entrada de un
evento mientras este no haya finalizado, con las mismas condiciones de fecha y
precio que rigen su alta. Los cambios se reflejan de inmediato en la aplicación.

### RF-I-05

> **Cancelación de un evento**

La institución marca un evento como cancelado, opcionalmente con el motivo. El
sistema avisa a los turistas que habían interactuado con ese evento y deja de
emitir avisos por cercanía asociados a él, para no atraer visitantes a un recinto
donde ya no ocurrirá nada. El evento cancelado permanece visible señalado como
tal en lugar de desaparecer.

### RF-I-06

> **Clonación de un evento**

Para la programación recurrente —una función semanal, un taller que se repite—,
la institución duplica un evento anterior conservando su descripción, ubicación y
precio, y dejando las fechas vacías. Es un atajo de captura: el evento clonado no
existe hasta que se le asignan fechas válidas y se guarda como registro
independiente.
