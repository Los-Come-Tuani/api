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
- **Funcionales:** 108
- **No funcionales:** 25

---

## Ámbitos

K'plan no es una aplicación sino un ecosistema de dos lados. El turista consume
la experiencia desde una aplicación móvil; los actores que producen la oferta
—alcaldías, comercios, guías, traductores e instituciones culturales— la
alimentan desde portales web distintos, y un equipo interno modera lo que se
publica. Los requerimientos se agrupan por superficie porque es la partición que
determina quién puede ejecutar cada comportamiento.

| Documento | Prefijo | Superficie | Total |
| --- | --- | --- | --- |
| [Plataforma](funcionales/plataforma.md) | `RF-S` | Servicios transversales a todas las superficies | 25 |
| [Aplicación móvil](funcionales/app-movil.md) | `RF-T` | Turista nacional y extranjero | 27 |
| [Portal de prestadores](funcionales/portal-prestadores.md) | `RF-P` | Guías turísticos y traductores | 18 |
| [Portal de comercios](funcionales/portal-comercios.md) | `RF-C` | MiPymes y emprendimientos | 12 |
| [Portal de alcaldías](funcionales/portal-alcaldias.md) | `RF-A` | Gobiernos locales de las Ciudades Creativas | 10 |
| [Portal de instituciones](funcionales/portal-instituciones.md) | `RF-I` | Casas de cultura, teatros y ticketeras | 6 |
| [Backoffice](funcionales/backoffice.md) | `RF-B` | Moderación y supervisión internas | 10 |

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

