---
icon: lucide/shield-check
---

# Roles y permisos

Qué puede hacer cada persona en K'Plan, cómo se asigna y cómo se protege un endpoint.
Complementa a [Autenticación y cuentas](autenticacion.md).

## Cómo está armado

Un **rol** es un grupo de Django (`Group`) con un perfil (`ApiGroupProfile`) que dice
qué clase de grupo es y qué papel muestra:

| Campo                 | Para qué sirve                                                           |
| --------------------- | ------------------------------------------------------------------------ |
| `kind`                | `staff` (equipo de K'Plan), `operator` (negocios, alcaldías, instituciones) o `public` (turistas, guías, traductores) |
| `role`                | El papel que ven los clientes en `user.role` (ver abajo)                 |
| `requires_two_factor` | Quien tenga el rol debe activar el segundo factor                        |
| `is_system`           | Lo necesita el sistema: no se edita ni se borra desde el portal          |

Un **permiso funcional** es lo que una persona del equipo puede hacer (`guides.review`,
`users.manage`...). Llega siempre por un rol: los permisos que alguien tenga sueltos no
cuentan, ni los de una cuenta que no puede operar. Un superusuario tiene todos.

## Por dónde entra cada rol

| `kind`     | Entra por         | Ejemplos                              |
| ---------- | ----------------- | ------------------------------------- |
| `staff`    | Portal (`/auth/web/*`)    | Super admin, Verificador, Aprobador   |
| `operator` | Portal (`/auth/web/*`)    | Negocio, Alcaldía, Institución        |
| `public`   | App (`/auth/mobile/*`)    | Turista, Guía, Traductor              |

Por la otra superficie el inicio de sesión responde `401` con el mismo mensaje que una
contraseña mala: no se revela que la cuenta existe, y cuenta como intento fallido para
el bloqueo. Un superusuario y una cuenta sin grupos entran por las dos.

Si una cuenta tiene varios papeles, `user.role` muestra el de mayor rango:
`admin`, `alcaldia`, `institucion`, `negocio`, `guia`, `traductor`, `turista`.

## Catálogo de permisos

Los identificadores son los mismos que usa el portal (`src/data/models/access.ts`);
`GET /auth/staff-permission/` devuelve el catálogo con su etiqueta y descripción.

| Módulo              | Permisos                                                          |
| ------------------- | ----------------------------------------------------------------- |
| Agenda              | `agenda.view`                                                     |
| Organizaciones      | `organizations.view`, `organizations.review`, `organizations.manage` |
| Guías y traductores | `guides.view`, `guides.review`, `guides.decide`                   |
| Lugares             | `places.view`, `places.manage`                                    |
| Circuitos           | `circuits.view`, `circuits.manage`                                |
| Contenido           | `content.moderate`                                                |
| Facturación         | `billing.view`, `billing.manage`                                  |
| Equipo y usuarios   | `users.view`, `users.manage`, `staff.manage`                      |

**Quien puede más, puede ver.** `manage`, `review` y `decide` incluyen el `view` de su
módulo: un rol con `guides.decide` trae también `guides.view` en la sesión. El rol
guarda solo lo que se le asignó; la sesión trae lo ya expandido.

## Roles que trae el sistema

`manage.py apiauthseed` (y lo corre solo cada `migrate`, salvo `SKIP_SEEDERS=True`)
deja el catálogo y estos roles:

- **De sistema** (se vuelven a fijar en cada siembra): Administrador (todo; exige
  segundo factor), Cliente, Guía, Traductor, Negocio, Alcaldía e Institución.
- **De ejemplo del equipo** (se crean una vez; después se editan o se borran con
  libertad y volver a migrar no los pisa): Personal, Observador de guías y
  traductores, Verificador, Aprobador, Observador de negocios, Gestor de
  organizaciones y Moderador de contenido. Todos exigen segundo factor.

Un grupo creado a mano con `/auth/group/` no tiene perfil y por eso no aparece como rol
del equipo: el portal solo administra grupos con perfil `staff`.

Negocio, Alcaldía e Institución son roles de **operador** con ámbito: se dan sobre una
organización concreta con `asignacion_rol`, no solo por pertenecer al grupo. Ver
[Organizaciones y verificación](organizaciones.md#roles-con-ambito).

## Segundo factor obligatorio

Quien tiene un rol con `requires_two_factor` entra, pero mientras no active el 2FA solo
puede usar lo necesario para activarlo y lo mínimo de la cuenta (perfil, cambio de
contraseña, revocar sesiones y baja). Todo lo demás responde `403` con
`"Tu rol exige la verificación en dos pasos. Actívala para seguir."`. La sesión lo
anuncia en `user.two_factor` (`{ "enabled": false, "required": true }`), para que el
portal lleve a la persona a la página de seguridad. Mientras el rol lo exija, el 2FA
tampoco se puede desactivar (`403`).

## Gestión del equipo

Todo bajo `/auth/`. El permiso es el que pide cada ruta; `403` si falta.

| Ruta                                       | Permiso                      | Qué hace                                                |
| ------------------------------------------ | ---------------------------- | ------------------------------------------------------- |
| `GET staff-permission/`                    | `staff.manage`               | Catálogo de permisos                                    |
| `GET staff-role/`                          | `staff.manage` o `users.view`| Roles del equipo, con cuántas personas tiene cada uno   |
| `POST staff-role/`                         | `staff.manage`               | Crea un rol (`201`)                                     |
| `GET staff-role/{id}/`                     | `staff.manage` o `users.view`| Un rol                                                  |
| `PUT staff-role/{id}/`                     | `staff.manage`               | Cambia nombre, descripción, permisos y segundo factor   |
| `DELETE staff-role/{id}/`                  | `staff.manage`               | Borra un rol sin personas (`204`)                       |
| `GET staff-member/`                        | `staff.manage` o `users.view`| El equipo: cada persona con su rol del equipo (y los superusuarios, con `role: null`), por nombre |
| `POST staff-invite/`                       | `staff.manage`               | Invita a alguien al equipo (`201`)                      |
| `POST staff-accept/`                       | Pública (sin sesión)         | La persona invitada elige su contraseña (`204`)         |
| `POST user-role/`                          | `staff.manage`               | Cambia el rol de una persona del equipo                 |
| `POST user-status/`                        | `users.manage`               | Suspende o reactiva una cuenta                          |
| `POST user-password-reset/`                | `users.manage`               | Manda a la persona un código para crear otra contraseña |
| `GET user/`, `user/all/`, `user/{id}/`     | `users.view`                 | Ver a las personas (los permisos del modelo también sirven) |

Cuerpo de un rol: `{ "name", "description"?, "permissions": [...],
"requires_two_factor"? }` (el segundo factor es obligatorio salvo que se diga
`false`). Permisos desconocidos dan `400` con `body.permissions`; un nombre repetido,
`409` con `body.name`.

Reglas que protegen al equipo:

- Los roles de sistema no se editan ni se borran (`403`).
- Un rol con personas no se borra (`409`): primero se les cambia el rol.
- Nadie se quita a sí mismo `staff.manage` desde su rol, ni cambia su propio rol ni su
  propio estado (`403`): se quedaría sin poder deshacerlo.
- La última persona activa con el rol Administrador no se suspende ni se cambia de rol
  (`409`).
- Una cuenta de superusuario solo la administra otro superusuario (`403`).
- Los permisos se dan por rol. Escribir permisos sueltos de una persona
  (`/auth/user/{id}/permissions/`, y sus enlaces) es solo de un superusuario (`403`).
- Una persona del equipo tiene un solo rol del equipo; sus grupos de otra clase no se
  tocan.

### Invitación

1. `POST /auth/staff-invite/` `{ "email", "first_name", "last_name"?, "role_id" }` crea
   la cuenta **pendiente**, le da el rol y le manda un código de seis dígitos al correo.
   Responde `201` con la persona (`status: "pending"`) y `sent`.
2. La persona abre el portal y manda `POST /auth/staff-accept/` `{ "email", "code",
   "password" }`: la cuenta pasa a activa y verificada, y ya puede iniciar sesión. Un
   correo sin invitación y un código malo dan la misma respuesta; cinco códigos malos
   invalidan el vigente; una contraseña débil no gasta el código.
3. Reinvitar a una cuenta pendiente cambia su rol y manda otro código que reemplaza al
   anterior. Entre un correo y el siguiente hay una espera de 60 segundos: dentro de
   ella el rol se cambia pero no sale otro correo, y la respuesta trae `sent: false`
   (la persona usa el último código que recibió).

Un correo que ya tiene cuenta responde `409` con `body.email`.

## Proteger un endpoint

- **Un endpoint nuevo de dominio**: pedir el permiso al principio del método con
  `await ensure_permission(self.request.user, FunctionalPermissions.GUIDES_REVIEW)`
  (`api_auth.services.roles`). Pasa quien tenga **alguno** de los permisos dados.
- **Un controlador de modelo**: declarar `functional_permissions` por método HTTP, como
  `ApiUserFunctionalMixin` (`GET` → `users.view`). Los permisos del modelo de Django
  siguen valiendo; los funcionales se suman.
- En las pruebas, `make_role(nombre, *permisos)` y `make_member(correo, *permisos)`
  (`api_tests/conftest.py`) crean un rol y una persona del equipo con exactamente esos
  permisos; `web_login(client, user)` abre la sesión web. `test_team.py` tiene la matriz
  rol × endpoint: un endpoint nuevo se agrega a `MATRIX`.

## Al desplegar

- La siembra crea los perfiles de los grupos que ya existían con el nombre de un rol de
  sistema. **Administrador exige segundo factor**: quien lo tenga y no lo haya activado
  entra, pero solo podrá activarlo hasta que lo haga. Conviene que cada administrador
  active el suyo antes de cambiar nada más.
- Los permisos de los roles de ejemplo se asignan solo cuando se crean. Ajustarlos
  después es cosa del equipo desde el portal.
