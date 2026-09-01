---
hide:
  - toc
icon: lucide/workflow
---

# Diagramas de estados

Una máquina por entidad con ciclo de vida. El diagrama muestra el flujo; la tabla
`estado_<entidad>` impone qué permite cada estado, y `transicion_<entidad>`
registra quién lo cambió y por qué.

Lo que no aparece como estado, aunque lo parezca: `itinerario.ajustado` es una
bandera de un solo sentido, no un estado; `perfil_prestador.promedio_valoracion`
es dato derivado; y la visibilidad de un comercio es consecuencia de su
verificación, no una máquina propia.

---

## Entidades

| Entidad | Estados | Terminal | Quién dispara la mayoría |
| --- | :-: | --- | --- |
| [Cuenta](cuenta.md) | 5 | `expulsada`, destrucción | Titular y supervisor |
| [Prestador](prestador.md) | 4 + 4 | `rechazada`, `vencida` | Moderador y proceso programado |
| [Circuito oficial](circuito.md) | 4 | `retirado` | Operador de alcaldía |
| [Itinerario](itinerario.md) | 4 | `eliminado` | Turista y sus visitas |
| [Convocatoria](convocatoria.md) | 4 | `adjudicada`, `cancelada`, `expirada` | Turista y calendario |
| [Reserva](reserva.md) | 7 | `cerrada`, `cancelada`, `expirada` | Turista, prestador y pasarela |
| [Cupón](cupon.md) | 3 + 4 | `consumido`, `expirado` | Comercio y turista |
| [Evento cultural](evento.md) | 4 | `finalizado`, `cancelado` | Institución y calendario |

## Eventos

| Proceso | Estados | Corre en paralelo a |
| --- | :-: | --- |
| [Verificación](verificacion.md) | 4 | Acreditación y organizaciones |
| [Sanción](sancion.md) | 2 | Cuenta |
| [Aviso](aviso.md) | 5 | Nada: es su propio ciclo |

---

## Cómo se lee un diagrama

| Símbolo | Significa |
| --- | --- |
| ● | Dónde nace la fila |
| ◎ | Dónde termina su ciclo |
| Borde continuo | Estado del que se puede salir |
| Borde punteado | Estado terminal |
| Etiqueta de la flecha | Quién o qué dispara la transición |

Una nota al costado señala una regla que el grafo no puede mostrar: que publicar
exige dos paradas, que `ajustado` no es un estado, que retirar una campaña no
toca los cupones ya entregados.

---

## Forma de la tabla de estados

Todas las tablas `estado_<entidad>` comparten columnas. Los atributos booleanos
son las preguntas que el sistema hace sobre el estado, para que agregar uno sea
insertar una fila y no repartir condicionales por el código.

| Columna | Tipo | Qué responde |
| --- | --- | --- |
| `codigo` | `varchar UK` | Cómo lo referencia el código |
| `etiqueta` | `varchar` | Cómo se muestra |
| `es_inicial` | `bool` | Con cuál nace la fila |
| `es_terminal` | `bool` | Desde cuál no se sale |
| `orden` | `smallint` | Cómo se ordena en un listado |

A esas cinco cada entidad suma las suyas: `estado_usuario.revoca_sesion`,
`estado_circuito.es_visible`, `estado_reserva.admite_cancelacion`.

`transicion_<entidad>` es de solo inserción y guarda estado de origen, estado de
destino, responsable, motivo e instante. El estado actual vive como llave foránea
en la propia entidad porque las consultas frecuentes no pueden pagar una
agregación sobre el historial.
