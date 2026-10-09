<div align="center">
  <img
    src="docs/banner.svg"
    width="300"
    height="125"
    style="padding: 10px;"
  />
</div>

<h1 align="center">
  <code>kplan-api</code>
</h1>

<h3 align="center">
  Microservicios para la aplicación móvil <code>k'plan</code>
</h3>

<div align="center">

[![PostgreSQL.][postgres-badge]][postgres-docs]
[![Django.][django-badge]][django-docs]
[![OpenAPI.][openapi-badge]][openapi-docs]
<br/>
[![ruff.][ruff-badge]][ruff-docs]
[![ty.][ty-badge]][ty-docs]
[![uv.][uv-badge]][uv-docs]

</div>

## Ejecución Local

### Requisitos

Debe tener estas herramientas previamente instaladas para configurar el proyecto.

1. [`docker`][docker]
   - Esta instalación **debe** incluir `docker compose`.
   - Idealmente, también _debería_ ser [rootless][rootless], ya que algunos flujos
     de configuración crean archivos. Si `docker` no es rootless, estos archivos
     se crearían con permisos elevados y no se podrán modificar.
1. [`git`][git]
1. [`just`][just]
1. [`uv`][uv-install]
   - Versión `0.12.1` o superior (la que usan el CI y el `dockerfile`). Una
     versión anterior puede no conocer el Python fijado en `.python-version`.
1. [`prettier`][prettier]
   - Lo usa `just fmt`, y con él `just full-fix`, `just mk-migrations`,
     `just pre-commit` y el hook de `prek` que instala `just init-local`.

Opcional: [`jq`][jq], solo para las recetas `local-*` y `remote-*` (que además
usan `curl`).

Las recetas de `just` usan `bash`. En Windows use Git Bash (se instala junto
con `git`) o WSL2.

No necesita instalar PostgreSQL ni Redis: ambos se levantan
como contenedores definidos en `compose.yml`.

### Clonar repositorio

```bash
git clone https://github.com/Los-Come-Tuani/api kplan-api
cd kplan-api
```

### Setup automático

La forma más rápida de dejar el proyecto listo es:

```bash
just init-local
```

Esta receta hace todo el trabajo pesado:

1. Genera el archivo `.env` a partir de `.env.example`.
1. Solicita interactivamente el correo y la contraseña del
   superuser local, y los escribe en el `.env`.
1. Instala las dependencias con `uv sync --frozen`.
1. Instala los hooks de `prek`.
1. Levanta los contenedores de PostgreSQL y Redis.
1. Corre las migraciones.
1. Crea el superuser.
1. Siembra datos iniciales.

Si prefiere hacerlo paso a paso, continúe con las secciones siguientes.

### Setup manual

#### Instalación de dependencias

```bash
just sync
```

#### Variables de entorno

El proyecto **exige** ciertas variables de entorno o fallará al iniciar.
Para generar el `.env` con llaves secretas aleatorias:

```bash
just init-env
```

El archivo resultante toma `.env.example` como base:

```bash
DEBUG="True"
DEPLOY="False"
SKIP_SEEDERS="False"

DATABASE_URL="postgresql://kplanapi:kplanapi@127.0.0.1:5432/kplanapi"
REDIS_URL="redis://127.0.0.1:6379"

JWT_SECRET_KEY="SECRET!!!"
SECRET_KEY="SECRET!!!"

REDIS_SECRET_KEY="kplanapi"

# Listas separadas por comas. Vacías = valores de desarrollo.
ALLOWED_HOSTS=""
CORS_ALLOWED_ORIGINS=""
CSRF_TRUSTED_ORIGINS=""

GRANIAN_HOST="127.0.0.1"
GRANIAN_INTERFACE="asginl"
GRANIAN_LOG_ACCESS_ENABLED="1"
GRANIAN_PORT="8080"
GRANIAN_RELOAD_PATHS="src"
GRANIAN_WORKERS="1"
GRANIAN_WORKING_DIR="src"
GRANIAN_WS="0"

DJANGO_SUPERUSER_EMAIL="admin@example.com"
DJANGO_SUPERUSER_PASSWORD="Superuser-Data-2026"
```

Notas importantes:

- Las credenciales de `DATABASE_URL` y `REDIS_URL` ya coinciden con las de
  los contenedores. No hay que crear bases de datos ni usuarios manualmente:
  el contenedor de PostgreSQL crea la base `kplanapi` en su primer arranque.
- Si el puerto `5432` de su máquina ya está ocupado (por ejemplo, por un
  PostgreSQL instalado localmente), agregue `POSTGRES_PORT="5433"` al `.env`
  (o el puerto libre que prefiera) y use ese mismo puerto en `DATABASE_URL`.
  Solo cambia el puerto publicado en su máquina: dentro de Docker el API sigue
  conectándose a `postgres:5432`.
- `DJANGO_SUPERUSER_EMAIL` y `DJANGO_SUPERUSER_PASSWORD` deben estar definidas
  para poder usar `just mk-admin`, que crea el superuser sin interacción. Todas las
  cuentas, el superuser incluido, inician sesión con el correo.
- Los correos (códigos de verificación y de recuperación de contraseña) salen por
  la consola del API mientras no se defina `EMAIL_HOST`; con `DEPLOY=True` y sin
  `EMAIL_HOST` se descartan, para que ningún código quede en los logs. En
  producción define `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` y
  `DEFAULT_FROM_EMAIL` en el servicio.
- `JWT_SECRET_KEY` y `SECRET_KEY` son obligatorias también para los
  perfiles de Docker (`compose.yml` las declara como
  requeridas con `${VAR:?}`).
- `TOTP_ENCRYPTION_KEYS` son las llaves Fernet con las que se cifra en la base el
  secreto del 2FA. Vacía, en desarrollo se deriva de `SECRET_KEY`; con
  `DEPLOY=True` es obligatoria (genere una con `just fernet-key`). Para rotarlas,
  anteponga la llave nueva, corra `just dj-man rotatetotpkeys` y retire la vieja.
- `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` son listas
  separadas por comas. Vacías, el API acepta `localhost`, `127.0.0.1`, `10.0.2.2`
  (el emulador de Android) y los orígenes `http://localhost:3000` y
  `http://localhost:5173` (el portal). En producción se definen como variables del
  servicio (el App Service de Azure, o Railway para `develop-a`; ver
  [Despliegue en Azure](#despliegue-en-azure)), nunca en el repositorio; los
  orígenes deben ser `https` y sin `/` final, y `ALLOWED_HOSTS` no admite `*` con
  `DEPLOY=True`.
- Use `localhost` y no `127.0.0.1` al abrir el portal y el API: son del mismo
  sitio solo si comparten el nombre de host, y sin eso las cookies de sesión no
  viajan.

Si quiere regenerar solo una llave:

```bash
just repl -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# o en unix, sin depender de python:
tr -dc 'a-zA-Z0-9-_' < /dev/urandom | head -c 128
```

#### Levantar servicios

```bash
just services
```

Esta receta levanta `postgres` y `redis` en segundo plano y espera a que
sus healthchecks pasen. Es una dependencia implícita de casi todas
las recetas de Django (`migrate`, `run`, `serve`, `test`, `validate`),
así que rara vez necesitará invocarla directamente.

#### Migrar base de datos

```bash
just migrate
```

#### Crear usuario admin

```bash
just mk-admin
```

#### Sembrar datos iniciales

```bash
just dj-man populate
```

### Ejecutar el API

Hay dos modos de trabajo.

#### Modo local (recomendado para desarrollo)

El API corre en su máquina con `uv`, contra PostgreSQL y Redis dockerizados.
Esto le da recarga en caliente inmediata y acceso directo al debugger.

```bash
# con DEBUG=True y recarga automática:
just run

# con DEBUG=False, sin recarga (más parecido a producción):
just serve
```

El servidor queda disponible en `http://127.0.0.1:8080`.

#### Modo Docker

El API corre dentro de un contenedor construido desde el `dockerfile`.
El `compose.yml` define dos perfiles:

- `dev` (servicio `kplanapi-dev`): incluye las dependencias de
  desarrollo y arranca el servidor con `--reload`.
- `prod` (servicio `kplanapi-prod`): instala solo dependencias
  de producción, fuerza `DEBUG=False` y no monta volúmenes.

```bash
# levantar el perfil dev (por defecto):
just up

# levantar el perfil prod:
just up prod
```

`just up` construye la imagen del perfil, ejecuta el servicio `migrate` de un
solo uso, y luego levanta el API esperando su healthcheck (`GET /health/`).

Si solo quiere construir la imagen sin levantarla:

```bash
just build
just build prod
```

En ambos perfiles el API se expone en `http://127.0.0.1:8080`.

> **Windows:** el perfil `dev` monta `./src` como _bind mount_, y en Docker
> Desktop para Windows eso vuelve muy lento el arranque del API (minutos), por
> lo que `just up` puede terminar con el contenedor `unhealthy` aunque luego se
> recupere. En Windows prefiera el modo local, el perfil `prod`, o clone el
> repositorio dentro del sistema de archivos de WSL2.

### Comandos útiles

```bash
# ejecutar cualquier comando de manage.py:
just dj-man <comando>

# abrir el shell de django:
just dj-repl

# generar migraciones:
just mk-migrations

# linting, formato y type checking:
just full-check
just full-fix

# system checks de django, como en el CI (con el `DEBUG="True"` del `.env`
# local, `--deploy` siempre advierte sobre HSTS, cookies y `DEBUG`):
DEBUG=False just validate --deploy --fail-level WARNING

# correr las pruebas (incluye las de contrato con schemathesis, que recorren
# todas las rutas del OpenAPI con una sesión de superusuario):
just test

# generar una llave Fernet para TOTP_ENCRYPTION_KEYS:
just fernet-key

# volver a cifrar los secretos del 2FA con la llave primaria (tras rotar llaves):
just dj-man rotatetotpkeys

# todo lo anterior:
just pre-commit
```

Para ver todas las recetas disponibles:

```bash
just
```

### Problemas comunes

- `uv` falla con `Failed to inspect Python interpreter from search path` y
  nombra `WindowsApps\python3.exe` (Windows): es el alias de Python de la
  Microsoft Store, activo pero sin Python instalado. Desactive los alias de
  ejecución de aplicaciones de `python.exe` y `python3.exe` en la configuración
  de Windows, o defina `UV_PYTHON` con la ruta de su Python.
- `uv` falla con `No interpreter found for Python 3.14.6`: su `uv` es anterior a
  esa versión de Python. Actualícelo (`uv self update`, o el método con el que
  lo instaló).
- `just build` o `just up` fallan en `apt-get update` con `403 Forbidden`: algún
  proxy o firewall de su red está bloqueando el `User-Agent` de `apt`. Pruebe
  desde otra red o VPN.

## Despliegue en Azure

El API publicado en Azure es siempre el código de la rama `production` de este
repositorio, que es la rama por defecto en GitHub. Nadie copia código a Azure a
mano: cada `push` a `production` lo construye y lo despliega el workflow
[`.github/workflows/azure.yml`](.github/workflows/azure.yml).

| Rama         | Dónde corre                                | Dominio                         |
| ------------ | ------------------------------------------ | ------------------------------- |
| `production` | Azure App Service `kplan` (Canada Central) | `https://azure-api.kplan.dev`   |
| `develop-a`  | Railway                                    | `https://develop-api.kplan.dev` |

El portal (`https://portal.kplan.dev`), la landing (`https://kplan.dev`) y los
builds de release de la app móvil usan el API de Azure.

### Cómo llega un cambio a Azure

Los cambios se trabajan en `develop-a` (directamente o en una rama que se
fusiona en ella) y pasan a Azure al fusionar `develop-a` en `production`:

```bash
git switch production
git pull --ff-only
git merge --no-ff develop-a -m "merge: develop-a en production"
git push origin production
```

Con ese `push`, el workflow:

1. Construye la imagen del `dockerfile` con la etapa `runtime-azure`.
1. La publica en Docker Hub como [`jpzunigadev/kplan-api`][kplan-image], con
   dos etiquetas: `latest` y el SHA completo del commit.
1. Le indica al App Service `kplan` que corra la imagen etiquetada con ese SHA
   (`azure/webapps-deploy`). Azure nunca usa `latest`: cada despliegue queda
   atado a un commit exacto de `production`.

Al arrancar, el contenedor (`scripts/start.sh`) aplica las migraciones
pendientes, levanta Nginx en el puerto `8080` (`deploy/azure/nginx.conf`) y deja
el API (Granian) en `127.0.0.1:8000`, detrás de Nginx. App Service termina el
HTTPS y reenvía el tráfico al `8080`. Como `ALLOWED_HOSTS` incluye
`azure-api.kplan.dev`, cada `migrate` carga además el contenido de ejemplo, que
solo agrega lo que falte.

### Configuración

Secretos del repositorio en GitHub (Settings → Secrets and variables →
Actions):

- `DOCKERHUB_USERNAME` y `DOCKERHUB_TOKEN`: la cuenta de Docker Hub que publica
  la imagen.
- `AZUREAPPSERVICE_PUBLISHPROFILE_4AE80A6822C44E7EB53A50603913BF05`: el perfil
  de publicación del App Service `kplan` (se descarga desde la página del App
  Service en el portal de Azure).

Variables de entorno del App Service `kplan` (contenedor Linux), en el portal de
Azure:

- `WEBSITES_PORT=8080`, el puerto de Nginx.
- `DEPLOY=True` y `DEBUG=False`.
- `DATABASE_URL` (PostgreSQL), `REDIS_URL` y `REDIS_SECRET_KEY`. Con un Redis
  administrado con TLS (`rediss://`), como el de Azure, la clave puede tener 32
  caracteres; sin TLS se piden 64.
- `SECRET_KEY` y `JWT_SECRET_KEY` (de 64 a 256 caracteres) y
  `TOTP_ENCRYPTION_KEYS` (`just fernet-key`).
- `ALLOWED_HOSTS` con `azure-api.kplan.dev`, y `CORS_ALLOWED_ORIGINS` con
  `https://portal.kplan.dev`, `https://kplan.dev` y `https://www.kplan.dev`
  (`CSRF_TRUSTED_ORIGINS` toma esos mismos si no se define).
- Opcionales: `EMAIL_*` (sin ellas los correos se descartan),
  `GOOGLE_OAUTH_CLIENT_IDS`, `STORAGE_*` (ver `docs/archivos.md`) y `FCM_*`.

Los valores viven solo en GitHub y en Azure, nunca en el repositorio. Cambiar
una variable reinicia el App Service con la misma imagen: el código que corre no
cambia.

### Comprobar que Azure corre lo mismo que `production`

1. Anote el SHA del último commit de `production` en GitHub:

   ```bash
   git ls-remote https://github.com/Los-Come-Tuani/api refs/heads/production
   ```

1. En GitHub, Actions → "deploy to azure web app - kplan": la última ejecución
   tiene que ser de ese commit y estar en verde.
1. La imagen que corre el App Service tiene que llevar ese SHA como etiqueta.
   En el portal de Azure se ve en App Service `kplan` → Centro de
   implementación; con la CLI de Azure:

   ```bash
   az webapp config show --name kplan --resource-group <grupo-de-recursos> \
     --query linuxFxVersion --output tsv
   # DOCKER|docker.io/jpzunigadev/kplan-api:<SHA>
   ```

   La misma etiqueta aparece en las [etiquetas de la imagen][kplan-image-tags]
   en Docker Hub.

1. El API responde:

   ```bash
   curl https://azure-api.kplan.dev/health/
   # {"status":"success","components":{"cache":"ok","database":"ok","storage":"ok"}}
   ```

Mientras el workflow corre (unos minutos después del `push`), Azure sigue con el
commit anterior.

### Reglas para que no se separen

- No se despliega por otro camino (ZIP, FTP, `az webapp deploy`, archivos
  editados desde Kudu o el portal de Azure) ni se cambia a mano la imagen del
  App Service: Azure quedaría corriendo algo que no está en `production`.
- Para deshacer un cambio publicado se hace `git revert` en `production` y se
  empuja; el workflow despliega ese commit nuevo. No se apunta el App Service a
  una etiqueta vieja.
- Para volver a desplegar sin cambios (por ejemplo, si una ejecución falló por
  algo externo), se relanza el workflow desde Actions → "Run workflow" sobre
  `production`.

[django-badge]: https://img.shields.io/badge/django-white?style=for-the-badge&color=gray&logoColor=white&logo=django
[django-docs]: https://docs.djangoproject.com/en/
[docker]: https://docs.docker.com/get-started/get-docker/
[git]: https://git-scm.com/install/
[jq]: https://jqlang.org/download/
[just]: https://github.com/casey/just
[kplan-image]: https://hub.docker.com/r/jpzunigadev/kplan-api
[kplan-image-tags]: https://hub.docker.com/r/jpzunigadev/kplan-api/tags
[openapi-badge]: https://img.shields.io/badge/openapi-white?style=for-the-badge&color=gray&logoColor=white&logo=openapiinitiative
[openapi-docs]: https://www.openapis.org/
[postgres-badge]: https://img.shields.io/badge/postgresql-white?style=for-the-badge&color=gray&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzOTQuNSA0MDgiPjxwYXRoIGZpbGw9IiNmZmZmZmYiIGQ9Ik0zODMuMiAyNTIuNWMtNTAuMyAxMC40LTUzLjgtNi42LTUzLjgtNi42QzM4Mi42IDE2NyA0MDQuOCA2NyAzODUuNiA0Mi42IDMzMy4zLTI0LjIgMjQyLjggNy40IDI0MS4zIDguMmgtLjVxLTE0LjgtMy0zMy41LTMuNGMtMjIuOC0uNC00MCA2LTUzLjEgMTUuOSAwIDAtMTYxLjUtNjYuNS0xNTQgODMuNkMyIDEzNi4zIDQ2IDM0NiA5OC44IDI4Mi42YzE5LjMtMjMuMiAzNy45LTQyLjcgMzcuOS00Mi43YTQ5IDQ5IDAgMCAwIDMxLjkgOC4xbC45LS44Yy0uMyAzLS4xIDUuNy40IDktMTMuNiAxNS4yLTkuNiAxNy45LTM2LjggMjMuNS0yNy40IDUuNi0xMS4zIDE1LjctLjggMTguMyAxMi44IDMuMiA0Mi40IDcuOCA2Mi4zLTIwLjJsLS44IDMuMmM1LjMgNC4zIDkgMjcuNyA4LjQgNDktLjYgMjEuMi0xIDM1LjggMy4yIDQ3LjJzOC40IDM3IDQ0IDI5LjRjMjkuOC02LjQgNDUuMy0yMyA0Ny40LTUwLjUgMS42LTE5LjYgNS0xNi43IDUuMi0zNC4zbDIuOC04LjNjMy4yLTI2LjYuNS0zNS4yIDE4LjktMzEuMmw0LjQuNGMxMy42LjYgMzEuMi0yLjIgNDEuNi03IDIyLjQtMTAuNCAzNS42LTI3LjcgMTMuNi0yMy4yIi8+PC9zdmc+Cg==
[postgres-docs]: https://www.postgresql.org/docs/
[prettier]: https://prettier.io/docs/install
[rootless]: https://docs.docker.com/engine/security/rootless/
[ruff-badge]: https://img.shields.io/badge/ruff-white?style=for-the-badge&color=gray&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0MCA0MCI+PHBhdGggZmlsbD0iI2ZmZmZmZiIgZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNNDAgNGE0IDQgMCAwIDAtNC00SDB2NDBoMTguNFYyOGgzLjJ2MTJINDBWMjQuOGgtOHYtMy4yaDRhNCA0IDAgMCAwIDQtNFpNMjQuOCAxNS4ydjMuMmgtOS42di0zLjJ6IiBjbGlwLXJ1bGU9ImV2ZW5vZGQiLz48L3N2Zz4K
[ruff-docs]: https://docs.astral.sh/ruff
[ty-badge]: https://img.shields.io/badge/ty-white?style=for-the-badge&color=gray&logoColor=white&logo=ty
[ty-docs]: https://docs.astral.sh/ty
[uv-badge]: https://img.shields.io/badge/uv-white?style=for-the-badge&color=gray&logoColor=white&logo=uv
[uv-docs]: https://docs.astral.sh/uv
[uv-install]: https://docs.astral.sh/uv/#installation
