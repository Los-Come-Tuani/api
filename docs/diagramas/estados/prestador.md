---
hide:
  - toc
icon: lucide/badge-check
---

# Prestador y acreditación

Dos máquinas en paralelo. El perfil es visible mientras tenga **al menos una**
acreditación en `aprobada` y sin vencer; en cuanto la última vence, el proceso
programado lo suspende sin que nadie abra la aplicación.

Renovar no reactiva la acreditación vencida: crea una fila nueva que recorre su
propio ciclo. Es lo que permite conservar el historial de licencias de un guía.

## Perfil del prestador

<div align="center" markdown>

```mermaid
---
config:
  fontFamily: monospace
---
stateDiagram-v2
    direction TB
    [*] --> sin_acreditar : crea su perfil
    sin_acreditar --> en_revision : carga su acreditación
    en_revision --> activo : el moderador aprueba
    en_revision --> sin_acreditar : rechaza con motivo
    activo --> suspendido : vence su acreditación
    suspendido --> activo : aprueban una nueva

    note right of suspendido
      Cancela sus reservas
      confirmadas
    end note
```

</div>

| Estado | `es_visible` | `acepta_reservas` |
| --- | :-: | :-: |
| `sin_acreditar` | no | no |
| `en_revision` | no | no |
| `activo` | **sí** | **sí** |
| `suspendido` | no | no |

`suspendido` conserva el acceso: el prestador entra a la aplicación para
regularizar sus papeles y atender los servicios ya comprometidos, pero no aparece
en búsquedas ni recibe contrataciones nuevas.

## Acreditación

<div align="center" markdown>

```mermaid
---
config:
  fontFamily: monospace
---
stateDiagram-v2
    direction TB
    classDef terminal stroke-dasharray: 4 3

    [*] --> cargada : adjunta el documento
    cargada --> en_revision : el moderador la toma
    en_revision --> aprobada : documento válido
    en_revision --> rechazada : rechaza con motivo
    aprobada --> vencida : llega el vencimiento
    rechazada --> [*]
    vencida --> [*]

    class rechazada,vencida terminal
```

</div>

Solo `aprobada` acredita. Una acreditación `vencida` no se reabre y una
`rechazada` tampoco: en ambos casos el prestador carga un documento nuevo.

Pasar a `suspendido` **cancela sus reservas confirmadas** y avisa a cada turista
con tiempo para buscar otro prestador, con reembolso íntegro. Ningún servicio se
presta sin acreditación vigente: es la misma regla que impide que aparezca en
búsquedas.

El prestador conserva el acceso a la aplicación para regularizar sus papeles y
consultar su historial, pero no puede prestar ni captar.
