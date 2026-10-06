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

- **Nada está empujado a ningún remoto.** No empujes sin que el usuario lo pida: un push a
  `develop-a` puede disparar un despliegue sin las variables nuevas (ver sección 9).
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
| f2-roles-permissions    | **API hecha** (sección 7). Falta el lado del portal                                 |
| f3-f8-roadmap           | Pendiente (documentación; el dominio se confirma fase por fase)                     |

Siguiente paso recomendado: lo que falta de F2 en el portal (sección 7), y después pedirle
al usuario que elija la fase de dominio (F3 en adelante).

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
- **Modelos nuevos**: `ApiLoginAttempt`, `ApiLoginLock`, `ApiVerificationCode` y
  `ApiExternalIdentity` (`models/security.py`), y `ApiGroupProfile` (`models/role.py`).
  Migraciones `0004_identity` (con relleno de datos), `0005_external_identity` y
  `0006_group_profile`.
- **Pruebas**: 390 casos (≈3 min con la cobertura). Cubren config, TOTP, cifrado, login, 2FA,
  registro, contraseña, perfil, baja, bloqueo, modelos, Google, roles, equipo y
  `schemathesis` contra `/openapi/`.
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
  `GET|PUT|DELETE /auth/staff-role/{id}/`, `POST /auth/staff-invite/`,
  `POST /auth/staff-accept/` (pública), `POST /auth/user-role/`, `POST /auth/user-status/`,
  `POST /auth/user-password-reset/`. Detalle y permisos en `docs/roles.md`.
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

**Falta de F2**:

- **Portal** (no empezado): agregar los IDs `*.view` a `src/data/models/access.ts`
  (`PERMISSIONS`, `PERMISSION_GROUPS`) y usarlos en `navigation.ts`/`routes.tsx`; mostrar
  `two_factor.required` (llevar a Seguridad); página de aceptar invitación (por ejemplo
  `/invitacion`: correo + código + contraseña -> `POST /auth/staff-accept/`); y, si se
  quiere, conectar las páginas de equipo, usuarios y roles con los endpoints nuevos
  (hoy siguen siendo demo). Respetar `sent: false` al reinvitar.
- **App**: nada obligatorio. El inicio de sesión móvil ya solo admite roles públicos.
- Los operadores externos (negocio, alcaldía, institución) llegan con F3 (tabla de
  asignación con ámbito y `revocada_en`); hoy existen como roles de sistema sin personas.
- Matriz de pruebas de los endpoints de dominio: se amplía en cada fase (un objeto de otro
  ámbito responde 404).

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
- PowerShell: no pases archivos por `Get-Content`/`Set-Content` (rompe UTF-8 y agrega BOM);
  edita con las herramientas del editor. El árbol de trabajo está en CRLF (`autocrlf`).
- `ruff` es muy estricto (`ALL`): comentarios en lugar de docstrings en muchas piezas,
  líneas cortas, y `# ty: ignore[...]` donde los tipos de Django no resuelven (un ignore
  que sobra también es un aviso: quítalo).
