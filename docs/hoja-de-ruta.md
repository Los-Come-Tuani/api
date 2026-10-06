---
icon: lucide/map
---

# Hoja de ruta del API

Qué está hecho, qué sigue y qué hay que decidir antes de cada fase. Las fases F0 a F2 ya
están en el API; de F3 en adelante cada fase **se confirma con el equipo antes de
empezar**. Es un mapa, no un contrato: el contrato de cada ruta nace con su fase, en el
OpenAPI (`/openapi/`) y en una guía como [Autenticación y cuentas](autenticacion.md) o
[Roles y permisos](roles.md).

El diseño de fondo ya existe y manda: el [modelo de dominio](modelo-dominio/index.md)
(módulos M1 a M16 y sus [decisiones](modelo-dominio/decisiones.md)), los
[requerimientos](requerimientos/index.md) y los [diagramas](diagramas/estados/index.md).
Cada fase parte de ahí; esta página solo las ordena y dice qué falta resolver.

## Hecho

| Fase | Qué trae                                                                                         | Módulos     |
| ---- | ------------------------------------------------------------------------------------------------ | ----------- |
| F0   | Secretos fuera de git (gitleaks), configuración por entorno, 2FA cifrado y probado               | M2          |
| F1   | Identidad: correo, registro con código, contraseña, perfil, baja, Google; portal y app enlazados | M2          |
| F2   | Roles y permisos funcionales, superficies por rol, 2FA obligatorio, equipo e invitaciones        | M3 (parte)  |
| F3   | **API hecha**: alta pública de comercios, instituciones y alcaldías, cola de verificación, roles con ámbito y archivos. Falta adaptar el portal ([guía](organizaciones.md)) | M1, M3, M5, M7, M14 |

### Dónde F2 se aparta del modelo (a propósito)

F2 usa los grupos de Django con un perfil (`ApiGroupProfile`) y permisos funcionales
(`guides.review`...), el "andamiaje" que [D-03](modelo-dominio/decisiones.md#d-03) reconoce.
Cumple lo esencial (el permiso solo llega por rol, y un permiso suelto solo lo asigna un
superusuario) pero **no** modela todavía lo que pide [M3](modelo-dominio/modulos/roles.md):

- `rol` con `ambito_requerido` (`global`, `alcaldia`, `comercio`, `institucion`) y
  `asignable`.
- `asignacion_rol` con el ámbito tipado ([D-02](modelo-dominio/decisiones.md#d-02)), quién
  la otorgó y `revocada_en` (revocar es escribir la fecha, no borrar).
- Permisos como `recurso` + `accion` en lugar de identificadores funcionales.

Eso entra con **F3**, que es cuando existen las organizaciones y las alcaldías a las que
se asignan los operadores. Mientras tanto Negocio, Alcaldía e Institución existen como
roles de sistema sin personas.

## Cómo se construye cada fase

1. **Contrato primero**: se proponen las rutas con la convención del router actual
   (recurso en singular, `kebab-case`, barra final, sin prefijo `/api`), se confirman con
   el equipo y recién entonces se escribe código. Antes de publicar la app se versiona con
   `/v1/`.
2. **Una app de Django por dominio** (como `api_auth`), con modelos que heredan de
   `ApiModel` (historial y triggers incluidos), esquemas estrictos, servicios y
   controladores delgados. Las tablas siguen los regímenes de auditoría de
   [D-31](modelo-dominio/decisiones.md#d-31) y las [convenciones](modelo-dominio/convenciones.md).
3. **Permisos desde el primer endpoint**: cada ruta pide un permiso funcional con
   `ensure_permission` o `functional_permissions` (ver [Roles y permisos](roles.md)).
   Quien opera una organización solo ve lo suyo: un objeto ajeno responde `404`, no `403`.
4. **Pruebas**: cada fase agrega su fila a la matriz rol × endpoint, casos de `403`/`404`
   y el contrato lo comprueba `schemathesis` contra `/openapi/`.
5. **Clientes**: el portal alinea su sección de `endpoints.ts`, su repositorio y su
   handler de demo; la app reemplaza el origen de datos de prueba por el del API.
6. **Guía y memoria**: la fase termina con su guía en `docs/` y con la memoria de
   `.cursor/memory` al día.

## Lo que cruza todas las fases

- **El portal no coincide del todo con el modelo.** El portal trata a negocios y
  alcaldías como una sola `Organization`; el modelo ([D-12](modelo-dominio/decisiones.md#d-12))
  las separa en `comercio`, `institucion_cultural` y `alcaldia`, que casi no comparten
  datos. El API manda el contrato: portal y app adaptan sus repositorios. Es lo primero que
  hay que confirmar en F3.
- **Estados y transiciones.** El modelo pide una fila de transición por cada cambio de
  estado, con quién y por qué ([D-13](modelo-dominio/decisiones.md#d-13), `RF-S-10`).
  Hoy el cambio de estado de una cuenta queda en el historial de la tabla (`pghistory`),
  sin motivo. Decidir si cada fase crea sus tablas `transicion_*` o se amplía el historial.
- **Catálogos** (M1): motivos de rechazo o corrección, parámetros y monedas se necesitan
  desde la primera decisión de admisión.
- **Archivos**: las solicitudes llevan documentos y fotos. Hace falta decidir dónde viven
  (volumen, bucket S3 o equivalente), el tamaño máximo, los tipos permitidos y cómo se
  sirven (URL firmada). Es la ruta `upload/`.
- **Trabajos programados**: destruir la cuenta a los 30 días de la baja (ya existe el
  estado `closing`), vencer códigos y generar cobros. Decidir cómo se ejecutan (cron de la
  plataforma o una cola).
- **Correo y avisos**: hoy el correo sale por `EMAIL_*`. Los avisos a la app necesitan un
  proveedor de notificaciones push.
- **Tiempo real**: el chat entre turista y guía puede empezar con consultas periódicas y
  pasar a WebSocket (el API es ASGI) cuando haga falta.

## F3. Organizaciones y admisión

Para qué: que un comercio, alcaldía o institución se postule, el equipo la revise y entre
a administrar sus lugares. Módulos: **M7** (organizaciones), **M3** (`asignacion_rol` con
ámbito), **M14** (verificación) y la parte de **M5** que son las alcaldías.

**Estado: el API está hecho; falta el portal.** Lo que se decidió con el equipo antes de
empezar:

- Manda el modelo de dominio: comercio, institución cultural y alcaldía por separado, con
  una sola cola de verificación. El portal se adapta.
- Alcance: el núcleo (alta pública de las tres, cola con aprobar, rechazar con motivo y
  corregir y reenviar, y operadores con ámbito). La solicitud asistida con cobro y el
  pedido de otro lugar quedan fuera.
- Archivos: un bucket compatible con S3 con URLs firmadas ([Archivos](archivos.md)).
- Quien se postula entra al portal con acceso limitado a su solicitud mientras la revisan,
  con el correo verificado por el código del alta.
- Nombres: la base de datos en español, como pide el modelo; el código, las rutas y el
  JSON en inglés.

Lo que se hizo y lo que sigue está en [Organizaciones y verificación](organizaciones.md).
La tabla de abajo era la propuesta inicial; las rutas reales son las de esa guía.

| Recurso (propuesta)                         | Lo usa      | Permiso                                   |
| ------------------------------------------- | ----------- | ----------------------------------------- |
| `organization/`, `organization/{id}/`       | Portal      | `organizations.view` / `manage`           |
| `organization/{id}/stop/` (asignar lugares) | Portal      | `organizations.manage`                    |
| `organization-application/` y `mine/`       | Portal      | Quien se postula; el equipo `organizations.view` |
| `organization-application/{id}/` `assign`, `document`, `resubmit`, `advance`, `request-changes`, `decision` | Portal | `organizations.review` (decidir: `manage`) |
| `organization-application/assisted/`        | Portal      | `organizations.review`                    |
| `place-request/` y su `decision`            | Portal      | `organizations.review`                    |
| `upload/`                                   | Portal, app | Sesión                                    |

Antes de empezar, confirmar: cómo se parten las organizaciones del portal en las tres
tablas del modelo; el flujo de estados de la solicitud (ver [verificación](diagramas/estados/verificacion.md)
y [prestador](diagramas/estados/prestador.md)); dónde se guardan los archivos; y la
migración de F2 a `rol` + `asignacion_rol` con ámbito.

## F4. Territorio y circuitos

Para qué: los lugares, sus fichas, las publicaciones y los circuitos que ve la app.
Módulos: **M5** (ciudades, puntos de interés, circuitos oficiales) y **M1** (pilares
culturales).

| Recurso (propuesta)                                   | Lo usa      | Permiso                              |
| ----------------------------------------------------- | ----------- | ------------------------------------ |
| `stop/`, `stop/available/` (pública), `stop/{id}/`    | Portal, app | `places.view` / `manage`; el dueño edita lo suyo |
| `stop/{id}/profile/` (ficha)                          | Portal      | Dueño de la parada o `places.manage` |
| `post/`                                               | Portal, app | Dueño o `content.moderate`           |
| `circuit/`, `circuit/{id}/`                           | Portal, app | `circuits.view` / `manage`           |
| `circuit/{id}/group-session/` (horarios de grupo)     | App         | Guía del circuito                    |

Antes de empezar, confirmar: borradores y publicación de una ficha editada por su dueño;
el circuito oficial se versiona ([D-15](modelo-dominio/decisiones.md#d-15)); el catálogo
de ciudades; y qué datos de mapa guarda el API y cuáles siguen en la app.

## F5. Guías y traductores

Para qué: que alguien se postule como guía o traductor desde la app, el equipo verifique
sus documentos y antecedentes, y quede aprobado. Módulos: **M4** (perfil de prestador y
acreditaciones) y **M14** (solicitudes de verificación).

| Recurso (propuesta)                                   | Lo usa      | Permiso                               |
| ----------------------------------------------------- | ----------- | ------------------------------------- |
| `guide-application/`, `{id}/`, `reviewers/`           | Portal      | `guides.view`                         |
| `guide-application/{id}/` `assign`, `document`, `background/{tipo}`, `advance`, `request-changes` | Portal | `guides.review` |
| `guide-application/{id}/decision/`                    | Portal      | `guides.decide`                       |
| `guide-application/mine/` y reenvío                   | App         | Turista que se postula                |
| `tour-guide/` (perfil, cobertura, estado)             | App         | Guía aprobado                         |

Al aprobar, la cuenta recibe el rol público de guía o traductor (un grupo con `kind`
`public`). Guía y traductor comparten tabla y proceso
([D-12](modelo-dominio/decisiones.md#d-12)). Antes de empezar, confirmar: los antecedentes
que se verifican y quién los verifica; los plazos por etapa; qué ve el solicitante cuando
se le pide una corrección.

## F6. Eventos, cupones e insignias

Para qué: la oferta que publican las organizaciones y que modera el equipo. Módulos:
**M8** (agenda cultural) y **M12** (insignias y cupones).

| Recurso (propuesta)                                   | Lo usa      | Permiso                               |
| ----------------------------------------------------- | ----------- | ------------------------------------- |
| `event/`, `event/{id}/`, `event/{id}/moderation/`     | Portal, app | Organización; moderar: `content.moderate` |
| `coupon/`, `coupon-redemption/` y su `validate`       | Portal, app | Negocio; canje en la app              |
| `badge-activation/`, `badge-campaign/` y su `cancel`  | Portal, app | Organización; moderar: `content.moderate` |
| `visit-event/` (agenda de llegadas)                   | Portal, app | `agenda.view`                         |

Antes de empezar, confirmar: la política de moderación (antes o después de publicar), los
límites de cupones por negocio y cómo se acredita una visita (QR, ubicación o ambos; una
por establecimiento cada 24 horas, `RF-S-15`). Los saldos de insignias son libros de
movimientos ([D-24](modelo-dominio/decisiones.md#d-24)).

## F7. Contratación, chat y reseñas

Para qué: lo que pasa entre el turista y el guía una vez aprobado. Módulos: **M6**
(itinerarios), **M9** (recorridos, convocatorias, postulaciones y reservas), **M10**
(mensajería) y **M11** (reputación).

Recursos de la app (los modelos ya están en `mobile-1`): `itinerary`, `guide-request`,
`booking`, `guide-job`, `guide-chat-thread` y `guide-chat-message`, `trip` y su avance, y
reseñas. Son de roles públicos (`/auth/mobile/*`); el equipo solo necesita lectura para
atender incidencias.

Antes de empezar, confirmar: el ciclo de una reserva (estados, cancelación, plazos;
ver [reserva](diagramas/estados/reserva.md)); la tarifa que se congela en la reserva
([D-20](modelo-dominio/decisiones.md#d-20)); tiempo real del chat; moderación de reseñas.

## F8. Finanzas y notificaciones

Para qué: cobrar a las organizaciones, pagar a los guías y avisar a todos. Módulos:
**M13** (pagos, comisiones, saldos y retiros), **M15** (notificaciones) y lo que quede de
**M14** (reportes y sanciones).

| Recurso (propuesta)                         | Lo usa      | Permiso                                   |
| ------------------------------------------- | ----------- | ----------------------------------------- |
| `billing/statement/` y su `pay`             | Portal      | Organización; el equipo `billing.view`    |
| `pricing/`                                  | Portal      | `billing.view` / `manage`                 |
| `guide-withdrawal/`                         | App, portal | Guía; el equipo `billing.manage`          |
| Notificaciones y preferencias               | App, portal | Sesión                                    |

Antes de empezar, confirmar: la pasarela de pago disponible en Nicaragua, la moneda y
cómo se conciliarán los cobros; la cuenta bancaria de desembolso se cifra y su cambio
espera 24 horas ([D-09](modelo-dominio/decisiones.md#d-09), [D-10](modelo-dominio/decisiones.md#d-10));
el proveedor de notificaciones push y los correos del sistema.

## Cómo se confirma una fase

Antes de escribir código, para cada fase: (1) el equipo revisa las rutas propuestas y las
preguntas de su sección; (2) se deja por escrito lo decidido en esta página; (3) se corta
una rama desde `develop-a`; (4) al terminar, se actualizan las guías, la memoria y el
checklist de cada cliente.
