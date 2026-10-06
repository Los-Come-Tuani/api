# Memoria de trabajo: hoja de ruta del API de K'Plan

Actualizada el 2026-10-06. Es el traspaso para el siguiente agente: qué está hecho, qué
falta y cómo trabajar en esta máquina. Léela completa antes de tocar código. Si algo de
aquí ya no es cierto, corrígelo en el mismo commit en que lo cambies.

## 1. De dónde viene esto

- Plan aprobado por el usuario: "Hoja de ruta API K'Plan (portal + app móvil)". El archivo
  está fuera del repo (`C:\Users\PDesarrollo\.cursor\plans\hoja_de_ruta_api_k'plan_4fa012a7.plan.md`):
  se puede leer, **no editarlo**.
- Alcance aprobado: **F0, F1 y F2**. Las fases F3 a F8 son un mapa; cada una se confirma con
  el usuario antes de empezar.
- Hay tres repos. Cada uno tiene `.cursor/memory/hoja-de-ruta.md` con su parte:

| Repo   | Ruta                          | Rama de trabajo          | Memoria                                   |
| ------ | ----------------------------- | ------------------------ | ----------------------------------------- |
| API    | `C:\development\kplan\api`    | `develop-a`              | este archivo |
| Portal | `C:\development\kplan\portal` | `feat/hoja-de-ruta-api` (sale de `main`) | `.cursor/memory/hoja-de-ruta.md` |
| App    | `C:\development\mobile-1`     | `feat/hoja-de-ruta-api` (sale de `main`) | `.cursor/memory/hoja-de-ruta.md` |

- **Remotos (revisado el 2026-10-06, tarde).** `origin/develop-a` del API llega a `ac38063`
  (F0, F1, F2 y F3 hasta la guía de organizaciones; empujado el 2026-10-06 a las 14:23).
  **Solo local en el API**: desde `c0d3ca6` (`submitted` en `mine/`, el
  centro de las ciudades, el `PUT` firmado que pide R2, `GET /auth/staff-member/` y las
  memorias); lo empujado todavía sube con el formulario `POST`, que R2 no admite. Portal y
  app: `origin/feat/hoja-de-ruta-api` sigue en F0 (2026-10-05); el enlace de F1, F2 y F3 es
  local. No empujes sin que el usuario lo pida: un push a `develop-a` puede disparar un
  despliegue sin las variables nuevas (ver sección 9), y lo ya empujado trae
  `TOTP_ENCRYPTION_KEYS` como obligatoria con `DEPLOY=True`.
- Nunca commitear en `production` ni en `staging`. Portal y app no tienen rama de
  desarrollo: no tocar su `main`.
- Commits convencionales en español (`feat(auth): ...`, `docs: ...`). Sin emojis.

## 2. Estado de las tareas

| Tarea                   | Estado                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------- |
| f0-secrets-gitignore    | Hecha (3 repos)                                                                     |
| f0-env-config           | Hecha (3 repos)                                                                     |
| f0-totp-migration-tests | Hecha (API)                                                                         |
| f1-api-identity         | Hecha (API)                                                                         |
| f1-google-login         | Hecha en el API y en la app, con guía (`docs/google.md`). El portal no lo usa: Google es solo para roles públicos |
| f1-portal-link          | Hecha (portal, rama `feat/hoja-de-ruta-api`). Ver `portal/.cursor/memory`           |
| f1-app-link             | Hecha (app, rama `feat/hoja-de-ruta-api`). Ver `mobile-1/.cursor/memory`            |
| f2-roles-permissions    | **Hecha** en el API, el portal (permisos, invitación, equipo y roles) y la app (modo guía según el rol). "Todos los usuarios" del portal sigue en demo (sección 7) |
| f3-f8-roadmap           | Hecha (documentación: `docs/hoja-de-ruta.md`); cada fase de dominio se confirma antes |
| F3 (organizaciones)     | **Hecha** en el API y en el portal (alta, estado, corregir y la cola del equipo). Falta crear el bucket real (sección 7b) |

Siguiente paso recomendado: que el usuario elija la fase de dominio que sigue (F4 en adelante,
`docs/hoja-de-ruta.md`). Pendientes chicos que no dependen de una fase: el directorio de
cuentas para "Todos los usuarios" del portal (sección 7) y crear el bucket real (sección 7b).

## 3. Qué hay hecho en el API

- **Secretos (F0)**: `.gitignore` (`.env.*` salvo `.env.example`, llaves, keystores,
  `client_secret*.json`, cuentas de servicio, dumps), `.dockerignore`, `.gitleaks.toml`,
  hook `gitleaks` en `.prek.toml` y `.github/workflows/secrets.yml`. `compose.yml` publica
  Postgres y Redis solo en `127.0.0.1`.
- **Config por entorno (F0)**: `src/api_core/config.py`. `ALLOWED_HOSTS`,
  `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` salen de variables (listas separadas por
  comas); los valores por defecto de desarrollo incluyen `localhost:5173` y `10.0.2.2`.
  `TOTP_ENCRYPTION_KEYS` es obligatoria con `DEPLOY=True`. `hide_input_in_errors=True`
  evita que un error de configuración muestre secretos. `.env.example` lista todo.
- **2FA cifrado (F0)**: el secreto TOTP va cifrado con Fernet (`services/crypto.py`,
  `MultiFernet` para rotar). Comando `rotatetotpkeys`. Migración `0003_totp_secret_encrypted`
  (la `0002_two_factor`, que crea las tablas del 2FA, ya venía en `develop-a`).
- **Identidad (F1)**: inicio de sesión por correo (el `username` es alias opcional y no
  sirve para entrar); estado de cuenta (`pending`, `active`, `suspended`, `expelled`,
  `closing`); bloqueo de 5 intentos por 15 minutos por correo tecleado (429 con
  `Retry-After`); registro con código por correo (nacionalidad y fecha de nacimiento >= 18);
  olvidé, restablecer y cambiar contraseña; `GET/PATCH /auth/profile/`; baja de cuenta a 30
  días con restauración; revocación inmediata de sesiones (`sessions_revoked_at`);
  perfil de sesión con rol, permisos, organización y estado de 2FA.
- **Google (F1)**: `POST /auth/mobile/google/` y `POST /auth/web/google/` con ID token;
  identidad externa en `ApiExternalIdentity`; solo roles públicos; solo se vincula a cuentas
  con correo verificado; `GOOGLE_OAUTH_CLIENT_IDS`. Guía paso a paso: `docs/google.md`.
- **Roles y permisos (F2)**: ver sección 7 y `docs/roles.md`.
- **Organizaciones (F3)**: alta pública de comercio, institución cultural y alcaldía, cola
  de verificación del equipo, roles con ámbito y archivos en un bucket S3. Ver sección 7b y
  `docs/organizaciones.md`.
- **Modelos nuevos**: `ApiLoginAttempt`, `ApiLoginLock`, `ApiVerificationCode` y
  `ApiExternalIdentity` (`models/security.py`), y `ApiGroupProfile` (`models/role.py`).
  Migraciones `0004_identity` (con relleno de datos), `0005_external_identity` y
  `0006_group_profile`.
- **Pruebas**: unas 512, más los casos que genera `schemathesis` contra `/openapi/` (597 en
  la última corrida completa, unos 2 minutos si nada más usa la base). Cubren config, TOTP, cifrado,
  login, 2FA, registro, contraseña, perfil, baja, bloqueo, modelos, Google, roles, equipo,
  organizaciones, archivos y la cola de verificación.
- **Docs**: `docs/autenticacion.md` (contrato de identidad para portal y app),
  `docs/roles.md` (roles, permisos y equipo), `docs/google.md`, `docs/guia.md`,
  `docs/hoja-de-ruta.md` (F3 a F8 con rutas propuestas y decisiones pendientes) y
  `README.md` (secretos y ejecución local).

Contrato completo y vigente: `docs/autenticacion.md`, `docs/roles.md` y el OpenAPI en
`/openapi/`. **El diseño de fondo del dominio ya existe** en `docs/modelo-dominio/` (módulos
M1 a M16 y decisiones D-01 a D-33), `docs/requerimientos/` y `docs/diagramas/`: cada fase de
dominio parte de ahí, no de los modelos del portal ni de la app.

`organization_id` del usuario de la sesión sigue siendo `null` hasta F3 (organizaciones).

## 4. Rutas que consumen los clientes

Todas sin prefijo `/api`, con barra final:

- CSRF (portal): `GET /auth/csrf/` -> 204 con la cabecera `x-csrftoken`.
- Sesión portal: `POST /auth/web/login/`, `/auth/web/two-factor/`, `/auth/web/refresh/`,
  `/auth/web/logout/`. Cookies `HttpOnly` `access`, `refresh` y `challenge`. Todo `POST`
  lleva `X-CSRFToken`, y también cualquier método no seguro con sesión por cookie.
- Sesión app: `POST /auth/mobile/login/`, `/auth/mobile/two-factor/` (`{challenge, code}`),
  `/auth/mobile/refresh/` (`{refresh}`), `/auth/mobile/logout/`, `/auth/mobile/google/`.
- Cuenta: `POST /auth/register-code/`, `/auth/register-verify/`, `/auth/register/`,
  `/auth/password-forgot/`, `/auth/password-reset/`, `/auth/password-change/`,
  `/auth/account-close/`, `/auth/account-restore/`, `/auth/session-revoke/`;
  `GET/PATCH /auth/profile/`.
- 2FA con sesión: `GET /auth/two-factor/` (200 `{confirmed_at, enabled, pending,
  recovery_codes}`), `POST /auth/two-factor-setup/` (201 `{secret, uri}`),
  `POST /auth/two-factor-confirm/` (201 `{codes}`), `POST /auth/two-factor-recovery/`
  (201 `{codes}`), `POST /auth/two-factor-disable/` (204; `{code, password}`).
- Equipo (F2): `GET /auth/staff-permission/`, `GET|POST /auth/staff-role/`,
  `GET|PUT|DELETE /auth/staff-role/{id}/`, `GET /auth/staff-member/` (el equipo con su rol;
  los superusuarios con `role: null`), `POST /auth/staff-invite/`,
  `POST /auth/staff-accept/` (pública), `POST /auth/user-role/`, `POST /auth/user-status/`,
  `POST /auth/user-password-reset/`. Detalle y permisos en `docs/roles.md`.
- Organizaciones (F3): `GET /catalog/city|business-type|institution-type/` (públicas; la
  ciudad trae su centro), `POST /upload/` (pública; devuelve una URL para un `PUT` firmado),
  `POST /organization-application/business|
  institution|municipality/` (portal: cookies y CSRF; deja la sesión abierta),
  `GET /organization-application/mine/` (con `submitted`: lo que mandó, para corregir),
  `POST /organization-application/mine/resubmit/` (devuelve lo mismo que `mine/`).
  Cola del equipo: `GET /verification-request/`, `.../reason/`, `.../{id}/` y
  `POST .../{id}/take|release|approve|reject/`. Detalle en `docs/organizaciones.md`.
- Errores: `{ "detail": "...", "field_errors": { "body.campo": "..." } }`. El 429 trae
  `Retry-After`.
- Local: API en `http://localhost:8080`, portal en `http://localhost:5173` (usar `localhost`
  en los dos: mezclarlo con `127.0.0.1` vuelve las cookies cross-site). Emulador Android:
  `http://10.0.2.2:8080`.

## 5. Portal y app (F1)

Hechos y verificados contra el API real (prueba de integración, navegador real y prueba de
contrato en Dart). El detalle de cada uno está en su propia memoria:
`C:\development\kplan\portal\.cursor\memory\hoja-de-ruta.md` y
`C:\development\mobile-1\.cursor\memory\hoja-de-ruta.md`. En la app falta decidir el
`applicationId` y el bundle id definitivos **antes** de crear los Client ID de Google, y el
inicio de sesión con Apple en iOS.

## 6. Qué cambia para los clientes con F2

- El inicio de sesión móvil solo admite turista, guía y traductor; el web, equipo y
  operadores. Un rol ajeno recibe el mismo `401` que una contraseña mala.
- `user.permissions` ahora son IDs funcionales (`guides.review`, `users.manage`...) en vez
  de códigos de permiso de Django, ya con los que se deducen (`guides.decide` -> `guides.view`).
- `user.two_factor.required` es `true` si algún rol de la cuenta exige el segundo factor:
  hasta activarlo, todo responde `403` salvo lo necesario para activarlo.
- `user.role` sale del perfil del grupo (`ApiGroupProfile.role`), ya no del nombre.

## 7. F2 roles y permisos

**Hecho en el API** (commit `feat(auth): roles, permisos funcionales y gestión del equipo`):

- `catalog.py`: 17 permisos con los IDs del portal más los de solo lectura, con etiqueta en
  español, y `expand_implied` (`manage`/`review`/`decide` incluyen `view`).
- `models/role.py`: `ApiGroupProfile` (`kind` staff/operator/public, `role`,
  `requires_two_factor`, `is_system`). Los permisos funcionales son filas `Permission`
  bajo el tipo de contenido de `ApiGroupProfile`.
- `seeder.py` (`manage.py apiauthseed`, corre solo tras cada `migrate`): catálogo, roles
  de sistema (se vuelven a fijar) y roles de ejemplo (se crean una vez). El Administrador
  tiene todo.
- `services/roles.py`: permisos efectivos (solo vía rol; superusuario todo), `role_of`,
  `ensure_permission`, superficies (`SURFACES_BY_KIND`) y 2FA obligatorio
  (`ensure_two_factor_enrolled`, que `JwtRbacAsyncAuth` llama antes de los permisos;
  `allows_pending_two_factor = True` en los controladores que sirven para activarlo).
- `services/team.py` y `controllers/team.py`: roles del equipo, invitación (con y sin
  espera entre correos: `sent`), aceptar invitación, estado, rol y recuperación de
  contraseña de otra persona; con las protecciones de `docs/roles.md`.
- `users.view` abre `GET /auth/user/`, `/auth/user/all/` y `/auth/user/{id}/`
  (`ApiUserFunctionalMixin`); los permisos de modelo de Django siguen valiendo.
- D-03 (el permiso solo se da por rol): los permisos sueltos que escriben
  `/auth/user/{id}/permissions/` (PUT, PATCH) y su enlace (PUT, DELETE) son solo de
  superusuario (`superuser_only`, `SUPERUSER_ONLY_DETAIL`).
- Pruebas: `test_roles.py` (catálogo, siembra, sesión, superficies, 2FA, `users.view`) y
  `test_team.py` (matriz rol x endpoint, CRUD de roles, invitación, estado, rol y
  recuperación).

- `GET /auth/staff-member/` (`StaffMemberController`, `staff_members_sync`): el equipo para
  la pantalla "Equipo interno" del portal; pide `staff.manage` o `users.view`. Sin ella el
  portal no tenía cómo listar al equipo (`/auth/user/` no filtra por clase de rol).

**Portal: hecho** (ver su memoria). Permisos `*.view` en el menú y las rutas, 2FA obligatorio
que lleva a Seguridad, `/invitacion`, y las pantallas "Equipo interno" y "Roles y permisos"
contra `/auth/staff-*` (reinvitar respeta `sent: false`; quitar el acceso pide `users.manage`).

**App: hecho.** El modo guía sigue al `role` de la sesión: `guia` y `traductor` lo tienen,
`turista` no. Con el API configurado, la postulación desde la app queda cerrada con un aviso
(no hay ruta todavía: llega con F5); la demo conserva el flujo simulado.

**Falta de F2**:

- **Todos los usuarios** (portal): sigue en demo. Hace falta un directorio de cuentas con el
  rol derivado (`role_of`), filtros por rol y estado y búsqueda, para que el portal deje
  `/api/users`. Con eso pasa también "Mandar código para nueva contraseña"
  (`POST /auth/user-password-reset/`, que ya existe).
- Dar o quitar el rol de guía o traductor no tiene ruta hasta F5: no hay admin de Django,
  `user-role/` solo acepta roles del equipo y las rutas genéricas de grupos responden 400
  (aviso 10 de la sección 9). Para probar la app como guía hoy: `manage.py shell` y agregar
  a la cuenta al grupo "Guía".
- Los operadores externos (negocio, alcaldía, institución) llegan con F3 (tabla de
  asignación con ámbito y `revocada_en`); hoy existen como roles de sistema sin personas.
- Matriz de pruebas de los endpoints de dominio: se amplía en cada fase (un objeto de otro
  ámbito responde 404).

## 7b. F3 organizaciones y verificación

**Hecho en el API** (commits `feat(organizaciones)...` y `feat(archivos)...`). Decisiones
que tomó el usuario: manda el modelo de dominio (comercio, institución cultural y alcaldía
por separado, una sola cola); alcance de núcleo (sin solicitud asistida ni pedir otro
lugar); archivos en un bucket S3 con URLs firmadas; quien se postula entra con acceso
limitado; **base de datos en español** (`db_table` y `db_column`) y código, rutas y JSON
en inglés.

- Apps nuevas: `api_catalogs` (tipos, motivos, monedas), `api_territory` (diez ciudades,
  alcaldía), `api_organizations` (comercio, horario, platillo, foto, institución),
  `api_moderation` (estados, solicitud y resolución de verificación, cola) y `api_roles`
  (`asignacion_rol` con ámbito y servicios de asignar y revocar). `api_utils.seeding`
  siembra tras cada `migrate`.
- `ApiGroupProfile.scope` (migración `api_auth.0007`): el ámbito que exige cada rol;
  Negocio, Alcaldía e Institución lo traen. La asignación se comprueba en la base.
- La sesión trae `organization` (`{id, kind, name, verified}`) y `organization_id`.
- `GET mine/` y `POST mine/resubmit/` devuelven `MineApplicationGet`: la solicitud más
  `submitted`, los datos con la forma de lo que se manda al corregir (archivos como
  `{key, url}`); lo arma `api_organizations/services/mine.py`. Con eso el portal llena el
  formulario de corrección. `GET catalog/city/` trae `latitude` y `longitude` (el centro
  para encuadrar el mapa).
- Archivos: `api_core.services.storage` (S3, deshabilitado y en memoria para pruebas) y
  `api_core.services.uploads` (tipos y tamaños por clase, y `read_url` para ver un archivo).
  Variables `STORAGE_*`; sin ellas, `POST /upload/` responde 503. Dependencia nueva: boto3.
  Guía: `docs/archivos.md`. **Se sube con un `PUT` firmado** (`{key, url, method, headers}`):
  la primera versión usaba un formulario `POST` (`generate_presigned_post`) y R2 no lo
  admite; con R2 habría fallado solo en producción, y por eso las pruebas no lo veían.
- Pruebas: `test_organizations_models`, `test_moderation_models`, `test_role_assignments`,
  `test_upload`, `test_organization_applications` y `test_verification_queue`.

**Falta de F3** (en este orden):

1. **Portal: hecho.** El alta, el estado y la corrección de quien se postula, y la cola del
   equipo (`/solicitudes`: bandeja, tomar, devolver, aprobar, rechazar con motivo), están en
   el portal contra el API real (ver su memoria). Se retiró el alta asistida y la revisión
   por documento de la demo. Lo que dejó de la demo anterior sigue en `db.organizationApplications`
   solo para los estados de cuenta y la propiedad de los lugares, hasta F4.
2. **Bucket real.** Falta crear el bucket y las variables `STORAGE_*` (guía en
   `docs/archivos.md`, con el CORS del portal: `PUT` y `Content-Type`). Se probó el flujo
   completo en un navegador contra un servidor S3 local (moto), con el mismo código de
   `S3Storage`; falta confirmarlo con R2 de verdad (el `PUT` firmado con `Content-Length`).
3. Lo que quedó fuera a propósito (lista en `docs/organizaciones.md`): lista «Todas» y
   suspender organizaciones, más de un operador, suscripción, platillo por su dueño,
   limpieza de archivos huérfanos y aviso de bienvenida.
4. El 404 sobre objetos de otra organización llega con el primer recurso que un operador
   administre (F4 en adelante).

## 8. F3 a F8 (mapa, se confirma una por una)

El mapa completo, con módulos del modelo de dominio, rutas propuestas, permisos y las
preguntas que hay que contestar antes de cada fase, está en `docs/hoja-de-ruta.md`. En corto:
F3 organizaciones y admisión (+ `upload/`) -> F4 territorio y circuitos -> F5 guías y
traductores -> F6 eventos, cupones e insignias -> F7 contratación, chat y reseñas -> F8
finanzas y notificaciones. El checklist de endpoints del portal es
`portal/src/data/api/endpoints.ts` (unos 90). El API manda el contrato: rutas con la
convención del router actual (recurso en singular, kebab-case); portal y app adaptan sus
repositorios. Versionar con `/v1/` antes de publicar la app. Cada fase nueva protege sus
endpoints con `ensure_permission` o `functional_permissions` y agrega su fila a la matriz
de `test_team.py` (o a una propia).

Cosas que F3 tiene que resolver primero (detalle en `docs/hoja-de-ruta.md`):

- El portal usa una sola `Organization`; el modelo (D-12) tiene `comercio`,
  `institucion_cultural` y `alcaldia` por separado.
- F2 usa Groups + `ApiGroupProfile` y permisos funcionales. M3 pide `rol` con
  `ambito_requerido`, `asignacion_rol` con ámbito (alcaldía, comercio o institución),
  `otorgada_por` y `revocada_en`. Esa asignación con ámbito es lo que permite que
  `organization_id` de la sesión deje de ser `null` y que un objeto ajeno dé 404.
- Estados: D-13 pide una fila de transición por cambio (quién y por qué). Hoy solo hay el
  historial de `pghistory`.

## 9. Avisos para el usuario (no los pierdas; díselos al terminar)

1. `origin/develop-a` y `origin/staging` tienen migraciones 2FA en conflicto
   (`0002_two_factor.py` frente a `0002_2fa.py`): al unir ramas hay que reconciliarlas.
2. Con `DEPLOY=True` ahora hace falta la variable `TOTP_ENCRYPTION_KEYS` (se genera con
   `just fernet-key`). Sin proveedor de correo (`EMAIL_HOST`...) los correos se descartan.
3. La migración `0004_identity` rellena datos: los superusuarios sin correo reciben
   `<usuario>@sin-correo.example` y no podrán entrar hasta que se les ponga uno real.
4. Falta el trabajo programado que destruye la cuenta tras los 30 días de baja (hoy solo
   existen la solicitud, la restauración y el estado `closing`).
5. `ALLOWED_HOSTS`, CORS y CSRF conservan los valores heredados de Railway como respaldo en
   `DEPLOY` mientras no existan las variables; bórralos cuando estén definidas.
6. El identificador de la app (`com.example...`) lo decide el usuario. No hay URL de
   producción todavía: son placeholders.
7. Los secretos reales solo viven en variables de entorno. El `.env` local está ignorado.
8. **Al desplegar F2**: la siembra le pone perfil a los grupos existentes con nombre de
   rol de sistema, y **Administrador exige segundo factor**: quien lo tenga y no lo haya
   activado entra, pero solo podrá activarlo hasta que lo haga. Los roles de ejemplo se
   crean con sus permisos una sola vez. Un grupo creado a mano con `/auth/group/` no tiene
   perfil y no aparece en los roles del equipo.
9. Una cuenta de equipo o de operador ya no puede entrar por la app, y una de turista,
   guía o traductor ya no puede entrar por el portal.
10. Los endpoints genéricos de relaciones de usuario (`PUT/PATCH /auth/user/{id}/groups/` y
    `/permissions/`, sus enlaces `/{related}/` y `POST /auth/user/` con `groups` o
    `permissions`) responden 400 aunque el cuerpo sea correcto: los DTO piden `tuple` en
    modo estricto y el JSON trae listas (y el `related` de la ruta de enlace tampoco valida).
    Venían así; no se tocaron porque el equipo se gestiona con las rutas de `docs/roles.md`.
    Conviene arreglarlos o retirarlos antes de exponerlos a alguien.

11. **Al desplegar F3**: nuevas migraciones (`api_auth.0007` y las de las cinco apps nuevas),
    que siembran las diez ciudades, los catálogos y el ámbito de los roles de operador.
    `STORAGE_*` son opcionales para arrancar (sin ellas, subir archivos responde 503), pero
    hay que crear el bucket y definirlas para que alguien pueda postularse (`docs/archivos.md`).
    Con `DEPLOY=True` el endpoint del bucket tiene que ser `https`.
12. `POST /upload/` es pública (quien se postula sube antes de tener cuenta): la acotan el
    límite de 10 peticiones por minuto, los tipos y tamaños y la vigencia de la URL. Falta
    limpiar los archivos que nadie reclama y revisar su contenido; es un riesgo conocido.
13. La base de datos del dominio está en español y la de `api_auth` sigue en inglés: el
    renombrado de `ApiUser` y compañía (`usuario`...) queda para otra fase y es una migración
    de renombrado, no de datos.

## 10. Cómo trabajar en esta máquina (Windows, PowerShell)

El Postgres 18 portátil y el módulo de ajustes locales están **fuera del repo**, en
`%LOCALAPPDATA%\Temp\kplan-dev`. Si la carpeta desapareció, se recrea: Postgres 18 (hace
falta `uuidv7()`) de `postgresql-18.6-1-windows-x64-binaries.zip` de EnterpriseDB, o `just up`
con Docker.

- Base de datos: `127.0.0.1:55432`, base y usuario `kplanapi` (el `.env` local, ignorado,
  ya apunta ahí). Arrancarla si no corre, **sin `-w`** (con `-w` se cuelga la shell):
  `pg_ctl.exe start -D "$env:LOCALAPPDATA\Temp\kplan-dev\pgdata" -o "-p 55432 -c listen_addresses=127.0.0.1" -l "$env:LOCALAPPDATA\Temp\kplan-dev\pg.log"`.
- Entorno de pruebas (sin Redis: cache en memoria):

```powershell
Set-Location C:\development\kplan\api
$env:PYTHONUTF8 = '1'
$env:PYTHONPATH = "$env:LOCALAPPDATA\Temp\kplan-dev\localsettings;$PWD\src"
$env:DJANGO_SETTINGS_MODULE = 'kplan_local_settings'
$env:DEBUG = 'False'; $env:CI = 'true'
uv run --frozen pytest --create-db --no-cov -q -p no:warnings
uv run --frozen ruff format src; uv run --frozen ruff check src
uv run --frozen ty check
uv run --frozen python src/manage.py makemigrations --check --dry-run
```

- Servidor local: mismo entorno sin `DEBUG`/`CI`, y
  `uv run --frozen granian --interface asgi --host 127.0.0.1 --port 8080 api_core.asgi:application`.
  Tras cambiar código hay que reiniciarlo (no recarga). Para matarlo en Windows hay que
  parar también el proceso hijo `python.exe` de `multiprocessing`, si no el puerto queda
  ocupado. `manage.py migrate` aplica las migraciones y siembra los roles.
- Pruebas en el navegador (todo en `%LOCALAPPDATA%\Temp\kplan-dev`, fuera del repo):
  `e2e\run-e2e-f3.ps1` (F3: alta, rechazo, corrección, aprobación, 41 comprobaciones),
  `e2e\run-e2e-f3-queue.ps1` (la cola del equipo), `e2e\e2e-f3-demo.mjs` (modo demo),
  `e2e\e2e-f2-team.mjs` (equipo y roles; `E2E_EMAIL`, `E2E_PASSWORD`, y `E2E_PORTAL`,
  `E2E_ROLE_A`, `E2E_ROLE_B` para la demo), `run-e2e-f2.ps1` (F2) y `run-e2e.ps1` (F1). Se corren
  con Edge (`playwright-core`). Para F3 hace falta un servidor S3 local: `moto-env\Scripts\
  moto_server.exe -p 9444` (el 9100 lo usa el servicio de impresión), `e2e\make-bucket.py`
  (bucket `kplan-dev` con CORS) y el API con `e2e\start-api.ps1`, que le pone las `STORAGE_*`
  y deja el "correo" en `api.out.log` (de ahí el script lee el código). El portal, con
  `npm run dev` en `5173`; el modo demo, `npx vite --mode demo --port 5174`.
- Secretos en commits: `gitleaks` portátil en `%LOCALAPPDATA%\Temp\kplan-dev\gitleaks`;
  antes de commitear, `gitleaks git --staged --redact`. El hook de `prek` también lo corre.
- Herramientas: `uv` (siempre `--frozen`), ruff (`select = ALL`, preview), ty, pytest-django,
  schemathesis. El editor `Grep` solo busca en el workspace de la API: para portal y app usa
  `rg` desde la shell.

## 11. Trampas ya resueltas (no las redescubras)

- Los DTO son estrictos (`strict=True`, `extra=forbid`): no convierten `str` a `Enum` ni a
  `date`. Usa `Literal[...]` y `Field(strict=False)`. En herencia múltiple gana la última
  base al mezclar `model_config`. Una lista JSON **no** valida contra `tuple[...]`: los
  DTO de entrada usan `list[...]`.
- `EmailStr` rechaza `.test`, `.invalid`, `.local` y `localhost`: en datos y pruebas usa
  `example.com`.
- `pgtrigger.ignore` + `IntegrityError` dentro de un `atomic` deja la transacción rota:
  `_create_user` usa un savepoint.
- `pytest-django` envuelve cada prueba en una transacción: los reintentos de `pgtransaction`
  se desactivan en las pruebas. `TRUNCATE` está bloqueado por `trg_protect_truncate`, así que
  no sirven las pruebas con `transaction=True`.
- Schemathesis llama a la app WSGI cruda: hay que desconectar las señales
  `close_old_connections` y pedir el token antes de desconectarlas.
- `post_migrate` siembra roles y permisos también en la base de pruebas: los nombres de
  grupo sembrados (Administrador, Verificador, Aprobador...) ya existen en cada prueba, así
  que las pruebas usan otros nombres. `ApiVerificationCode` es de solo lectura (trigger):
  para saltar la espera entre correos se acorta `CONFIG.VERIFICATION_RESEND_AFTER`
  (`CONFIG.model_copy(update=...)` con `monkeypatch`).
- Un `.exclude(group=...)` sobre una relación múltiple saca la fila si **alguno** de sus
  grupos coincide: para "los permisos de mis otros roles" se filtra con `group__in`.
- Dos controladores sobre la misma ruta base necesitan `endpoint_cls =
  ModelOperationIdEndpoint` (list/retrieve/update...) o el `operationId` se duplica.
- **R2 (y por tanto el bucket de producción) no admite el formulario `POST` firmado**: solo
  `GET`, `HEAD`, `PUT` y `DELETE`. Las subidas son un `PUT` con `Content-Type` y `Content-Length`
  dentro de la firma. Lo que funciona con S3 o MinIO puede fallar con R2: confirma cada operación
  del almacenamiento contra la tabla de compatibilidad de R2 antes de usarla.
- Pruebas en navegador con Playwright: `page.mouse.click(x, y)` no se desplaza a la vista, y un
  clic fuera del viewport no hace nada. Antes de calcular la posición de un mapa o de un
  elemento largo, `scrollIntoViewIfNeeded()`.
- `pgtrigger`: `UpdateOf` lleva el nombre real de la **columna** (en español: no resuelve
  `db_column`); las condiciones `Q` sí usan campos. `ReadOnly` no admite `condition`. El
  cuerpo de la función del disparador tiene que terminar en `RETURN` (`NEW` o `NULL`) y no
  puede llevar llaves `{}`.
- Django exige `on_delete` de la misma clase en toda la cadena de un modelo (E323 y E050):
  los modelos del dominio usan las variantes de Python (`CASCADE`, `RESTRICT`, `SET_NULL`).
- Un error de ApiError que no sea una clase propia sale como 500 aunque lleve `http_status`:
  el manejador usa `default_http_status` de la clase (por eso `ServiceUnavailableError`). Un
  503 global chocaría con el del chequeo de salud: se declara con `extra_responses`.
- Una restricción de unicidad violada sale con el nombre de la columna **en español** en
  `field_errors`: los servicios comprueban antes y responden con el nombre en inglés.
- Los mensajes de commit van en un archivo creado con la herramienta de escritura (sin BOM);
  `Out-File -Encoding utf8` agrega un BOM que termina en el asunto del commit.
- PowerShell: no pases archivos por `Get-Content`/`Set-Content` (rompe UTF-8 y agrega BOM);
  edita con las herramientas del editor. El árbol de trabajo está en CRLF (`autocrlf`).
- `ruff` es muy estricto (`ALL`): comentarios en lugar de docstrings en muchas piezas,
  líneas cortas, y `# ty: ignore[...]` donde los tipos de Django no resuelven (un ignore
  que sobra también es un aviso: quítalo).
