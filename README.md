<div align="center">
  <img
    src="docs/banner.svg"
    width="300"
    height="125"
  />
</div>

<h1 align="center">
  <code>kplan-api</code>
</h1>

<h3 align="center">
  Microservicios para la aplicación móvil K'Plan.
</h3>

<div align="center">

[![PostgreSQL.][postgres-badge]][postgres-docs]
[![Django.][django-badge]][django-docs]
[![OpenAPI.][openapi-badge]][openapi-docs]
<br>
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
1. Solicita interactivamente username y contraseña del
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

DATABASE_URL="postgresql://kplan-api:kplan-api@127.0.0.1:5432/kplan-api"
REDIS_URL="redis://127.0.0.1:6379"

JWT_SECRET_KEY="SECRET!!!"
SECRET_KEY="SECRET!!!"

REDIS_SECRET_KEY="kplan-api"

GRANIAN_HOST="127.0.0.1"
GRANIAN_INTERFACE="asginl"
GRANIAN_LOG_ACCESS_ENABLED="1"
GRANIAN_PORT="8080"
GRANIAN_RELOAD_PATHS="src"
GRANIAN_WORKERS="1"
GRANIAN_WORKING_DIR="src"
GRANIAN_WS="0"

DJANGO_SUPERUSER_PASSWORD="superuser-data"
DJANGO_SUPERUSER_USERNAME="superuser-data"
```

Notas importantes:

- Las credenciales de `DATABASE_URL` y `REDIS_URL` ya coinciden con las de
  los contenedores. No hay que crear bases de datos ni usuarios manualmente:
  el contenedor de PostgreSQL crea la base `kplan-api` en su primer arranque.
- `DJANGO_SUPERUSER_USERNAME` y `DJANGO_SUPERUSER_PASSWORD` deben estar definidas
  para poder usar `just mk-admin`, que crea el superuser sin interacción.
- `JWT_SECRET_KEY` y `SECRET_KEY` son obligatorias también para los
  perfiles de Docker (`compose.yml` las declara como
  requeridas con `${VAR:?}`).

Si quiere regenerar solo una llave:

```bash
just repl -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# o en linux, sin depender de python:
# tr -dc 'a-zA-Z0-9-_' < /dev/urandom | head -c 128
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

- `dev` (servicio `kplan-api-dev`): incluye las dependencias de
  desarrollo y arranca el servidor con `--reload`.
- `prod` (servicio `kplan-api-prod`): instala solo dependencias
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

# system checks de django:
just validate --deploy --fail-level WARNING

# correr las pruebas:
just test

# todo lo anterior:
just pre-commit
```

Para ver todas las recetas disponibles:

```bash
just
```

[django-badge]: https://img.shields.io/badge/django-white?style=for-the-badge&color=gray&logoColor=white&logo=django
[django-docs]: https://docs.djangoproject.com/en/
[docker]: https://docs.docker.com/get-started/get-docker/
[git]: https://git-scm.com/install/
[just]: https://github.com/casey/just
[openapi-badge]: https://img.shields.io/badge/openapi-white?style=for-the-badge&color=gray&logoColor=white&logo=openapiinitiative
[openapi-docs]: https://www.openapis.org/
[postgres-badge]: https://img.shields.io/badge/postgresql-white?style=for-the-badge&color=gray&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzOTQuNSA0MDgiPjxwYXRoIGZpbGw9IiNmZmZmZmYiIGQ9Ik0zODMuMiAyNTIuNWMtNTAuMyAxMC40LTUzLjgtNi42LTUzLjgtNi42QzM4Mi42IDE2NyA0MDQuOCA2NyAzODUuNiA0Mi42IDMzMy4zLTI0LjIgMjQyLjggNy40IDI0MS4zIDguMmgtLjVxLTE0LjgtMy0zMy41LTMuNGMtMjIuOC0uNC00MCA2LTUzLjEgMTUuOSAwIDAtMTYxLjUtNjYuNS0xNTQgODMuNkMyIDEzNi4zIDQ2IDM0NiA5OC44IDI4Mi42YzE5LjMtMjMuMiAzNy45LTQyLjcgMzcuOS00Mi43YTQ5IDQ5IDAgMCAwIDMxLjkgOC4xbC45LS44Yy0uMyAzLS4xIDUuNy40IDktMTMuNiAxNS4yLTkuNiAxNy45LTM2LjggMjMuNS0yNy40IDUuNi0xMS4zIDE1LjctLjggMTguMyAxMi44IDMuMiA0Mi40IDcuOCA2Mi4zLTIwLjJsLS44IDMuMmM1LjMgNC4zIDkgMjcuNyA4LjQgNDktLjYgMjEuMi0xIDM1LjggMy4yIDQ3LjJzOC40IDM3IDQ0IDI5LjRjMjkuOC02LjQgNDUuMy0yMyA0Ny40LTUwLjUgMS42LTE5LjYgNS0xNi43IDUuMi0zNC4zbDIuOC04LjNjMy4yLTI2LjYuNS0zNS4yIDE4LjktMzEuMmw0LjQuNGMxMy42LjYgMzEuMi0yLjIgNDEuNi03IDIyLjQtMTAuNCAzNS42LTI3LjcgMTMuNi0yMy4yIi8+PC9zdmc+Cg==
[postgres-docs]: https://www.postgresql.org/docs/
[rootless]: https://docs.docker.com/engine/security/rootless/
[ruff-badge]: https://img.shields.io/badge/ruff-white?style=for-the-badge&color=gray&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA0MCA0MCI+PHBhdGggZmlsbD0iI2ZmZmZmZiIgZmlsbC1ydWxlPSJldmVub2RkIiBkPSJNNDAgNGE0IDQgMCAwIDAtNC00SDB2NDBoMTguNFYyOGgzLjJ2MTJINDBWMjQuOGgtOHYtMy4yaDRhNCA0IDAgMCAwIDQtNFpNMjQuOCAxNS4ydjMuMmgtOS42di0zLjJ6IiBjbGlwLXJ1bGU9ImV2ZW5vZGQiLz48L3N2Zz4K
[ruff-docs]: https://docs.astral.sh/ruff
[ty-badge]: https://img.shields.io/badge/ty-white?style=for-the-badge&color=gray&logoColor=white&logo=ty
[ty-docs]: https://docs.astral.sh/ty
[uv-badge]: https://img.shields.io/badge/uv-white?style=for-the-badge&color=gray&logoColor=white&logo=uv
[uv-docs]: https://docs.astral.sh/uv
[uv-install]: https://docs.astral.sh/uv/#installation
