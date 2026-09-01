---
hide:
  - toc
icon: lucide/notebook-pen
---

# Requerimientos

Qué debe hacer K'plan, expresado desde el negocio y no desde la
implementación. Un requerimiento describe un comportamiento observable por un
actor: no menciona tablas, endpoints, controladores ni sentencias de base de
datos. Esa traducción ocurre después, en el modelo de dominio, y siempre citando
de vuelta el requerimiento que la origina.

Cada requerimiento tiene un identificador estable de la forma `RF-<ámbito>-<nn>`
y un encabezado propio, de modo que pueda referenciarse desde los actores, los
casos de uso y las decisiones de diseño sin ambigüedad. Los identificadores no
se reutilizan: si un requerimiento se retira, su número queda vacante.

- **Ámbitos:** 7
- **Funcionales:** 116
- **No funcionales:** 25

---

## Ámbitos

K'plan no es una aplicación sino un ecosistema de dos lados. El turista consume
la experiencia desde una aplicación móvil; los actores que producen la oferta
—alcaldías, comercios e instituciones culturales— la alimentan desde portales
web, y un equipo interno modera lo que se publica. Guías y traductores no tienen
portal: comparten la aplicación móvil con el turista, porque como él trabajan en
la calle. Los requerimientos se agrupan por superficie porque es la partición que
determina quién puede ejecutar cada comportamiento.

| Documento | Prefijo | Superficie | Actores | Total |
| --- | --- | --- | --- | --- |
| [Plataforma](funcionales/plataforma.md) | `RF-S` | Transversal | todos | 26 |
| [App del turista](funcionales/app-turista.md) | `RF-T` | App móvil | Turista | 30 |
| [App de prestadores](funcionales/app-prestadores.md) | `RF-P` | App móvil | Guía, Traductor | 20 |
| [Portal de comercios](funcionales/portal-comercios.md) | `RF-C` | Web | Operador de comercio | 12 |
| [Portal de alcaldías](funcionales/portal-alcaldias.md) | `RF-A` | Web | Operador de alcaldía | 11 |
| [Portal de instituciones](funcionales/portal-instituciones.md) | `RF-I` | Web | Operador de institución | 7 |
| [Backoffice](funcionales/backoffice.md) | `RF-B` | Web | Moderador, Supervisor | 10 |

El documento de plataforma existe porque hay comportamientos que ninguna
superficie posee en exclusiva. La identidad, la mensajería, las valoraciones y
los avisos por cercanía son bilaterales por definición: el turista y el prestador
usan la misma sala de chat y se califican mutuamente. Documentarlos una sola vez
en el ámbito transversal evita repetir la misma regla en dos portales y que
después ambas copias diverjan.

---

## No funcionales

Las [restricciones de calidad](no-funcionales.md) que el sistema debe satisfacer
con independencia de la superficie: seguridad, privacidad, localización, límites
de contenido y trazabilidad. Solo se registran las que tienen respaldo en las
fuentes; cuando existe la necesidad pero no el valor, el requerimiento la nombra
y remite el número concreto a definición posterior.

---
