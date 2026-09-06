---
hide:
  - toc
icon: lucide/calendar-check
---

# Contratación de acompañamiento

De la solicitud publicada al pago liberado. Es el flujo más largo del sistema y
el único donde intervienen las cuatro particiones: el turista pide, el sistema
media, el prestador presta y la pasarela sostiene el dinero mientras tanto.

El camino dibujado es el de la **convocatoria**. La reserva directa de un
recorrido en catálogo ([RF-T-18][rf-t-18]) salta los cuatro primeros pasos y
entra por «crea la reserva en pendiente de pago»; de ahí en adelante es idéntico.

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
flowchart TB
    classDef auto stroke-dasharray: 4 3

    inicio((inicio))
    fin(((fin)))

    subgraph pt["Turista"]
        direction TB
        t1["Publica la solicitud con rango<br/>de fechas, presupuesto e idioma"]
        t2["Compara perfiles, credenciales<br/>verificadas, tarifas y valoraciones"]
        t3{"¿Acepta alguna<br/>postulación?"}
        t4["Evalúa al prestador"]
    end

    subgraph ps["k'plan"]
        direction TB
        s1{"¿Fechas futuras y<br/>presupuesto positivo?"}
        s2["Difunde la convocatoria a los prestadores<br/>verificados de la zona, sin identidad del turista"]
        s3["Abre la sala de chat y bloquea<br/>teléfonos y correos"]
        s4["Adjudica: acepta esa postulación,<br/>descarta el resto y congela la tarifa"]
        s5["Crea la reserva en pendiente de pago"]
        s6["Retiene el dinero, confirma la reserva<br/>y revela las identidades en la sala"]
        s7["Marca la reserva en curso"]
        s8["Cierra la reserva, libera el pago<br/>menos la comisión y recalcula promedios"]
        s9["Expira la convocatoria"]
        s10["Expira la reserva"]
        sj["Espera las dos evaluaciones"]
    end

    subgraph pp["Guía o traductor"]
        direction TB
        p1["Revisa el tablero de solicitudes"]
        p2["Se postula y negocia tarifa<br/>y punto de encuentro"]
        p3["Presta el servicio en el territorio"]
        p4["Marca el servicio como prestado<br/>y evalúa al turista"]
    end

    subgraph pg["Pasarela de pago"]
        direction TB
        g1{"¿Confirma<br/>el cobro?"}
    end

    inicio --> t1
    t1 --> s1
    s1 -->|"no: devuelve el error"| t1
    s1 -->|sí| s2
    s2 --> p1
    p1 --> p2
    p2 --> s3
    s3 --> t2
    t2 --> t3
    t3 -->|"no, y llega la fecha de viaje"| s9
    s9 --> fin
    t3 -->|sí| s4
    s4 --> s5
    s5 --> g1
    g1 -->|"no, o vence el plazo"| s10
    s10 --> fin
    g1 -->|sí| s6
    s6 --> s7
    s7 --> p3
    p3 --> p4
    p4 --> t4
    p4 --> sj
    t4 --> sj
    sj --> s8
    s8 --> fin

    class s9,s10 auto
```

</div>

## Quién ejecuta cada paso

| Partición        | Pasos | Qué le corresponde                                                    |
| ---------------- | :---: | --------------------------------------------------------------------- |
| Turista          |   4   | Publicar lo que necesita, elegir con quién y evaluar al terminar      |
| `k'plan`         |  11   | Validar, difundir sin identidad, adjudicar, congelar precio y liberar |
| Guía o traductor |   4   | Buscar trabajo, postularse, prestar y evaluar                         |
| Pasarela de pago |   1   | Confirmar el cobro. Nada más                                          |

## Las tres decisiones

**¿Fechas futuras y presupuesto positivo?** Es validación de
[RF-T-15][rf-t-15] y devuelve al turista al mismo formulario. Se dibuja porque el
rechazo interrumpe el flujo: sin fechas válidas no hay a quién difundir la
convocatoria.

**¿Acepta alguna postulación?** La salida negativa no es «rechaza»: es que
llegue la fecha de viaje sin que haya aceptado ninguna. Ahí el proceso programado
cierra la convocatoria como `expirada`, y no hace falta un plazo aparte porque la
fecha ya estaba declarada en la convocatoria.

**¿Confirma el cobro?** Es la única decisión que no toma nadie del sistema. Si la
pasarela no confirma, la reserva nunca sale de `pendiente_pago` y termina
`expirada`. El plazo exacto antes de esa expiración
[sigue sin definirse](../estados/reserva.md).

## Dos cosas que ocurren en paralelo

Después de `marca el servicio como prestado`, el flujo se abre en dos: el
prestador ya evaluó al turista en ese mismo paso y el turista todavía tiene que
evaluar al prestador. `Espera las dos evaluaciones` es el punto donde vuelven a
juntarse, y la reserva no llega a `cerrada` hasta que lo hacen
([RF-S-22][rf-s-22], [RF-P-14][rf-p-14]).

El detalle es lo que impide cerrar el servicio con una sola voz. Mientras falte
una de las dos puntuaciones el dinero sigue retenido, que es el único incentivo
real para que la evaluación se emita.

## Lo que el diagrama deja fuera a propósito

La cancelación. Cualquiera de las dos partes puede cancelar mientras la reserva
esté `confirmada`, y con menos de veinticuatro horas de anticipación el motivo es
obligatorio y cuenta en la reputación de quien cancela. Dibujarlo habría exigido
una flecha desde casi cada caja; la tabla completa está en el
[diagrama de estados de la reserva](../estados/reserva.md#quien-puede-cancelar).

Tampoco aparece la contratación simultánea de guía y traductor
([RF-T-30][rf-t-30]). No es una bifurcación de este flujo: es este mismo flujo
recorrido dos veces, con dos convocatorias y dos reservas independientes.

[rf-p-14]: ../../requerimientos/funcionales/app-prestadores.md#rf-p-14
[rf-s-22]: ../../requerimientos/funcionales/plataforma.md#rf-s-22
[rf-t-15]: ../../requerimientos/funcionales/app-turista.md#rf-t-15
[rf-t-18]: ../../requerimientos/funcionales/app-turista.md#rf-t-18
[rf-t-30]: ../../requerimientos/funcionales/app-turista.md#rf-t-30
