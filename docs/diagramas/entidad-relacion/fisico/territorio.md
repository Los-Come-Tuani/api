---
hide:
  - toc
icon: lucide/map
---

# Territorio y circuitos

Las coordenadas son dos columnas decimales con escala fija y rango verificado, no
un tipo geográfico nativo. Es la opción que funciona sin extensiones instaladas;
si el motor de producción las tiene, la columna cambia de tipo y las búsquedas
por radio dejan de aproximarse sobre un rectángulo.

`circuito_oficial.version` es un entero que un disparador incrementa cuando
cambia la geometría —altas, bajas o reordenamientos en `circuito_parada`— y solo
entonces. Editar el título no lo mueve, porque la aplicación usa ese número para
decidir si debe redibujar el trazado.

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
    ciudad {
        uuid id PK
        varchar codigo UK
        varchar nombre
        numeric latitud
        numeric longitud
        bool activa
    }
    alcaldia {
        uuid id PK
        uuid ciudad_id FK
        varchar nombre
        citext correo_contacto
        varchar telefono
        timestamptz dada_de_alta_en
    }
    punto_interes {
        uuid id PK
        uuid ciudad_id FK
        varchar nombre
        text descripcion
        numeric latitud
        numeric longitud
        bool activo
        timestamptz creado_en
    }
    circuito_oficial {
        uuid id PK
        uuid alcaldia_id FK
        varchar titulo
        text descripcion
        uuid foto_portada_id FK
        int version
        uuid estado_id FK
        timestamptz publicado_en
    }
    estado_circuito {
        uuid id PK
        varchar codigo UK
        varchar etiqueta
        bool es_visible
        bool admite_edicion
    }
    circuito_parada {
        uuid id PK
        uuid circuito_id FK
        uuid punto_interes_id FK
        smallint orden
        text indicacion
    }
    pilar_cultural {
        uuid id PK
        varchar codigo UK
        varchar etiqueta
        varchar icono
        smallint orden
    }
    punto_pilar {
        uuid id PK
        uuid punto_interes_id FK
        uuid categoria_id FK
    }
    foto {
        uuid id PK
        uuid punto_interes_id FK
        uuid circuito_id FK
        uuid comercio_id FK
        uuid evento_id FK
        varchar archivo_id
        varchar texto_alternativo
        smallint orden
    }
    ciudad ||--o| alcaldia : "es operada por"
    punto_interes ||--o{ punto_pilar : "se clasifica en"
    pilar_cultural ||--o{ punto_pilar : "clasifica"
    ciudad ||--o{ punto_interes : "contiene"
    alcaldia ||--o{ circuito_oficial : "publica"
    estado_circuito ||--o{ circuito_oficial : "clasifica"
    circuito_oficial ||--o{ circuito_parada : "ordena"
    punto_interes ||--o{ circuito_parada : "es visitado en"
    circuito_oficial ||--o{ foto : "se ilustra con"
    punto_interes ||--o{ foto : "se ilustra con"
```

</div>

`foto` usa el mismo patrón de referencias excluyentes que el ámbito de un rol:
cuatro llaves nulables y una verificación que exige exactamente una presente. Una
tabla de fotos por dueño habría duplicado cuatro veces las mismas columnas.

| Restricción | Sobre | Por qué |
| --- | --- | --- |
| Único | `alcaldia.ciudad_id` | Una sola alcaldía por ciudad |
| Verificación | Latitud entre 10.7 y 15.1; longitud entre -87.7 y -82.6 | El territorio nicaragüense; una coordenada fuera es un error de captura |
| Único | `circuito_parada` por circuito y orden, diferida | Reordenar intercambia posiciones dentro de una transacción |
| Único | `circuito_parada` por circuito y punto de interés | Un lugar no se visita dos veces en el mismo recorrido |
| Verificación | `foto` con exactamente una llave de dueño presente | Una foto pertenece a una sola cosa |
| Único | `punto_pilar` por punto y categoría | Un pilar no se asigna dos veces al mismo lugar |
| Disparador | Un circuito visible conserva al menos dos paradas | Un recorrido de un punto no se puede trazar |

La eliminación de un circuito restringe si tiene itinerarios que lo siguen: hay
que despublicarlo primero. La de un punto de interés anula la referencia en las
paradas de itinerario que lo copiaron, porque esas paradas ya guardan su propio
nombre y su propia coordenada y sobreviven sin él.
