---
hide:
  - toc
icon: lucide/waypoints
---

# Diagramas de casos de uso

Qué puede pedirle cada actor al sistema, y qué arrastra consigo cada petición.
El diagrama de casos de uso no cuenta el orden ni las condiciones: eso lo
cuentan los [diagramas de actividades](../actividades/index.md) y los
[diagramas de estados](../estados/index.md). Aquí solo se ve quién está
autorizado a iniciar qué, y qué otro caso queda obligado cuando lo hace.

Son tres cortes, y no uno por superficie, porque los casos de uso que importan
cruzan superficies: la solicitud que el turista publica en el móvil es la que el
guía atiende en el móvil y la que el supervisor cancela desde el backoffice.
Partir por superficie habría separado lo que ocurre junto.

---

## Los tres cortes

| Diagrama                            | Actores | Casos | Qué responde                                                           |
| ----------------------------------- | :-----: | :---: | ---------------------------------------------------------------------- |
| [Contratación](contratacion.md)     |    5    |  13   | Cómo un turista termina acompañado por alguien a quien pagó            |
| [Descubrimiento](descubrimiento.md) |    5    |  18   | De dónde sale el contenido que se recorre y qué hace el turista con él |
| [Moderación](moderacion.md)         |    6    |  18   | Quién decide que un prestador existe y quién lo saca del sistema       |

Lo que no está en ninguno de los tres es deliberado. La mensajería, la
billetera, el balance de ingresos y la exportación de reportes son casos de uso
reales, pero ninguno cambia quién puede hacer qué: son consultas o son pasos
incluidos dentro de los casos que sí aparecen.

---

## Cómo se lee un diagrama

| Símbolo                     | Significa                                                       |
| --------------------------- | --------------------------------------------------------------- |
| Caja                        | Un actor: un papel, no una persona                              |
| Caja de borde punteado      | Un actor no humano: proceso programado o servicio externo       |
| Óvalo                       | Un caso de uso: algo que el sistema hace y que vale por sí solo |
| Recuadro que los agrupa     | La frontera del sistema                                         |
| Línea continua              | Asociación: ese actor puede iniciar ese caso de uso             |
| Flecha punteada `«include»` | El caso de origen **siempre** ejecuta el de destino             |
| Flecha punteada `«extend»`  | El caso de origen ocurre **a veces** sobre el de destino        |

La distinción entre las dos flechas punteadas es la que más se equivoca al leer.
`«include»` va de lo que obliga hacia lo obligado: cerrar un servicio incluye
evaluar, y no existe un cierre sin evaluación. `«extend»` va de lo opcional hacia
la base sobre la que se monta: ajustar una parada extiende el seguimiento de un
circuito oficial, y el seguimiento existe perfectamente sin que nadie ajuste
nada.

---

## Correspondencia con la matriz de capacidades

Ninguna línea de asociación puede contradecir la
[matriz de capacidades](../../actores/index.md#matriz-de-capacidades). Si la
matriz deja vacía la casilla del traductor en «publicar recorrido con tarifa»,
en ningún diagrama puede salir una línea del traductor hacia ese óvalo.

Donde la matriz marca **◐** —capacidad acotada o condicionada— el diagrama
igualmente dibuja la línea, porque el actor sí puede iniciar el caso. La
condición se declara en la tabla de precondiciones que acompaña a cada diagrama,
que es donde cabe decir que un guía sin credencial aprobada no aparece en ningún
tablero.
