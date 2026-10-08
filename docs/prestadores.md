---
icon: lucide/badge-check
---

# Guías y traductores

Cómo se postula un guía o un traductor desde la app, cómo lo revisa el equipo de K'Plan y
qué pasa cuando vence un documento. Es la fase F5 de la [hoja de ruta](hoja-de-ruta.md) y
sigue el [modelo de dominio](modelo-dominio/modulos/perfiles.md): guía y traductor comparten
perfil y proceso ([D-12](modelo-dominio/decisiones.md#d-12)), y lo que los distingue son los
servicios que ofrecen y el documento que los acredita.

## Lo que se decidió

- **Una cuenta, un papel** ([RF-S-26](requerimientos/funcionales/plataforma.md#rf-s-26)).
  Quien quiere ser guía o traductor crea una cuenta de prestador desde la app; un turista
  que quiere serlo usa otro correo. Mientras el equipo lo revisa, la cuenta solo ve el
  estado de su solicitud.
- **Documentos**: la cédula y el récord de policía a todos; la licencia del INTUR a los
  guías; el certificado de idiomas a los traductores; y la licencia de conducir y el seguro
  del vehículo a quien lleva turistas en su vehículo. El modelo solo prevé la credencial
  del servicio: los demás son una decisión del equipo.
- **Revisión en dos pasos**: quien revisa (`guides.review`) acepta o rechaza cada documento
  y, si algo está mal, pide correcciones; quien decide (`guides.decide`) aprueba o rechaza
  al final. Una renovación se resuelve con la revisión de su documento.
- **Vencimiento y renovación**: cada documento guarda su fecha de emisión y, si caduca, la
  de vencimiento. Un comando diario vence los documentos y suspende al prestador que se
  queda sin alguno de los que se le piden. Renovar un documento no interrumpe el trabajo.
- **Perfil público** editable desde la app: foto, presentación, idiomas y teléfono.

## El camino de una solicitud

```text
postulación (cuenta + perfil + documentos) ──► bandeja del equipo
                                                   │
           ┌───────────── toma ◄── devuelve ───────┤
           ▼                                       │
  revisa cada documento ──► alguno rechazado ──► pide correcciones ──► corrige y reenvía ──► otro expediente
           │
           └──► todos aceptados ──► decide ──► aprueba ──► perfil activo + rol de guía o traductor
                                        └────► rechaza con motivo ──► corrige y reenvía ──► otro expediente
```

- Rechazar no reabre el expediente: **corregir abre otro**, y el anterior se conserva con
  su motivo, como en las [organizaciones](organizaciones.md).
- Un documento aceptado no se vuelve a revisar al reenviar: pasa tal cual al expediente
  nuevo. Solo se revisa lo que se sube otra vez.
- Aprobar es lo único que vuelve al perfil `active` y le da a la cuenta el rol de **Guía**
  o de **Traductor** (los dos si ofrece ambos servicios). Con ese rol la app entra al modo
  de guía.

## Catálogos (públicos)

| Ruta                           | Qué trae                                                                                                                                    |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET catalog/city/`            | Las ciudades (las mismas de F3)                                                                                                             |
| `GET catalog/language/`        | Los idiomas: `id`, `code` (ISO 639-1, como `en`) y `label`                                                                                  |
| `GET catalog/service-type/`    | Lo que ofrece un prestador: `guia` y `traductor`                                                                                            |
| `GET catalog/credential-type/` | Los documentos: `code`, `label`, `service` (el servicio que acredita, o nulo si se le pide a todos), `requires_expiry` y `requires_vehicle` |

Los documentos que se le piden a una persona salen de ahí: los que no son de un servicio,
los del servicio que ofrece, y los de vehículo si lleva turistas en el suyo.

| `code`               | Documento                  | Se le pide a         | Vence |
| -------------------- | -------------------------- | -------------------- | :---: |
| `cedula`             | Cédula de identidad        | Todos                |  sí   |
| `record_policia`     | Récord de policía          | Todos                |  no   |
| `licencia_intur`     | Licencia o carné del INTUR | Guías                |  sí   |
| `certificado_idioma` | Certificado de idiomas     | Traductores          |  no   |
| `licencia_conducir`  | Licencia de conducir       | Quien lleva turistas |  sí   |
| `seguro_vehiculo`    | Seguro del vehículo        | Quien lleva turistas |  sí   |

## Postulación (app)

1. `GET catalog/...`: las listas del formulario.
2. `POST /auth/register-code/` con `{ "email" }`: el código de seis dígitos al correo.
3. `POST /upload/` por cada archivo, con `kind` `provider-document` (PDF, JPG o PNG de hasta
   10 MB), y subirlo con un `PUT` a la URL firmada ([Archivos](archivos.md)).
4. `POST /provider-application/` con la cuenta, el perfil y los documentos:

```json
{
  "email": "marlene@example.com",
  "code": "123456",
  "password": "...",
  "first_name": "Marlene",
  "last_name": "Ríos",
  "birth_date": "1990-05-01",
  "nationality": "NI",
  "services": ["guia"],
  "city_id": "…",
  "phone": "+505 8831 4476",
  "presentation": "Seis años en Granada: historia colonial y gastronomía.",
  "languages": [
    { "code": "es", "level": "native" },
    { "code": "en", "level": "advanced" }
  ],
  "carries_tourists": false,
  "documents": [
    {
      "type": "cedula",
      "number": "201-010190-0001A",
      "issued_on": "2020-01-10",
      "expires_on": "2030-01-10",
      "file_key": "provider-document/…"
    }
  ]
}
```

- `services`: `guia`, `traductor` o los dos. `city_id` nulo es todo el país (la cobertura
  nacional del INTUR); con una ciudad, opera solo ahí.
- `languages`: al menos uno, sin repetir, con `level` `basic`, `intermediate`, `advanced` o
  `native`.
- `documents`: exactamente uno por cada tipo que se le pide, y ninguno más. `issued_on` no
  puede ser futura; `expires_on` es obligatoria en los tipos que vencen, posterior a la
  emisión y a hoy (un documento vencido no se acepta). `number` es el folio del documento.
- `presentation` es lo que verá el turista (hasta 1000 caracteres).

Responde `201` con `{ "access", "refresh", "user", "application" }`: la cuenta queda dentro,
igual que con el inicio de sesión móvil. El `user` no tiene `role` todavía y trae
`provider` con `{ id, status: "in_review", services }`. `application` tiene la forma de
`mine/` (abajo).

Errores: `400` con `field_errors` si el código es malo o ya se usó, la contraseña es débil,
falta o sobra un documento (`body.documents`), un archivo no se subió o un campo no valida;
un correo que ya tiene cuenta no recibe código, así que falla igual que un código
equivocado. Todo ocurre en una transacción: si algo falla, el código vuelve a servir.

## Lo que ve quien se postuló

`GET /provider-application/mine/` devuelve su expediente más reciente (`404` si la cuenta no
es de un prestador):

| Campo        | Qué es                                                                                                                  |
| ------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `procedure`  | `application` (la postulación) o `renewal` (una renovación)                                                             |
| `status`     | `submitted`, `in_review`, `approved` o `rejected`                                                                       |
| `resolution` | Si se resolvió: `approved`, `reason` (`{ code, label }`), `note`, `resolved_at`                                         |
| `provider`   | El perfil: `id`, `status`, `services`, `approved_at`                                                                    |
| `profile`    | Lo que mandó, con la forma del reenvío: `services`, `city_id`, `phone`, `presentation`, `languages`, `carries_tourists` |
| `documents`  | Sus documentos vigentes, uno por tipo (abajo)                                                                           |
| `missing`    | Los tipos que se le piden y no tienen un documento utilizable                                                           |

Cada documento trae `id`, `type` (`{ code, label }`), `number`, `issued_on`, `expires_on`,
`file` (`{ key, url }`: la URL de lectura vence en minutos), `status` y `review`:

- `status`: `uploaded` (subido, sin resolver), `in_review`, `approved` (en vigor),
  `rejected`, `expired` o `replaced` (lo reemplazó uno más nuevo).
- `review`: lo que dijo quien revisó, o nulo: `accepted`, `reason`, `note` y
  `reviewed_at`. Un documento rechazado dice por qué, para corregirlo sin adivinar.

El perfil del prestador (`provider.status`) es `unaccredited` (sin acreditar: le pidieron
correcciones o lo rechazaron), `in_review`, `active` o `suspended`.

### Corregir y reenviar

`POST /provider-application/mine/resubmit/` corrige lo rechazado y lo manda de nuevo. Lleva
los datos del perfil (los mismos de la postulación, sin la cuenta) y en `documents` solo lo
que se sube otra vez. Responde `201` con la forma de `mine/`.

- Solo cuando la última postulación se rechazó (`409` si está en revisión o aprobada).
- Cada tipo que se pide tiene que quedar con un documento utilizable: los rechazados, los
  vencidos y los que faltan se suben de nuevo (`400` en `body.documents`). Uno que se sube
  otra vez reemplaza al anterior.

### Renovar un documento

`POST /provider-application/mine/renewal/` con `{ "documents": [...] }` (uno o más, de los
tipos que se le piden) abre un expediente de renovación. Solo para un prestador ya
aprobado (`active` o `suspended`) y sin otro expediente abierto (`409`). Mientras se revisa,
el documento anterior sigue en vigor: el prestador sigue trabajando. Si estaba suspendido,
vuelve a `active` cuando se aprueba lo que le faltaba.

## Perfil público

| Ruta                           | Qué hace                                                                                                          |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `GET provider-profile/mine/`   | El perfil: estado, servicios, ciudad, teléfono, presentación, foto, idiomas, documentos vigentes y los que faltan |
| `PATCH provider-profile/mine/` | Cambia `presentation`, `phone`, `languages` o `photo_key`                                                         |

- `photo_key` es la clave de un archivo subido con `kind` `provider-photo` (JPG, PNG o WEBP
  de hasta 5 MB); `null` quita la foto.
- Los cambios se ven de inmediato: son descriptivos y no pasan por la revisión
  ([RF-P-06](requerimientos/funcionales/app-prestadores.md#rf-p-06)). Los servicios y la
  ciudad no se cambian aquí: son parte de lo que se acredita.

La sesión (`user`) trae `provider` (`{ id, status, services }`) o nulo para quien no es
prestador.

## La cola del equipo

| Ruta                                          | Permiso                           | Qué hace                                 |
| --------------------------------------------- | --------------------------------- | ---------------------------------------- |
| `GET provider-request/`                       | `guides.view`                     | La bandeja, con filtros y páginas        |
| `GET provider-request/reason/`                | `guides.view`                     | Los motivos: `document` y `decision`     |
| `GET provider-request/{id}/`                  | `guides.view`                     | El expediente completo                   |
| `POST provider-request/{id}/take/`            | `guides.review` o `guides.decide` | La toma: queda en revisión y a su nombre |
| `POST provider-request/{id}/release/`         | `guides.review` o `guides.decide` | La devuelve a la cola                    |
| `POST provider-request/{id}/document-review/` | `guides.review` o `guides.decide` | Acepta o rechaza un documento            |
| `POST provider-request/{id}/request-changes/` | `guides.review` o `guides.decide` | Pide correcciones (cierra el expediente) |
| `POST provider-request/{id}/approve/`         | `guides.decide`                   | Aprueba al prestador                     |
| `POST provider-request/{id}/reject/`          | `guides.decide`                   | Lo rechaza con motivo                    |

- La bandeja acepta `status` (`open` por defecto: las enviadas y las que están en
  revisión; también `submitted`, `in_review`, `approved`, `rejected` o `all`), `service`
  (`guia` o `traductor`), `procedure` (`application` o `renewal`), `page` y `page_size`. Lo
  abierto sale por orden de llegada; lo cerrado, lo más reciente primero.
- Cada expediente dice en qué paso está (`stage`): `documents` mientras haya documentos sin
  revisar o alguno rechazado, y `decision` cuando todos los que se piden están aceptados
  (nulo si ya se resolvió). Trae también `counts`, la cuenta de sus documentos (`total`,
  `accepted`, `rejected`, `pending`).
- El expediente completo trae a la persona (`applicant`), su perfil, sus documentos (cada
  uno dice si se subió en este expediente, `in_this_request`, y si se pide, `required`), lo
  que falta (`missing`), la `resolution` y el `history` de los expedientes anteriores.
- `document-review` lleva `{ "document_id", "accepted" }` y, al rechazar, `reason` (de la
  lista `document`) y `note` (obligatoria con «otro»). Se revisan los documentos que se
  subieron en este expediente; mientras está abierto, la revisión se puede cambiar. Revisar
  sin tomar antes la toma; si la tiene otra persona, `409`.
- `request-changes` exige al menos un documento rechazado. Cierra el expediente como
  rechazado con el motivo «Hay documentos por corregir» y la `note`; el perfil vuelve a
  `unaccredited`.
- `approve` exige que cada documento que se pide esté aceptado y sin vencer (`409`). Decidir
  no exige tomar el expediente: quien decide puede hacerlo aunque lo tenga quien revisó.
- `reject` lleva un `reason` de la lista `decision` y `note` (obligatoria con «otro»).
- En una renovación no se decide: cuando el último documento queda revisado, el expediente
  se resuelve solo (aprobado si se aceptó todo). `approve` y `reject` responden `409`.
- Al resolver, la persona recibe un correo con la decisión y, si hay algo que corregir, qué
  y por qué.

## Vencimiento

`python src/manage.py expirecredentials` (una vez al día, con el cron de la plataforma):

1. Los documentos en vigor cuya fecha de vencimiento ya pasó quedan `expired`.
2. El prestador `active` que se queda sin un documento en vigor de alguno de los tipos que
   se le piden pasa a `suspended` y recibe un correo. Conserva su cuenta y su rol: entra a
   la app para renovar lo que venció, pero no aparece en búsquedas ni recibe
   contrataciones ([RF-P-05](requerimientos/funcionales/app-prestadores.md#rf-p-05)).

## Nombres

La base está en español y el código, las rutas y el JSON en inglés, como en F3.

| Tabla                                                                            | Modelo (Python)                                                            | App            |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | -------------- |
| `idioma`, `tipo_servicio`, `tipo_acreditacion`                                   | `Language`, `ServiceType`, `CredentialType`                                | `api_catalogs` |
| `estado_prestador`, `perfil_prestador`, `prestador_servicio`, `prestador_idioma` | `ProviderStatus`, `ProviderProfile`, `ProviderService`, `ProviderLanguage` | `api_profiles` |
| `estado_acreditacion`, `acreditacion`                                            | `CredentialStatus`, `Credential`                                           | `api_profiles` |

`solicitud_verificacion` suma `perfil_prestador_id` (el quinto objeto que se verifica) y
`tramite` (`alta` o `renovacion`).

Apartes del modelo, a propósito:

- El expediente es del **perfil**, no de cada acreditación como prevé el modelo: la
  revisión en dos pasos decide sobre la persona, y los documentos se revisan dentro de él.
  Cada documento guarda en qué expediente se subió y el veredicto de quien lo revisó.
- `tipo_acreditacion.tipo_servicio_id` admite nulo (el documento se le pide a todos) y suma
  `exige_vehiculo`; `estado_acreditacion` suma `reemplazada`.
- `perfil_prestador` suma `ciudad_id` (nulo es todo el país), `telefono` y
  `lleva_turistas`, y guarda la foto por su clave (`foto_clave`) mientras `foto` siga
  siendo del comercio.

## Lo que no está en F5

- Cambiar los servicios o la ciudad de un prestador ya aprobado.
- Avisar que un documento está por vencer (solo se avisa al suspender).
- Listar y buscar prestadores para el turista: llega con la contratación (F7).
- Las reseñas que alimentan `promedio_valoracion` y `total_resenas` (F7).
