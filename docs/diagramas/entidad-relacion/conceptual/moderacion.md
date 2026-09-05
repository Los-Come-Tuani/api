---
hide:
  - toc
icon: lucide/gavel
---

# Moderación y sanciones

<div align="center" markdown>

```mermaid
---
config:
  elk:
    mergeEdges: false
    nodePlacementStrategy: NETWORK_SIMPLEX
  fontFamily: monospace
  layout: elk
---
erDiagram
    Acreditacion |o--o| SolicitudVerificacion : "se somete a"
    Comercio |o--o| SolicitudVerificacion : "se somete a"
    Alcaldia |o--o| SolicitudVerificacion : "se somete a"
    InstitucionCultural |o--o| SolicitudVerificacion : "se somete a"
    SolicitudVerificacion ||--o| ResolucionVerificacion : "se cierra con"
    Usuario ||--o{ ResolucionVerificacion : "dicta"
    Motivo ||--o{ ResolucionVerificacion : "justifica"
    Usuario ||--o{ Reporte : "emite"
    Usuario ||--o{ Reporte : "es reportado en"
    Motivo ||--o{ Reporte : "clasifica"
    Reporte ||--o| Sancion : "puede originar"
    Usuario ||--o{ Sancion : "recibe"
    Usuario ||--o{ Sancion : "dicta"
    Sancion }o--o| Dispositivo : "veta"
```

</div>

`SolicitudVerificacion` es la cola de trabajo del equipo interno y admite cuatro
objetos mutuamente excluyentes: la acreditación de un prestador, o el registro de
un comercio, una alcaldía o una institución cultural. Las cuatro se registran
solas y ninguna existe para el turista antes de la aprobación. `ResolucionVerificacion` la cierra con quién decidió, cuándo y por qué, y el
motivo es obligatorio: un rechazo sin causa explicada obliga a reintentar a
ciegas.

`Sancion` es la causa y el estado de la cuenta es su consecuencia. Sin la tabla
no habría historial de reincidencia y una segunda suspensión borraría el rastro
de la primera. Cuando la sanción es una expulsión permanente, referencia también
el dispositivo desde el que operaba el infractor, que es lo que sostiene el veto
a crear cuentas nuevas desde el mismo aparato.

La resolución de una credencial vencida no cancela por sí sola las reservas
comprometidas del prestador; la expulsión permanente sí, y abre los reembolsos
que correspondan. Qué ocurre en el primer caso sigue sin definirse.
