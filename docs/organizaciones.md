---
icon: lucide/store
---

# Organizaciones y verificación

Cómo se postulan los comercios, las instituciones culturales y las alcaldías, y cómo el
equipo de K'Plan las revisa. Es la fase F3 de la [hoja de ruta](hoja-de-ruta.md) y
sigue el [modelo de dominio](modelo-dominio/modulos/organizaciones.md): las tres clases
de organización viven en tablas separadas ([D-12](modelo-dominio/decisiones.md#d-12)) y
una sola cola de verificación las resuelve a todas.

## El camino de una solicitud

```text
quien se postula ──► alta (cuenta + organización + expediente) ──► bandeja del equipo
                                                                      │
                          ┌──────────── toma ◄── devuelve ────────────┤
                          ▼                                           │
                    en revisión ──► aprueba ──► la organización es visible
                          │
                          └──► rechaza con motivo ──► correo ──► corrige y reenvía ──► otro expediente
```

- Mientras el equipo revisa, quien se postuló **entra al portal con acceso limitado a su
  solicitud**: su correo ya está verificado con el código del alta.
- Ninguna organización existe para el turista antes de la aprobación. La aprobación es
  lo único que escribe `verificado_en` en la ficha, y lo hace un disparador de la base.
- Rechazar no reabre el expediente: **subsanar abre otro**, y el rechazado se conserva con
  su motivo y su nota, para saber cuántas veces se intentó y por qué falló cada una.

## Alta pública (portal)

Cuatro pasos del cliente, todos sin sesión salvo el último, que la deja abierta:

1. `GET /catalog/city/`, `/catalog/business-type/` y `/catalog/institution-type/`: las
   listas de los formularios, públicas.
2. `POST /auth/register-code/` con `{ "email" }`: manda el código de seis dígitos al
   correo (el mismo del registro de la app; ver [Autenticación](autenticacion.md)).
3. `POST /upload/` por cada archivo y subirlo con la URL firmada (ver [Archivos](archivos.md)):
   la foto del platillo (`signature-dish-photo`) o el documento legal (`legal-document`).
4. `POST /organization-application/business/`, `/institution/` o `/municipality/`, con la
   cabecera `X-CSRFToken`, los datos de la cuenta y los de la organización.

Los datos de la cuenta son los mismos en las tres: `email`, `code`, `password`,
`first_name` y `last_name`. Los de la organización:

| Clase       | Datos                                                                                         |
| ----------- | --------------------------------------------------------------------------------------------- |
| `business`  | `city_id`, `business_type_id`, `ruc`, `name`, `address`, `phone`, `alternate_phone`?, `latitude`, `longitude`, `hours`, `signature_dish` |
| `institution` | `city_id`, `institution_type_id`, `name`, `contact_email`, `phone`, `document_key`          |
| `municipality` | `city_id`, `name`, `contact_email`, `phone`, `document_key`                                |

- `hours`: una fila por día (`weekday` 0 = domingo a 6 = sábado), cada una con `closed`
  o con `opens` y `closes` (`"08:00"`); un cierre anterior a la apertura significa
  madrugada, y el mismo día no va dos veces.
- `signature_dish`: `name`, `description`?, `reference_price`, `currency` (`NIO` o `USD`)
  y `photo_key`, la clave que devolvió `POST /upload/`.
- `latitude` y `longitude` tienen que caer en el territorio nicaragüense. El `ruc` tiene de
  13 a 16 letras, números o guiones (formato provisional: ninguna fuente define el oficial).
- `document_key` es la clave del documento que acredita la existencia legal de la
  institución o la representación de quien solicita por la alcaldía.

Responde `201` con `{ "user", "application" }` y **abre la sesión en cookies**, igual que
el inicio de sesión del portal. El `user` trae `role` (`negocio`, `institucion` o
`alcaldia`) y `organization` (`{ id, kind, name, verified }`).

Errores: `400` si el código es malo o ya se usó, la contraseña es débil, un archivo no se
subió o un campo no valida (con `field_errors`); `409` si el RUC, el nombre de la
institución en esa ciudad o la ciudad de la alcaldía ya están registrados (en `body.ruc`,
`body.name` y `body.city_id`). Un correo que ya tiene cuenta no recibe código, así que
el alta falla igual que con un código equivocado.

Todo ocurre en una transacción: la cuenta, la organización, el expediente y el rol de
operador con el ámbito de esa organización. Si algo falla, el código del correo vuelve a
servir.

## La solicitud de quien se postuló

- `GET /organization-application/mine/` devuelve la solicitud más reciente: `status`
  (`submitted`, `in_review`, `approved` o `rejected`) y, si se resolvió, `resolution` con
  el motivo (`reason`) y la nota del equipo. `404` para quien no es de una organización.
- `POST /organization-application/mine/resubmit/` corrige lo rechazado y lo manda de nuevo.
  Recibe los mismos datos del alta, sin la cuenta y con `kind` (`business`, `institution`
  o `municipality`). Responde `201` con la solicitud nueva.
  - Solo se puede cuando el último expediente se rechazó: en revisión (`409`) y aprobada
    (`409`) no se toca.
  - Corrige la misma ficha, que sigue sin verificar. En el comercio se reemplazan los
    horarios y el platillo (se retira el vigente y se inserta el nuevo).

## La cola del equipo

| Ruta                                    | Permiso                                    | Qué hace                                         |
| --------------------------------------- | ------------------------------------------ | ------------------------------------------------ |
| `GET verification-request/`             | `organizations.view`                       | La bandeja, con filtros y páginas                |
| `GET verification-request/reason/`      | `organizations.view` o `review`            | Los motivos que se ofrecen al rechazar           |
| `GET verification-request/{id}/`        | `organizations.view`                       | El expediente completo                           |
| `POST verification-request/{id}/take/`  | `organizations.review` o `manage`          | La toma: queda en revisión y a su nombre         |
| `POST verification-request/{id}/release/` | `organizations.review` o `manage`        | La devuelve a la cola                            |
| `POST verification-request/{id}/approve/` | `organizations.review` o `manage`        | Aprueba: la organización se hace visible         |
| `POST verification-request/{id}/reject/`  | `organizations.review` o `manage`        | Rechaza con motivo                               |

- La bandeja trae `status` (`open` por defecto, que son las enviadas y las que están en
  revisión; también `submitted`, `in_review`, `approved`, `rejected` o `all`), `kind`,
  `page` y `page_size`. Lo abierto sale **por orden de llegada**; lo cerrado, lo más
  reciente primero.
- El expediente trae a quien se postuló (`applicant`), los datos de la organización según
  su `kind`, los `documents` con una URL de lectura de cinco minutos (el bucket es
  privado), la `resolution` y el `history` de los expedientes anteriores.
- Tomar no le quita a otra persona lo que ya tiene en revisión (`409`); soltar la de otra
  persona exige `organizations.manage`. Aprobar o rechazar sin tomar antes la toma.
- Rechazar exige un `reason` de los que ofrece `reason/`; con «otro» hay que escribir la
  `note` (`400` con `body.reason` o `body.note`).
- Al resolver, quien se postuló recibe un correo con la decisión, con el motivo y la nota
  si se rechazó.

## Roles con ámbito

Negocio, Alcaldía e Institución son roles de sistema con **ámbito**: en
`ApiGroupProfile.scope` dicen sobre qué objeto actúa quien los tiene. La tabla
`asignacion_rol` (`RoleAssignment`) da el rol sobre una organización concreta, con quién
lo otorgó y `revocada_en` (revocar escribe la fecha, no borra). La base comprueba que el
ámbito de la asignación sea el que exige el rol, y que una asignación revocada no se
reactive. La asignación también mete a la persona en el grupo del rol, de donde salen su
papel (`user.role`) y la superficie por la que entra (el portal).

La sesión trae `organization` y `organization_id` de la asignación vigente. Lo que todavía
no existe es el 404 sobre objetos de otra organización: llega con los primeros recursos
que un operador administra (lugares, eventos, cupones).

## Nombres

La base de datos está en español, como pide el modelo (`comercio`, `ciudad`, `alcaldia`,
`solicitud_verificacion`, `asignacion_rol`...), con `db_table` y `db_column`. El código
Python, las rutas y el JSON siguen en inglés. Las tablas de `api_auth` se renombrarán en
otra fase.

| Tabla                    | Modelo (Python)        | App                |
| ------------------------ | ---------------------- | ------------------ |
| `ciudad`, `alcaldia`     | `City`, `Municipality` | `api_territory`    |
| `comercio`, `comercio_horario`, `platillo_estrella`, `foto`, `institucion_cultural` | `Business`, `BusinessHours`, `SignatureDish`, `Photo`, `CulturalInstitution` | `api_organizations` |
| `tipo_negocio`, `tipo_institucion`, `motivo`, `motivo_contexto`, `moneda` | `BusinessType`, `InstitutionType`, `Reason`, `ReasonContext`, `Currency` | `api_catalogs` |
| `estado_verificacion`, `solicitud_verificacion`, `resolucion_verificacion` | `VerificationStatus`, `VerificationRequest`, `VerificationResolution` | `api_moderation` |
| `asignacion_rol`         | `RoleAssignment`       | `api_roles`        |

Dos apartes del modelo, a propósito: `alcaldia` e `institucion_cultural` guardan su
documento en `documento_id` (el modelo solo lo prevé en la institución), y `foto` vive en
`api_organizations` mientras su único dueño sea el comercio.

## Lo que no está en F3

- La solicitud asistida por el equipo (con cobro de alta) y el pedido de otro lugar.
- La lista de organizaciones del equipo («Todas»), suspender una organización y editar la
  ficha ya aprobada.
- Más de un operador por organización (invitar a otras personas) y la baja de un
  operador.
- La suscripción del comercio (`suscripcion`) y el reemplazo del platillo estrella por su
  dueño (`RF-C-05`).
- Limpiar los archivos subidos que nadie reclama, y el aviso de bienvenida.
