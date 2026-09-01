---
hide:
  - toc
icon: lucide/list-tree
---

# Catálogos y parámetros

`parametro` guarda el valor como texto con su `unidad` aparte, porque el conjunto
mezcla metros, minutos, días y porcentajes. Convertir al tipo correcto es
responsabilidad de quien lo lee, y `grupo` permite cargar de una vez todos los
umbrales de un mismo dominio.

En el diagrama van solo las cuatro tablas con estructura. Las listas cerradas
comparten una forma tan simple que dibujarlas ocuparía el triple de espacio sin
decir nada.

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
    parametro {
        uuid id PK
        varchar clave UK
        varchar grupo
        varchar valor
        varchar unidad
        text descripcion
        bool editable
        timestamptz actualizado_en
    }
    parametro_cambio {
        uuid id PK
        uuid parametro_id FK
        varchar valor_anterior
        varchar valor_nuevo
        uuid cambiado_por FK
        text motivo
        timestamptz vigente_desde
    }
    motivo {
        uuid id PK
        varchar codigo UK
        varchar etiqueta
        bool exige_texto
        bool activo
    }
    motivo_contexto {
        uuid id PK
        uuid motivo_id FK
        varchar contexto
        smallint orden
    }
    moneda {
        uuid id PK
        char codigo UK
        varchar nombre
        smallint decimales
    }
    tasa_cambio {
        uuid id PK
        uuid moneda_origen_id FK
        uuid moneda_destino_id FK
        numeric tasa
        timestamptz vigente_desde
    }
    tipo_servicio {
        uuid id PK
        varchar codigo UK
        varchar etiqueta
    }
    tipo_acreditacion {
        uuid id PK
        varchar codigo UK
        varchar etiqueta
        uuid tipo_servicio_id FK
        bool exige_vencimiento
    }
    parametro ||--o{ parametro_cambio : "historiza"
    motivo ||--o{ motivo_contexto : "se ofrece en"
    moneda ||--o{ tasa_cambio : "cotiza"
    tipo_servicio ||--o{ tipo_acreditacion : "se acredita con"
```

</div>

## Listas cerradas

Todas comparten `id`, `codigo` único y `etiqueta`. El código nunca cambia aunque
cambie el texto que se muestra: es lo que referencian las reglas del sistema.

| Tabla | Columnas propias |
| --- | --- |
| `idioma` | `char codigo UK`, `varchar nombre`, `bool activo` |
| `pais` | `char codigo UK`, `varchar nombre` |
| `tipo_negocio` | `varchar codigo UK`, `varchar etiqueta`, `bool activo` |
| `tipo_beneficio` | `varchar codigo UK`, `varchar etiqueta`, `bool exige_monto` |
| `tipo_aviso` | `varchar codigo UK`, `varchar etiqueta`, `bool desactivable` |
| `pilar_cultural` | `varchar codigo UK`, `varchar etiqueta`, `varchar icono`, `smallint orden` |

`tipo_aviso.desactivable` es lo que impide que un usuario apague los avisos
transaccionales. `tipo_beneficio.exige_monto` distingue el descuento porcentual,
que necesita una cifra, del producto gratis, que no.

## Reglas

| Restricción | Sobre | Por qué |
| --- | --- | --- |
| Solo inserción | `parametro_cambio` | Revertir un umbral es insertar el cambio inverso, no borrar la fila |
| Único | `motivo_contexto` por motivo y contexto | Un motivo no aparece dos veces en la misma lista |
| Verificación | `tasa_cambio.tasa` mayor que cero | Una tasa nula o negativa rompe todo cálculo de conversión |
| Verificación | `tasa_cambio` con monedas distintas | Convertir una moneda a sí misma no tiene sentido |
| Único parcial | `tasa_cambio` por par de monedas y `vigente_desde` | Una sola tasa por par y fecha |
| Disparador | `parametro` con `editable` falso no se actualiza | Las vigencias de sesión y el umbral de edad no se tocan desde el portal |
