# Memoria de trabajo: hoja de ruta del API de K'Plan

Actualizada el 2026-10-05. Es el traspaso para el siguiente agente: qué está hecho, qué
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
| API    | `C:\development\kplan\api`    | `develop-a` y `feat/hoja-de-ruta-api` (mismo punto) | este archivo |
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
| f1-google-login         | Hecha en el API y con guía (`docs/google.md`). Faltan los botones en portal y app   |
| f1-portal-link          | **En curso: solo exploración y diseño, sin código.** Ver `portal/.cursor/memory`    |
| f1-app-link             | Pendiente. Solo está la base de F0 (cliente HTTP por entorno, logs redactados)      |
| f2-roles-permissions    | Pendiente                                                                           |
| f3-f8-roadmap           | Pendiente (documentación; el dominio se confirma fase por fase)                     |

Siguiente paso recomendado: terminar **f1-portal-link** (sección 5), luego **f1-app-link**
(sección 6) y **f2** (sección 7).

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
- **Modelos nuevos**: `ApiLoginAttempt`, `ApiLoginLock`, `ApiVerificationCode` y
  `ApiExternalIdentity` (`models/security.py`). Migraciones `0004_identity` (con
  relleno de datos) y `0005_external_identity`.
- **Pruebas**: 246 (≈85 s). Cubren config, TOTP, cifrado, login, 2FA, registro,
  contraseña, perfil, baja, bloqueo, modelos, Google y `schemathesis` contra `/openapi/`.
- **Docs**: `docs/autenticacion.md` (contrato de identidad para portal y app),
  `docs/google.md`, `docs/guia.md` y `README.md` (secretos y ejecución local).

Contrato completo y vigente: `docs/autenticacion.md` y el OpenAPI en `/openapi/`.

### Cosas provisionales que F2 debe reemplazar

- `services/session_user.py`: el rol sale del nombre del grupo (`ROLE_BY_GROUP`:
  `Administrador`/`Personal` -> `admin`, `Cliente` -> `turista`; superusuario -> `admin`).
  `organization_id` es siempre `null` (llega con F3). `two_factor.required` es siempre
  `false`. `permissions` son los códigos de permiso de Django (p. ej. `apiauth.view_apiuser`),
  no los IDs funcionales del portal.
- Los grupos sembrados siguen siendo `Administrador`, `Cliente` y `Personal`.

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
- Errores: `{ "detail": "...", "field_errors": { "body.campo": "..." } }`. El 429 trae
  `Retry-After`.
- Local: API en `http://localhost:8080`, portal en `http://localhost:5173` (usar `localhost`
  en los dos: mezclarlo con `127.0.0.1` vuelve las cookies cross-site). Emulador Android:
  `http://10.0.2.2:8080`.

## 5. Falta: portal (f1-portal-link)

Es el siguiente trabajo. El diseño detallado y ya decidido está en
`C:\development\kplan\portal\.cursor\memory\hoja-de-ruta.md`. Resumen: cliente HTTP con
cookies, CSRF y refresco único; login con paso 2FA; página de Seguridad; recuperar
contraseña con código; demo explícita; mapeo del usuario del API al modelo del portal.

## 6. Falta: app (f1-app-link)

Detalle en `C:\development\mobile-1\.cursor\memory\hoja-de-ruta.md`. Resumen: `ApiClient`
con refresco y `flutter_secure_storage`; login, registro (con nacionalidad, fecha de
nacimiento y código por correo) y recuperar contra el API; pantallas 2FA; botón Google;
**fijar `applicationId` y bundle id con el usuario antes de crear los Client ID**; firma
release.

## 7. Falta: F2 roles y permisos

- Catálogo de permisos con los IDs del portal (`portal/src/data/models/access.ts`:
  `agenda.view`, `organizations.review`, `organizations.manage`, `guides.review`,
  `guides.decide`, `places.manage`, `circuits.manage`, `content.moderate`, `users.manage`,
  `staff.manage`, `billing.manage`) más los de solo lectura: `guides.view`,
  `organizations.view`, `users.view`, `billing.view`, `places.view`, `circuits.view`.
- Roles del equipo = Grupos de Django con perfil (`kind`, `requires_2fa`, `is_system`).
  Roles de ejemplo: Observador de guías y traductores (`guides.view`); Verificador
  (`guides.view` + `guides.review`); Aprobador (además `guides.decide`); Observador de
  negocios (`organizations.view`); Gestor de organizaciones (además `review` y `manage`);
  Moderador de contenido (`content.moderate`); Super admin (rol de sistema, no editable).
- El permiso se otorga solo vía rol: bloquear `/auth/user/<id>/permissions/` salvo
  superusuario.
- Cada superficie admite solo sus roles: login `mobile` para turista, guía y traductor; login
  `web` para equipo y operadores. Un rol ajeno recibe el mismo error que credenciales
  inválidas (RF-S-08).
- 2FA obligatorio para roles del equipo (`requires_2fa`), con enrolamiento forzado la primera
  vez. Suspender a alguien revoca todas sus sesiones al instante (ya existe el mecanismo
  `sessions_revoked_at`).
- Permisos por método en cada controlador. El mecanismo ya existe en
  `src/api_auth/services/permissions.py` (`ensure_model_permissions`).
- Invitar al equipo (`POST` de staff con correo) y cambiar el estado de usuarios.
- Matriz de pruebas rol x endpoint (200 / 403 / 404). Un objeto de otro ámbito responde 404.
- Los operadores externos (negocio, alcaldía, institución) llegan con F3 (tabla de asignación
  con ámbito y `revocada_en`).

## 8. F3 a F8 (mapa, se confirma una por una)

F3 organizaciones y admisión (+ `uploads`) -> F4 territorio y circuitos -> F5 guías y
traductores -> F6 eventos, cupones e insignias -> F7 contratación, chat y reseñas -> F8
finanzas y notificaciones. El mejor checklist de endpoints es
`portal/src/data/api/endpoints.ts` (unos 90). El API manda el contrato: rutas con la
convención del router actual (recurso en singular, kebab-case); portal y app adaptan sus
repositorios. Versionar con `/v1/` antes de publicar la app.

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
uv run --frozen pytest --create-db --no-cov -q
uv run --frozen ruff format src; uv run --frozen ruff check src
uv run --frozen ty check
uv run --frozen python src/manage.py makemigrations --check --dry-run
```

- Secretos en commits: `gitleaks` portátil en `%LOCALAPPDATA%\Temp\kplan-dev\gitleaks`;
  antes de commitear, `gitleaks git --staged --redact`. El hook de `prek` también lo corre.
- Herramientas: `uv` (siempre `--frozen`), ruff (`select = ALL`, preview), ty, pytest-django,
  schemathesis. El editor `Grep` solo busca en el workspace de la API: para portal y app usa
  `rg` desde la shell.

## 11. Trampas ya resueltas (no las redescubras)

- Los DTO son estrictos (`strict=True`, `extra=forbid`): no convierten `str` a `Enum` ni a
  `date`. Usa `Literal[...]` y `Field(strict=False)`. En herencia múltiple gana la última
  base al mezclar `model_config`.
- `EmailStr` rechaza `.test`, `.invalid`, `.local` y `localhost`: en datos y pruebas usa
  `example.com`.
- `pgtrigger.ignore` + `IntegrityError` dentro de un `atomic` deja la transacción rota:
  `_create_user` usa un savepoint.
- `pytest-django` envuelve cada prueba en una transacción: los reintentos de `pgtransaction`
  se desactivan en las pruebas. `TRUNCATE` está bloqueado por `trg_protect_truncate`, así que
  no sirven las pruebas con `transaction=True`.
- Schemathesis llama a la app WSGI cruda: hay que desconectar las señales
  `close_old_connections` y pedir el token antes de desconectarlas.
- PowerShell: no pases archivos por `Get-Content`/`Set-Content` (rompe UTF-8 y agrega BOM);
  edita con las herramientas del editor. El árbol de trabajo está en CRLF (`autocrlf`).
- `ruff` es muy estricto (`ALL`): comentarios en lugar de docstrings en muchas piezas,
  líneas cortas, y `# ty: ignore[...]` donde los tipos de Django no resuelven.
