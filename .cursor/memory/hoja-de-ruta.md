# Memoria de trabajo: hoja de ruta del API de K'Plan

Actualizada el 2026-10-08 (mañana, en la PC 2). Es el traspaso para el siguiente agente: qué está hecho, qué
falta y cómo trabajar en esta máquina. Léela completa antes de tocar código. Si algo de
aquí ya no es cierto, corrígelo en el mismo commit en que lo cambies.

## 1. De dónde viene esto

- Plan aprobado por el usuario: "Hoja de ruta API K'Plan (portal + app móvil)". El archivo
  está fuera del repo (`C:\Users\PDesarrollo\.cursor\plans\hoja_de_ruta_api_k'plan_4fa012a7.plan.md`):
  se puede leer, **no editarlo**.
- Alcance aprobado: **F0, F1 y F2**. Las fases F3 a F8 son un mapa; cada una se confirma con
  el usuario antes de empezar.
- Hay tres repos. Cada uno tiene `.cursor/memory/hoja-de-ruta.md` con su parte:

| Repo   | Ruta (PC 1, `PDesarrollo`)    | Ruta (PC 2, `Lenovo`)     | Rama de trabajo          |
| ------ | ----------------------------- | ------------------------- | ------------------------ |
| API    | `C:\development\kplan\api`    | `C:\coding\kplan2\api`    | `develop-a`              |
| Portal | `C:\development\kplan\portal` | `C:\coding\kplan2\portal` | `feat/hoja-de-ruta-api` (sale de `main`) |
| App    | `C:\development\mobile-1`     | `C:\coding\kplan2\mobile` | `feat/hoja-de-ruta-api` (sale de `main`) |

El usuario trabaja en las dos máquinas: **antes de empezar, `git fetch` en los tres repos**
y cámbiate a la rama de trabajo (la sección 10 dice cómo correr todo en cada una). Cada repo
tiene su memoria en `.cursor/memory/hoja-de-ruta.md`.

- **Remotos (2026-10-07, 11:15).** Todo está empujado a pedido del usuario: el API en
  `origin/develop-a` (F0 a F3 y F5, con el `PUT` firmado que pide R2), y portal y app en
  `origin/feat/hoja-de-ruta-api` (en la app va también el mapa con MapLibre y las
  animaciones Lottie, que entraron en el mismo envío). No empujes sin que el usuario lo
  pida: un push a `develop-a` corre el CI de GitHub (build, lint, test, validate, prek,
  secrets) y puede disparar un despliegue sin las variables nuevas (ver sección 9);
  `TOTP_ENCRYPTION_KEYS` es obligatoria con `DEPLOY=True`.
- Nunca commitear en `production` ni en `staging`. Portal y app no tienen rama de
  desarrollo: no tocar su `main`.
- **Ramas y dominios (2026-10-08, decisión del usuario).** API: `production` ->
  `https://api.kplan.dev`, `staging` -> `https://staging-api.kplan.dev` (no se le sube lo
  nuevo: tiene sus propios commits), `develop-a` -> `https://develop-api.kplan.dev` (aquí
  vive todo lo de F1 a F8). Portal: `main` es producción (`https://portal.kplan.dev`) y
  `staging` (sale de `feat/hoja-de-ruta-api`) va a `https://staging-portal.kplan.dev` contra
  `develop-api`. App: `main` es producción (`env/prod.example.json` -> `api.kplan.dev`) y
  `staging` usa `env/staging.example.json` -> `develop-api.kplan.dev`. El portal toma
  `VITE_API_URL` de las variables del build en Cloudflare; el API, sus dominios de
  `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` en Railway. Lo nuevo se
  sube a `staging` del portal y de la app adelantando la rama a `feat/hoja-de-ruta-api`.
- Commits convencionales en español (`feat(auth): ...`, `docs: ...`). Sin emojis.

## 2. Estado de las tareas

| Tarea                   | Estado                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------- |
| f0-secrets-gitignore    | Hecha (3 repos)                                                                     |
| f0-env-config           | Hecha (3 repos)                                                                     |
| f0-totp-migration-tests | Hecha (API)                                                                         |
| f1-api-identity         | Hecha (API)                                                                         |
| f1-google-login         | Hecha en el API, la app y el portal, con guía (`docs/google.md`) |
| f1-portal-link          | Hecha (portal, rama `feat/hoja-de-ruta-api`). Ver `portal/.cursor/memory`           |
| f1-app-link             | Hecha (app, rama `feat/hoja-de-ruta-api`). Ver `mobile-1/.cursor/memory`            |
| f2-roles-permissions    | **Hecha** en el API, el portal (permisos, invitación, equipo y roles) y la app (modo guía según el rol). "Todos los usuarios" del portal sigue en demo (sección 7) |
| f3-f8-roadmap           | Hecha (documentación: `docs/hoja-de-ruta.md`); cada fase de dominio se confirma antes |
| F3 (organizaciones)     | **Hecha** en el API y en el portal (alta, estado, corregir y la cola del equipo). Falta crear el bucket real (sección 7b) |
| F5 (guías y traductores)| **Hecha** en el API, el portal (la cola en dos pasos) y la app (postularse, estado, corregir, renovar, perfil). Sección 7c |
| Directorio de cuentas   | **Hecho en el API** (`GET|PATCH /auth/account/`, `docs/roles.md`). El portal lo conecta (sección 7d) |
| F4 (lugares y circuitos)| **Hecha en el API**: lugares, ficha, novedades, circuitos oficiales, itinerarios del turista (sección 7d). Portal y app: ver sección 7d |
| F6 (agenda, insignias, cupones) | **Hecha en el API** (sección 7e), conectada en el portal y la app (2026-10-08) |
| F7 (guías, reservas, chat, reseñas) | **Hecha en el API** (sección 7f), conectada en el portal y la app (2026-10-08) |
| F8 (cobros, retiros, avisos, sanciones) | **Hecha en el API** (sección 7g), conectada en el portal y la app (2026-10-08); el push espera el proyecto de Firebase |

Orden que eligió el usuario (2026-10-07): directorio + F4, luego F6, F7 y F8, en ese orden;
cada fase se le confirma con sus preguntas antes de empezar. Pendiente chico: crear el
bucket real (sección 7b).

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
- **Google (F1)**: `POST /auth/mobile/google/` crea o enlaza turistas, guías y traductores;
  `POST /auth/web/google/` solo enlaza cuentas existentes y verificadas de organizaciones o
  equipo. Identidad externa en `ApiExternalIdentity`; `GOOGLE_OAUTH_CLIENT_IDS`. Guía:
  `docs/google.md`.
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
`C:\development\mobile-1\.cursor\memory\hoja-de-ruta.md`. El identificador Android y el
bundle ID son `dev.kplan.app`; el Client ID Web y el de Android de desarrollo ya existen.
Faltan la configuración de Google para iOS y el inicio de sesión con Apple.

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
`turista` no. Desde F5 manda además `provider` de la sesión y la postulación va contra el
API (sección 7c).

**Falta de F2**:

- **Todos los usuarios** (portal): sigue en demo. Hace falta un directorio de cuentas con el
  rol derivado (`role_of`), filtros por rol y estado y búsqueda, para que el portal deje
  `/api/users`. Con eso pasa también "Mandar código para nueva contraseña"
  (`POST /auth/user-password-reset/`, que ya existe).
- El rol de guía o traductor lo da aprobar la solicitud (F5, sección 7c). Quitarlo no tiene
  ruta: `user-role/` solo acepta roles del equipo y las rutas genéricas de grupos responden
  400 (aviso 10 de la sección 9).
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

## 7c. F5 guías y traductores

**Hecho en el API, el portal y la app.** Decisiones del usuario (2026-10-07): una cuenta, un papel (el
prestador crea su propia cuenta desde la app y, mientras lo revisan, solo ve su estado);
documentos: cédula y récord de policía a todos, licencia del INTUR a los guías,
certificado de idiomas a los traductores, licencia de conducir y seguro a quien lleva
turistas; revisión en **dos pasos** (`guides.review` acepta o rechaza cada documento y pide
correcciones; `guides.decide` aprueba o rechaza); vencimiento con comando diario,
renovación sin dejar de trabajar y perfil público editable. Contrato: `docs/prestadores.md`.

- App nueva `api_profiles` (M4): `estado_prestador`, `perfil_prestador` (`ciudad_id` nulo es
  todo el país, `lleva_turistas`, `foto_clave`, disparador de un solo papel por cuenta),
  `prestador_servicio`, `prestador_idioma`, `estado_acreditacion` (con `reemplazada`) y
  `acreditacion` (con el veredicto de quien revisó y el expediente donde se subió; un
  disparador exige el vencimiento en los tipos que vencen y otro, uno en vigor por tipo).
  `api_catalogs` suma `idioma`, `tipo_servicio` y `tipo_acreditacion` (seis tipos) y los
  motivos `rechazo_documento`, `rechazo_prestador` y `documentos_por_corregir`.
  `solicitud_verificacion` suma `perfil_prestador_id` y `tramite` (`alta`/`renovacion`);
  la cola de organizaciones los excluye (`organization_requests`).
- Rutas: `catalog/language|service-type|credential-type/` (públicas),
  `POST provider-application/` (pública, móvil: devuelve tokens), `GET .../mine/`,
  `POST .../mine/resubmit/`, `POST .../mine/renewal/`, `GET|PATCH provider-profile/mine/`, y
  la cola `provider-request/` (lista, `reason/`, detalle, `take`, `release`,
  `document-review`, `request-changes`, `approve`, `reject`). `upload/` suma
  `provider-document` y `provider-photo`.
- El veredicto y el estado son dos cosas: quien revisa deja `veredicto`; el estado cambia al
  resolver (aprobar pone `aprobada` y deja `reemplazada` la anterior). Un documento
  aceptado en un expediente rechazado pasa tal cual al siguiente y no se vuelve a revisar.
  Una renovación se resuelve sola cuando su último documento queda revisado.
- Aprobar da los grupos Guía y/o Traductor con `grant_role_sync` (sin ámbito). La sesión
  trae `provider` (`{id, status, services}`). Una cuenta con perfil y sin grupos solo entra
  por la app (`surface_allows_sync`).
- `python src/manage.py expirecredentials`: vence y suspende (con correo). **Hay que
  programarlo una vez al día al desplegar** (cron de Railway).
- Pruebas: `test_provider_applications.py` (27) y `test_provider_queue.py` (71, con la
  matriz de permisos). Ayudas en `api_tests/provider_helpers.py`. Suite completa: 722.

**Portal: hecho** (`e7cd18e`, ver su memoria). "Guías y traductores" va contra
`provider-request/`: la cola, el detalle con el visor de documentos, aceptar o rechazar cada
uno, pedir correcciones y la decisión final; la demo habla el mismo formato. Probado en el
navegador contra el API real (`e2e\e2e-f5-queue.mjs`, 23 comprobaciones) y en demo
(`e2e\e2e-f5-demo.mjs`).

**App: hecho** (`4dc73f4`, ver su memoria). Postularse como guía, traductor o ambos con la
subida firmada, el estado con el veredicto por documento, corregir solo lo rechazado,
renovar un documento y editar el perfil público. La cuenta de prestador no es turista: ya
no hay "Entrar como turista" y cualquier login de una cuenta aprobada lleva a la app del
guía. `test/integration/provider_contract_test.dart` pasó contra el API local con el S3 de
prueba (sección 10).

**Falta de F5**: el turista todavía no ve a los guías aprobados (el perfil público y la
contratación siguen simulados en la app; llegan con F7). En la app el nivel de idioma se
simplificó: español nativo, los demás avanzado (el API acepta los cuatro niveles). Aviso
para el usuario al desplegar: migraciones nuevas (`apicatalogs.0002`, `apimoderation.0002` y
`0003`, `apiprofiles.0001`) y el cron.

## 7d. Directorio de cuentas y F4 lugares, circuitos e itinerarios

**Hecho en el API** (2026-10-07, commits `feat(cuentas)...` y `feat(territorio)...`).
Decisiones del usuario: el equipo con `circuits.manage` crea circuitos en cualquier ciudad y
cada alcaldía verificada los de su ciudad; el circuito guarda la base del modelo más todos
los campos que usan portal y app; la ficha de un lugar la edita su dueño y sale de
inmediato; los circuitos propios del turista entran ya, como itinerarios. Contrato:
`docs/territorio.md` y la sección "Directorio de cuentas" de `docs/roles.md`.

- Directorio: `api_auth/{schemas,services,controllers}/directory.py`. El papel se deriva en
  SQL (`Case` + `Exists` por rol, mismo orden que `ROLE_PRIORITY`) para poder filtrar.
  `api_core/services/pages.py` (`paginate`, con la clase del esquema explícita: con el tipo
  genérico pydantic falla en tiempo de ejecución).
- `api_catalogs`: `pilar_cultural` (5 filas: historia, cultura, gastronomia, naturaleza,
  aventura) y `PILLAR_BY_BUSINESS_TYPE`. Ruta `catalog/pillar/`.
- `api_territory`: `punto_interes` (dueño opcional: comercio, institución o alcaldía; un
  comercio, un solo lugar), `ficha_lugar`, `oferta_lugar`, `publicacion`, `estado_circuito`,
  `circuito_oficial` (ciudad, alcaldía opcional solo en `creative`, tipo, precios, horarios,
  temporada, `version`) y `circuito_parada`. `foto` (en `api_organizations`) suma
  `punto_interes_id` y `circuito_id` con exactamente un dueño. Servicios en
  `api_territory/services/` (`access.Actor`: permisos + organización **verificada**).
- `api_itineraries` (M6): `estado_itinerario`, `itinerario` (cuelga de la cuenta, no de
  `perfil_turista`), `itinerario_parada` (copias) e `itinerario_circuito`. Disparadores:
  `ajustado` no se revierte y uno que sigue un circuito no tiene paradas propias.
- Aprobar un comercio (`api_moderation.services.resolve_sync`) le crea su lugar
  (`ensure_business_place_sync`) con su foto de platillo.
- `upload/` suma `place-photo` y `circuit-photo`. Una imagen cuya clave empieza con
  `https://` (contenido de ejemplo) se devuelve tal cual.
- `python src/manage.py seedcontent`: 26 lugares y 5 circuitos de la app (fixtures en
  `api_territory/fixtures/`), activa sus ciudades y crea alcaldías verificadas de ejemplo
  (León, Masaya, Estelí). Con `DEPLOY=True` pide `--force`: **no correrlo en producción**
  (ocuparía la alcaldía de esas ciudades). Rivas/Ometepe se salta (no es Ciudad Creativa).
- Pruebas: `test_directory.py` (16), `test_places.py` (30), `test_circuits.py` (20),
  `test_itineraries.py` (13); ayudas en `api_tests/territory_helpers.py`. Suite: 832.
  **La suite completa tarda ~17 min** (antes ~4): schemathesis genera los cuerpos grandes
  de `official-circuit/`. Para iterar, corre solo los archivos que tocas.

**Falta de F4**: horarios de grupo de un circuito (F7), reseñas (F7; `rating` y
`reviews_count` son un resumen fijo), métricas del circuito para la alcaldía (RF-A-10,
cuando exista iniciar un recorrido), pedir otro lugar (`place-request/`) y la lista de
organizaciones del portal (`organization/`).

**Portal**: lo conecta un agente (usuarios, lugares, ficha, novedades, circuitos; la
alcaldía entra a Circuitos). **App**: circuitos, lugares e itinerarios contra el API. El
estado real de cada uno está en su memoria.

## 7e. F6 agenda, insignias y cupones

**Hecho en el API** (2026-10-07). Decisiones del usuario: publican eventos instituciones y
alcaldías verificadas (y el equipo los especiales de K'Plan); moderación después
(`content.moderate` oculta eventos y retira campañas); la insignia se gana con QR **y**
menos de 50 m, una por lugar cada 24 h; la activación pagada de la insignia la hace el
equipo (`has_badge`) hasta F8; hasta tres campañas activas por comercio. Contrato:
`docs/agenda-y-recompensas.md`.

- `api_catalogs`: `categoria_evento` y `tipo_beneficio` (`seed_content_catalogs`). Rutas
  `catalog/event-category/` y `catalog/benefit-type/`.
- `api_agenda`: `estado_evento` y `evento` (institución o alcaldía o ninguna; `featured`,
  `hidden_at`, `clonado_de`). La vigencia sale del calendario en `sync_states()` (antes de
  cada lectura y con `manage.py syncevents`, que **hay que programar a diario**).
- `api_rewards`: `insignia` (una por lugar, `codigo_qr`; la crea o apaga `sync_badge` al
  cambiar `has_badge`), `visita_acreditada` (disparador de 24 h), `movimiento_insignia`
  (disparador de saldo no negativo), `estado_campania`, `campania_cupon`, `estado_cupon` y
  `cupon` (beneficio copiado y congelado). Canje y validación con filas bloqueadas
  (`select_for_update`). Visitas y canjes solo para el papel `turista`.
- `foto` suma `evento_id`. `upload/` suma `event-photo` y `coupon-photo`.
- Las migraciones iniciales de `apicatalogs` y `apiterritory` ahora dependen de
  `apicore.0002` (usaban `gin_trgm_ops` sin declararlo; con las apps nuevas el orden de
  creación de la base de pruebas cambió y fallaba).
- Pruebas: `test_agenda.py` (20) y `test_rewards.py` (25).

**Falta de F6**: lo pagado (tarifa por cupón validado, activación mensual de la insignia,
campañas de insignias extra con multiplicador) va con F8; avisos de cancelación y por
cercanía, con F8; medallas por ciudad y nivel de exploración; la agenda de llegadas
(`visit-events`), con F7. **Portal y app**: conectarlos a estas rutas (agenda de la
institución y la alcaldía, moderación, QR del lugar, campañas y validación en el portal;
agenda, escanear QR, saldo, tienda y billetera en la app).

## 7f. F7 guías, reservas, chat y reseñas

**Hecho en el API** (2026-10-07). Decisiones del usuario: en un circuito oficial (creativo,
especial o cualquiera que el turista no creó ni modificó) el guía publica sus salidas y el
turista reserva; en un itinerario propio el turista publica una convocatoria y elige entre
las postulaciones; sin cobro en línea hasta F8 (monto congelado, `estado_pago=sin_cobro`);
el turista cancela gratis hasta 24 h antes; chat por consultas periódicas; reseñas al
instante con impugnación; entran los horarios de grupo. Contrato: `docs/servicios.md`.

- `api_services`: `salida_guiada` (exclusiva en circuitos privados; un guía no sale dos
  veces a la misma hora), `estado_convocatoria`, `convocatoria`, `postulacion`,
  `estado_reserva` (sin `pendiente_pago` ni `expirada` hasta F8) y `reserva` (nace de una
  salida o de una postulación; monto de solo lectura). Servicios en `services/` (`guides`,
  `departures`, `requests`, `bookings`). Guía = prestador activo con el servicio `guia`.
- `api_messaging`: `conversacion` (una por reserva, nace con ella), participantes con
  `leido_hasta` y `mensaje` inmutable.
- `api_reputation`: `resena` (una por autor y reserva; inmutable salvo `oculta_en`) e
  `impugnacion`; las del turista recalculan `promedio_valoracion` y `total_resenas` del
  `perfil_prestador` y `calificacion`/`resenas` del circuito.
- Perfil público de los guías (`guide/`): lo que faltaba de F5 para que el turista los vea.
- Pruebas: `test_services.py` (20).

**Falta de F7**: WebSocket; avance del viaje parada por parada y agenda de llegadas
(`visit-events`); lectura de reservas por el equipo. **Portal y app**: conectarlos (en la
app: guías, salidas, reservar, convocatorias, chat, reseñas y la app del guía; en el
portal: la cola de impugnaciones).

## 7g. F8 cobros, retiros, estados de cuenta, avisos, reportes y sanciones

**Hecho en el API** (2026-10-08). Decisiones del usuario: pasarela intercambiable, hoy
`manual` (el turista ve `PAYMENT_INSTRUCTIONS` y el equipo con `billing.manage` confirma el
pago); comisión 15 % configurable con `billing.manage`; solo córdobas; retiros del guía a
mano (cuenta cifrada, un cambio espera 24 h); estados de cuenta mensuales para comercios
(insignia + cupón validado) cobrados fuera de línea; avisos por Firebase Cloud Messaging +
bandeja; entran reportes y sanciones. Contrato: `docs/finanzas.md` y `docs/avisos.md`.

- `api_finance`: `tarifa` (sembradas: `comision_reserva` 15, `insignia_mensual` 300,
  `cupon_validado` 10), `pago` (uno por reserva con monto; se refleja en
  `reserva.estado_pago`), `comision` (copia la tasa), `cuenta_bancaria` (número con
  `encrypt_secret`, fuera del historial; `rotatetotpkeys` lo rota), `solicitud_retiro`,
  `movimiento_saldo` (libro del guía, la suma nunca negativa por trigger), `estado_cuenta`
  y sus líneas. Servicios: `gateway.py` (protocolo + `ManualGateway`), `payments.py`
  (`open_payment`, `cancel_payment`, `settle` cierra la reserva prestada y pagada),
  `balance.py`, `statements.py`. Comando `issuestatements [--period AAAA-MM]`.
- `api_notifications`: `aviso_emitido` (bandeja; `estado_push`), `token_notificacion`,
  preferencias por clase. `notify()` deja el aviso y, con Firebase y la preferencia, lo
  manda en `on_commit`. `push.py` firma el JWT de la cuenta de servicio con PyJWT y usa
  `urllib` (sin dependencias nuevas). Lo llaman reservas, postulaciones, cancelaciones,
  chat, reseñas, pagos, retiros y sanciones.
- `api_reports`: motivos (contexto `reporte`), `reporte` (persona, reseña, lugar o evento)
  y `sancion` (suspensión/expulsión cambian el estado con `change_status_sync`; `syncevents`
  levanta las suspensiones vencidas y también vence convocatorias).
- Pruebas: `test_finance.py`, `test_notifications.py`, `test_reports.py` (32); ayudas de
  reservas en `api_tests/services_helpers.py`.

**Falta de F8**: pasarela real y su webhook; vencimiento del pago pendiente; cola de tareas
para los envíos; avisos por correo. El portal y la app ya consumen F6 a F8 (sus memorias
dicen qué sigue en demo); en la app el push es solo una interfaz hasta que exista el
proyecto de Firebase.

Ajustes que pidieron los clientes al conectarse (2026-10-08): despublicar o retirar un
circuito cancela sus salidas y reservas; `official-circuit/{id}/departure/`;
`duration_minutes` con traslados estimados (`services/legs.py`, misma cuenta que el portal y
la app); mensaje legible para listas cortas; `code` en `coupon-redemption/`, `organizer_id`
en `cultural-event/`, `pricing/` para el comercio; `user_id` del guía e `id` de sus reseñas,
resumen de la convocatoria en las postulaciones y `notification/unread/`. Pedidos que quedan
abiertos: convocatorias con servicio, horas y transporte; chat en tiempo real; cuándo
vuelve a valer la insignia de un lugar; avisos en el idioma del teléfono. Decisiones del
usuario: la sesión no trae la ciudad de la organización; los estados de cuenta son solo para
comercios.

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
6. El identificador de Android y el bundle ID de iOS son `dev.kplan.app`. No hay URL de
   producción todavía: las de portal y API siguen como placeholders.
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
14. **Al desplegar F5**: migraciones `apicatalogs.0002_prestadores`, `apimoderation.0002` y
    `0003`, `apiprofiles.0001` (siembran idiomas, servicios, tipos de documento, motivos y
    estados). Programar `python src/manage.py expirecredentials` una vez al día: sin él,
    nadie se suspende cuando le vence un documento.
15. **Al desplegar F4**: migraciones `apicatalogs.0003_pilares`,
    `apiorganizations.0002_foto_dueno_preparar` y `0003_foto_lugares_circuitos`,
    `apiterritory.0002_lugares_circuitos` y `apiitineraries.0001_initial` (siembran pilares y
    estados). Los comercios ya aprobados **no** reciben su lugar solos: solo los que se
    aprueban desde ahora (se puede llamar `ensure_business_place_sync` en un shell). La
    producción arranca sin lugares ni circuitos: los crea el equipo o las alcaldías;
    `seedcontent` es solo para desarrollo y demo.
16. El `.gitleaks.toml` permite las líneas de dependencia de migraciones
    (`("apiterritory", "0002_...")`), que la regla genérica tomaba por claves.
17. **Al desplegar F6**: migraciones `apicatalogs.0004_agenda_cupones`, `apiagenda.0001`,
    `apiorganizations.0004_foto_evento` y `apirewards.0001`. Programar
    `python src/manage.py syncevents` una vez al día (eventos, campañas y cupones vencidos).
18. **Al desplegar F7**: migraciones `apiservices.0001`, `apimessaging.0001` y
    `apireputation.0001`.
19. **Al desplegar F8**: migraciones `apifinance.0001`, `apinotifications.0001` y
    `apireports.0001`. Definir `PAYMENT_INSTRUCTIONS` con la cuenta real a la que paga el
    turista. Programar `issuestatements` el día 1 de cada mes (además de `syncevents` y
    `expirecredentials` diarios). Para los avisos al teléfono hace falta un proyecto de
    Firebase: `FCM_PROJECT_ID` y `FCM_SERVICE_ACCOUNT` (secreto, solo en Railway) en el
    API y el `google-services.json` del mismo proyecto en la app; sin ellos, solo bandeja.

## 10. Cómo trabajar en cada máquina (Windows, PowerShell)

### PC 2 (`Lenovo`, `C:\coding\kplan2`)

- Postgres 18 y Redis en Docker: abrir Docker Desktop y, en el API,
  `$env:POSTGRES_PORT='5433'; $env:JWT_SECRET_KEY='x'*64; $env:SECRET_KEY='x'*64; docker compose up -d postgres redis`
  (las variables solo para que compose arranque; **quítalas de la shell después**: tapan las
  del `.env`). El `.env` local apunta a `127.0.0.1:5433` y a Redis en `6379`.
- `uv` se actualizó a 0.12 para poder instalar Python 3.14.6 (`.python-version`).
- Pruebas: `$env:PYTHONUTF8='1'; $env:DEBUG='False'; $env:CI='true'; uv run --frozen pytest --no-cov -q -p no:warnings`
  (con Redis corriendo no hace falta el módulo de ajustes locales de la PC 1).
- Servidor: `powershell -NoProfile -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\Temp\kplan-dev\start-api.ps1"`
  (log en `api.out.log` de la misma carpeta). Cuentas locales (contraseña `Kplan-Local-2026`,
  solo en la base de esta máquina): `admin@example.com` (superusuario),
  `alcaldia.leon@example.com`, `negocio.leon@example.com`, `turista@example.com`,
  `guia.leon@example.com` (guía aprobado, entra por la app) y `teatro.leon@example.com`
  (institución verificada, portal); se recrean con `dev_accounts.py` de esa carpeta
  (`manage.py shell -c "exec(open(...).read())"`). El servidor arrancado desde una terminal
  del agente puede morir con ella: arráncalo con `Start-Process -WindowStyle Hidden`.
  Contenido de ejemplo: `manage.py seedcontent`.
- `gitleaks` portátil en `%LOCALAPPDATA%\Temp\kplan-dev\gitleaks\gitleaks.exe`. No hay
  ganchos de `prek` instalados: córrelo a mano antes de cada commit.
- Desde PowerShell las cookies `Secure` del portal no viajan por `http`; para probar a mano
  usa el inicio de sesión móvil (`Bearer`) o un navegador.

### PC 1 (`PDesarrollo`, `C:\development`)

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
- `Paginated[Get](...)` con el tipo genérico sin resolver revienta en tiempo de ejecución
  (pydantic evalúa el límite del tipo): `paginate` recibe la clase del esquema.
- Dos apps con llaves foráneas cruzadas (`foto` -> `punto_interes` y `punto_interes` ->
  `comercio`): `makemigrations` parte la de `apiorganizations` en dos (quitar la
  restricción vieja y, después de crear las tablas de territorio, agregar las columnas).
  Las llaves foráneas hacia la otra app van como texto (`"apiterritory.Circuit"`).
- Un comentario como `# Ajustar (D-33)` lo marca `ruff` como código comentado.
- `ruff` es muy estricto (`ALL`): comentarios en lugar de docstrings en muchas piezas,
  líneas cortas, y `# ty: ignore[...]` donde los tipos de Django no resuelven (un ignore
  que sobra también es un aviso: quítalo).
