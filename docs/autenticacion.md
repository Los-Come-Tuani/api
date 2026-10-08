---
icon: lucide/lock-keyhole
---

# Autenticación y cuentas

Contrato de identidad para el portal y la app. La fuente de verdad de cada ruta es el
OpenAPI en `/openapi/`; esta guía explica cómo se encadenan.

## Dos formas de sesión

|                   | App móvil (`/auth/mobile/*`)          | Portal web (`/auth/web/*`)               |
| ----------------- | ------------------------------------- | ---------------------------------------- |
| Credenciales      | `access` y `refresh` en el cuerpo     | Cookies `HttpOnly` (`access`, `refresh`) |
| Dónde se guardan  | Almacenamiento seguro del dispositivo | El navegador; el JavaScript no las ve    |
| CSRF              | No aplica                             | Cabecera `X-CSRFToken` en cada `POST`    |
| Cómo se autentica | `Authorization: Bearer <access>`      | La cookie `access` viaja sola            |

Para el portal: llamar a `GET /auth/csrf/` una vez (devuelve `204` con la cabecera
`x-csrftoken`) y mandar ese valor en `X-CSRFToken` en todo `POST`. Las peticiones
deben ir con `credentials: 'include'`, y portal y API deben compartir el sitio (en
desarrollo, `localhost` en los dos).

El `access` vive tres horas y el `refresh` un día. Renovar rota el par: el `refresh`
es de un solo uso y presentarlo dos veces falla.

## Inicio de sesión

`POST /auth/mobile/login/` y `POST /auth/web/login/` con `{ "email", "password" }`.

- **`200`**: sesión abierta. Trae `user` con la forma de la sección _Usuario de la
  sesión_ (y los tokens en el cuerpo solo en móvil).
- **`202`**: la cuenta tiene 2FA. Trae un `challenge` (móvil, en el cuerpo; web, en la
  cookie `challenge`). Se completa con `POST .../two-factor/` y `{ "code" }` (y
  `challenge` en móvil). El código es el TOTP de seis dígitos o un código de
  recuperación.
- **`401`**: credenciales inválidas. El mensaje es el mismo exista o no el correo, y
  también cuando el rol de la cuenta no entra por esa superficie (el equipo y los
  negocios entran por el portal; turistas, guías y traductores, por la app). Ver
  [Roles y permisos](roles.md).
- **`403`**: la contraseña era correcta pero la cuenta no puede operar (pendiente,
  suspendida, expulsada o en baja). El mensaje dice por qué. Solo se revela con la
  contraseña correcta.
- **`429`**: cinco intentos fallidos seguidos sobre el mismo correo bloquean el acceso
  quince minutos, exista o no la cuenta. Trae `Retry-After`.

El correo se compara sin importar mayúsculas ni espacios en los extremos. El
`username` es un alias opcional y **no** sirve para iniciar sesión.

## Inicio de sesión con Google

`POST /auth/mobile/google/` y `POST /auth/web/google/` con `{ "id_token",
"birth_date"?, "nationality"? }` devuelven lo mismo que el inicio de sesión (`200`, o
`202` si la cuenta tiene 2FA).

- **Móvil**: solo turistas, guías y traductores. La primera vez puede crear la cuenta y
  entonces exige también `birth_date` y `nationality`.
- **Portal**: solo negocios, alcaldías, instituciones y equipo. No crea cuentas: enlaza
  una cuenta existente, activa y con correo verificado; manda únicamente `id_token`.

Configuración completa en [Inicio de sesión con Google](google.md).

## Registro (app)

1. `POST /auth/register-code/` con `{ "email" }` → `204`. Manda un código de seis
   dígitos al correo (vence en 15 minutos; no se reenvía antes de 60 segundos). Responde
   igual si el correo ya tiene cuenta, pero en ese caso no manda nada.
2. `POST /auth/register-verify/` con `{ "email", "code" }` → `204` si el código sirve.
   No lo gasta: es para que la app avance en el formulario. Cinco códigos equivocados
   lo invalidan.
3. `POST /auth/register/` con `{ "email", "code", "password", "first_name",
"last_name"?, "birth_date", "nationality", "username"? }` → `201` con el usuario de
   la sesión. Gasta el código. La cuenta nace activa, verificada y con el rol de
   turista; después se llama a `login`.

Reglas: contraseña de al menos ocho caracteres con una mayúscula y un número,
`birth_date` en formato `YYYY-MM-DD` y mayor de 18 años, `nationality` con el código de
país de dos letras (`NI`, `US`). Una contraseña débil no gasta el código.

## Contraseña

- `POST /auth/password-forgot/` `{ "email" }` → `204`. Manda un código si la cuenta
  existe y puede operar; responde igual si no.
- `POST /auth/password-reset/` `{ "email", "code", "password" }` → `204`. Cambia la
  contraseña y cierra todas las sesiones.
- `POST /auth/password-change/` (con sesión) `{ "current_password", "password" }` →
  `204`. También cierra todas las sesiones: hay que volver a entrar.

## Perfil y sesión

- `GET /auth/profile/` devuelve el usuario de la sesión. `PATCH /auth/profile/` acepta
  `first_name`, `last_name`, `nationality` y `username` (con `null` se borra). El correo
  **no** se puede cambiar desde aquí: mandarlo da `400`.
- `POST /auth/session-revoke/` cierra la sesión en todos los dispositivos.
- `POST /auth/account-close/` `{ "password" }` pide la baja: la cuenta queda inactiva
  treinta días (`effective_at`) y se cierran las sesiones. `POST /auth/account-restore/`
  `{ "email", "password" }` la reactiva dentro del plazo.

## Usuario de la sesión

```json
{
  "id": "0194c1a2-...",
  "email": "ana@example.com",
  "first_name": "Ana",
  "last_name": "Gómez",
  "name": "Ana Gómez",
  "username": null,
  "birth_date": "1990-05-17",
  "nationality": "NI",
  "status": "active",
  "verified": true,
  "role": "turista",
  "groups": [{ "id": 3, "name": "Cliente" }],
  "permissions": [],
  "organization_id": null,
  "organization": null,
  "provider": null,
  "two_factor": { "enabled": false, "required": false },
  "created_at": "2026-10-05T21:40:00Z"
}
```

`status` es `pending`, `active`, `suspended`, `expelled` o `closing`. `role` es
`admin`, `alcaldia`, `guia`, `institucion`, `negocio`, `traductor`, `turista` o `null`.

`organization` es la organización sobre la que actúa la persona (su asignación de rol
vigente): `{ "id", "kind": "business" | "institution" | "municipality", "name",
"verified" }`, con `organization_id` repetido; `null` para quien no es de una organización.
Mientras `verified` es `false` solo ve su solicitud
([Organizaciones](organizaciones.md)).

`provider` es el perfil de guía o traductor: `{ "id", "status": "unaccredited" |
"in_review" | "active" | "suspended", "services": ["guia", "traductor"] }`; `null` para
quien no es prestador. Mientras lo revisan, la cuenta no tiene `role` todavía y solo entra
por la app; con la aprobación recibe `guia` o `traductor`
([Guías y traductores](prestadores.md)).

`permissions` son los permisos funcionales que le dan sus roles, ya con los que se
deducen (`guides.decide` trae `guides.view`), por ejemplo `["guides.decide",
"guides.view", "users.view"]`. `two_factor.required` es `true` cuando algún rol de la
cuenta exige el segundo factor. Detalle en [Roles y permisos](roles.md).

## Segundo factor (TOTP)

Con sesión: `GET /auth/two-factor/` (estado), `POST /auth/two-factor-setup/` (devuelve
`secret` y la URI `otpauth://` para el QR), `POST /auth/two-factor-confirm/` `{ "code" }`
(activa y devuelve diez códigos de recuperación, una sola vez),
`POST /auth/two-factor-recovery/` `{ "code" }` (genera diez nuevos) y
`POST /auth/two-factor-disable/` `{ "code", "password" }`.

El secreto se guarda cifrado (`TOTP_ENCRYPTION_KEYS`), cada código sirve una sola vez y
cinco fallos bloquean la verificación quince minutos.

## Errores

Todos los errores comparten la forma `{ "detail": "...", "field_errors": { "body.campo":
"..." } }`. Los de validación (`400`) traen el campo en `field_errors` con el prefijo de
dónde viaja (`body.`, `query.`...).
