# Guía para agentes

API de K'Plan: Django 6.1 con django-modern-rest (async), PostgreSQL 18 y Redis. La consumen el
portal web (`C:\development\kplan\portal`) y la app móvil (`C:\development\mobile-1`).

## Léelo primero

Hay una hoja de ruta en curso (identidad, Google, enlace del portal y de la app, roles y
permisos). Antes de trabajar en ella lee `.cursor/memory/hoja-de-ruta.md`: dice qué está
hecho, qué falta, cómo correr todo en esta máquina y qué avisos hay para el usuario. El portal
y la app tienen su propia memoria en `.cursor/memory/hoja-de-ruta.md`.

## Reglas del repo

- Español en código, comentarios, docs y commits. Commits convencionales
  (`feat(auth): ...`, `fix(config): ...`, `docs: ...`). Sin emojis.
- Ramas: se trabaja en `develop-a` o en una rama `feat/...` que salga de ella. Nunca se
  commitea en `production` ni en `staging`. No se empuja sin que el usuario lo pida.
- Ningún secreto en git. Las claves reales viven solo en variables de entorno (Railway) y en
  el `.env` local, que está ignorado. Los `VITE_*` y `--dart-define` de los clientes terminan
  dentro del bundle o del APK: ahí solo van valores públicos. Antes de commitear,
  `gitleaks git --staged --redact` (el hook de `prek` también lo corre).
- El API manda el contrato. Todo cambio de rutas o de formas de respuesta se refleja en
  `docs/autenticacion.md` (o la guía que corresponda) y lo comprueba `schemathesis` contra
  `/openapi/`.
- Cada cambio de comportamiento lleva su prueba en `src/api_tests`. Antes de cerrar:
  `ruff format`, `ruff check`, `ty check`, `makemigrations --check` y `pytest`
  (los comandos exactos, con el entorno de esta máquina, están en la memoria).
- Los errores de la API siguen la forma `{ "detail": "...", "field_errors": { ... } }` y no
  revelan si una cuenta existe.
