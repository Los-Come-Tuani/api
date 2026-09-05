---
hide:
  - toc
icon: lucide/route
---

# Diagramas de actividades

En qué orden ocurren las cosas, quién ejecuta cada paso y dónde el flujo puede
tomar otro camino. Es la capa que falta entre los
[casos de uso](../casos-de-uso/index.md), que dicen qué se puede pedir, y los
[diagramas de estados](../estados/index.md), que dicen en qué condición queda
cada fila.

Los tres flujos elegidos son los que atraviesan más de un actor y más de una
superficie. Un flujo que empieza y termina dentro del mismo portal —editar una
ficha, renombrar una ruta— no necesita diagrama: es una pantalla con una
validación.

---

## Los tres flujos

| Diagrama                                            | Particiones | Decisiones | Empieza en                        | Termina en                       |
| --------------------------------------------------- | :---------: | :--------: | --------------------------------- | -------------------------------- |
| [Contratación](contratacion.md)                     |      4      |     3      | El turista publica su solicitud   | La reserva cerrada y el pago liberado |
| [Acreditación del prestador](acreditacion.md)       |      3      |     3      | El prestador crea su cuenta       | El prestador visible y contratable |
| [De la visita al mostrador](insignias-y-cupones.md) |      3      |     5      | El dispositivo reporta su posición | El cupón consumido en el local   |

---

## Cómo se lee un diagrama

| Símbolo                | Significa                                                  |
| ---------------------- | ---------------------------------------------------------- |
| Círculo `inicio`       | Dónde arranca el flujo                                     |
| Círculo doble `fin`    | Dónde termina                                              |
| Caja                   | Una actividad: un paso con un responsable                  |
| Rombo                  | Una decisión: cada salida lleva su guarda                  |
| Caja de borde punteado | Un paso que ejecuta el proceso programado, sin que nadie lo pida |
| Recuadro que las agrupa | Una partición: de quién es la responsabilidad de esos pasos |

Las particiones son el eje del diagrama. Un paso dentro de la partición
`k'plan` no lo ejecuta ninguna persona: lo hace el sistema como consecuencia de
lo que hizo la partición anterior. Cuando un paso obligatorio del sistema aparece
en la partición de un actor, el diagrama está mal dibujado.

---

## Lo que ningún diagrama de actividades muestra

**Las cancelaciones.** Casi todo paso admite que alguien cancele, y dibujarlo
convertiría los tres diagramas en una maraña de flechas hacia el mismo final. Qué
ocurre al cancelar está en la máquina de estados de cada entidad, que es donde
cabe distinguir quién canceló, con cuánta anticipación y a quién se le reembolsa.

**Los errores de validación de campo.** Aparece la decisión cuando el rechazo
devuelve al usuario a un paso anterior del flujo; no aparece cuando solo pinta un
campo de rojo.

**Los avisos.** Cada transición relevante emite una notificación. Dibujarlas
duplicaría el número de cajas sin agregar una sola bifurcación.
