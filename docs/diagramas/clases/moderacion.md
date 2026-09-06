---
hide:
  - toc
icon: lucide/gavel
---

# Moderación y sanciones

Una sola cola de trabajo para cuatro objetos que no comparten ni una columna.
`Verificable` es la interfaz que lo hace posible sin obligar a la tabla común que
el modelo descarta.

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
classDiagram
    direction LR

    class Verificable {
        <<interface>>
        +documento_exigido() str
        +es_visible() bool
        +marcar_verificado(instante) None
    }

    class Acreditacion {
        +date vence_el
    }

    class Comercio {
        +str ruc
    }

    class Alcaldia {
        +str nombre
    }

    class InstitucionCultural {
        +str nombre
    }

    class SolicitudVerificacion {
        +datetime enviada_en
        +datetime resuelta_en
        +objeto() Verificable
        +tomar(moderador) None
        +devolver_a_cola() None
        +antiguedad() timedelta
    }

    class EstadoVerificacion {
        +str codigo
        +bool en_bandeja
        +bool es_terminal
    }

    class ResolucionVerificacion {
        <<solo insercion>>
        +bool aprobada
        +str nota
        +datetime resuelta_en
        +notificar() None
    }

    class Reporte {
        +str descripcion
        +int gravedad
        +datetime creado_en
        +datetime resuelto_en
        +resolver(responsable) None
    }

    class Sancion {
        <<solo insercion>>
        +bool permanente
        +str razon_interna
        +datetime dictada_en
        +datetime vence_en
        +esta_vigente(ahora) bool
        +dias_restantes(ahora) int
        +aplicar() None
    }

    class Usuario {
        +str correo
    }

    class Dispositivo {
        +str huella
    }

    Verificable <|.. Acreditacion
    Verificable <|.. Comercio
    Verificable <|.. Alcaldia
    Verificable <|.. InstitucionCultural
    Verificable "1" --> "0..1" SolicitudVerificacion : se somete a
    EstadoVerificacion "1" <-- "0..*" SolicitudVerificacion : estado actual
    SolicitudVerificacion "1" --> "0..1" ResolucionVerificacion : se cierra con
    Usuario "1" --> "0..*" ResolucionVerificacion : dicta
    Usuario "1" --> "0..*" Reporte : emite
    Usuario "1" --> "0..*" Reporte : es reportado en
    Reporte "1" --> "0..1" Sancion : puede originar
    Usuario "1" --> "0..*" Sancion : recibe
    Usuario "1" --> "0..*" Sancion : dicta
    Sancion "0..*" --> "0..1" Dispositivo : veta
```

</div>

## Qué agrega sobre el ER

**`Verificable` es interfaz y no superclase, y la diferencia importa.**
`Organizacion` sí es superclase de las tres organizaciones
([Organizaciones](organizaciones.md)), pero `Acreditacion` no es una
organización: es el documento de una persona. Lo único que las cuatro comparten
es que pasan por esta cola, y eso es exactamente lo que una interfaz expresa sin
inventar parentesco.

**`objeto()` reemplaza cuatro llaves excluyentes.** En el modelo físico,
`solicitud_verificacion` lleva `acreditacion_id`, `comercio_id`, `alcaldia_id` e
`institucion_cultural_id`, y a lo sumo una está presente. La operación devuelve
el verificable que sea, y el resto del módulo no vuelve a preguntar cuál.

**`antiguedad()` es el criterio de atención y por eso es operación.** La cola se
ordena por antigüedad de envío, de modo que ninguna solicitud quede
indefinidamente al final por falta de un criterio explícito
([RF-B-01][rf-b-01]).

**`ResolucionVerificacion` es de solo inserción y por eso no hay `reabrir()`.**
Rechazar es terminal para ese expediente: subsanar no lo reabre, el solicitante
carga un documento nuevo y eso genera otra solicitud. Así el historial conserva
cuántas veces se intentó y por qué se rechazó cada vez.

**`Sancion` es la causa y el estado de la cuenta es su consecuencia.**
`aplicar()` cambia el estado del usuario, revoca sus sesiones y, si es
permanente, cancela los servicios futuros que tuviera acordados
([RF-B-09][rf-b-09]). Sin la clase no habría historial de reincidencia y una
segunda suspensión borraría el rastro de la primera
([D-14](../../modelo-dominio/decisiones.md#d-14)).

**La asociación con `Dispositivo` es `0..1` y solo la usa la expulsión.** Cuando
la sanción es permanente, referencia el aparato desde el que operaba el
infractor, que es lo que sostiene el veto a crear cuentas nuevas desde el mismo
dispositivo ([RF-B-08][rf-b-08]). Una suspensión temporal deja esa asociación
vacía.

## Qué exige cada verificable

| Verificable           | Documento                                   | Consecuencia de aprobar mal                |
| --------------------- | ------------------------------------------- | ------------------------------------------ |
| `Acreditacion`        | Licencia del INTUR o certificado de idiomas | Un guía sin credencial atendiendo turistas |
| `Comercio`            | RUC y datos del formulario                  | Una ficha falsa en el mapa                 |
| `InstitucionCultural` | Documento de existencia legal               | Eventos inventados en la agenda            |
| `Alcaldia`            | Documento de representación                 | El sello oficial de una ciudad entera      |

`documento_exigido()` es lo que devuelve la segunda columna, y es abstracta
justamente porque la cuarta fila no se resuelve igual que las otras tres
([RF-A-11][rf-a-11]).

!!! warning "Un caso sin resolver"

    La resolución de una credencial vencida no cancela por sí sola las reservas
    comprometidas del prestador; la expulsión permanente sí, y abre los
    reembolsos que correspondan. Qué ocurre en el primer caso sigue sin definirse,
    y por eso `Sancion.aplicar()` no puede especificarse del todo todavía.

[rf-a-11]: ../../requerimientos/funcionales/portal-alcaldias.md#rf-a-11
[rf-b-01]: ../../requerimientos/funcionales/backoffice.md#rf-b-01
[rf-b-08]: ../../requerimientos/funcionales/backoffice.md#rf-b-08
[rf-b-09]: ../../requerimientos/funcionales/backoffice.md#rf-b-09
