---
hide:
  - toc
icon: lucide/shield-check
---

# Roles y permisos

`asignacion_rol` lleva tres llaves foráneas de ámbito y una restricción de
verificación que exige que a lo sumo una esté presente. Las tres nulas significan
alcance global, que es el caso del personal interno. `rol.ambito_requerido`
declara cuál de las tres exige cada rol, y un disparador comprueba que la
asignación la traiga.

Se eligió tres columnas nulables y no un par genérico de tipo e identificador
porque así cada referencia conserva su llave foránea real. Con un par genérico
nada impide apuntar a un comercio que ya no existe.

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
    direction LR
    rol {
        uuid id PK
        varchar codigo UK
        varchar etiqueta
        varchar ambito_requerido
        bool asignable
    }
    permiso {
        uuid id PK
        varchar codigo UK
        varchar recurso
        varchar accion
    }
    rol_permiso {
        uuid id PK
        uuid rol_id FK
        uuid permiso_id FK
        timestamptz concedido_en
    }
    asignacion_rol {
        uuid id PK
        uuid usuario_id FK
        uuid rol_id FK
        uuid alcaldia_id FK
        uuid comercio_id FK
        uuid institucion_id FK
        uuid otorgada_por FK
        timestamptz otorgada_en
        timestamptz revocada_en
    }
    usuario {
        uuid id PK
        citext email UK
    }
    alcaldia {
        uuid id PK
        uuid ciudad_id FK
    }
    comercio {
        uuid id PK
        varchar nombre_comercial
    }
    institucion_cultural {
        uuid id PK
        varchar nombre
    }
    rol ||--o{ rol_permiso : "agrupa"
    permiso ||--o{ rol_permiso : "se concede en"
    usuario ||--o{ asignacion_rol : "desempeña"
    rol ||--o{ asignacion_rol : "se otorga en"
    alcaldia ||--o{ asignacion_rol : "acota"
    comercio ||--o{ asignacion_rol : "acota"
    institucion_cultural ||--o{ asignacion_rol : "acota"
```

</div>

`asignacion_rol` no se borra: revocar es escribir `revocada_en`. Es lo que
permite responder quién tenía qué acceso el día en que ocurrió algo, que es
justamente lo que se pregunta después de un incidente.

| Restricción | Sobre | Por qué |
| --- | --- | --- |
| Verificación | A lo sumo una de las tres llaves de ámbito no es nula | Un rol se acota a un solo objeto |
| Verificación | El ámbito presente coincide con `rol.ambito_requerido` | Un operador de comercio no se asigna a una ciudad |
| Único parcial | Usuario y rol donde `revocada_en` es nula | Una persona no acumula el mismo rol dos veces |
| Único | `rol_permiso` por rol y permiso | Un permiso no se concede dos veces al mismo rol |
| Único | `permiso` por recurso y acción | El código es derivable, no una segunda fuente |

El permiso nunca se concede directamente a un usuario: no existe tabla
`usuario_permiso`. Retirar un acceso es siempre revocar una asignación de rol o
quitar un permiso del rol, en un solo lugar auditable.
