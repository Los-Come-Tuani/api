---
icon: lucide/globe
---

# Landing: solicitudes de demo y versiones de la app

Lo que alimenta el sitio público de K'Plan (repo `landing-page`): el formulario para pedir
una demostración y la descarga de los instaladores de la app. El equipo los atiende y los
publica desde el portal, en el grupo "Sitio web". Es la fase F9 de la
[hoja de ruta](hoja-de-ruta.md).

## Lo que se decidió

- **El API guarda todo; la landing solo llama a rutas públicas.** El portal es el panel
  privado: ahí se atienden las solicitudes y se suben y publican los instaladores.
- **Pedir una demo no crea una cuenta.** Quien la pide deja nombre, correo, organización y
  qué es; el equipo lo contacta por fuera y anota cómo va.
- **Contra el abuso**, sin servicios externos: el límite estricto de peticiones (10 por
  minuto por dirección) y un campo trampa (`website`) que la landing esconde. Si llega
  lleno se responde igual que a una persona y no se guarda nada.
- **Aviso en la campana del portal** a quien tenga `demos.manage` (y a los superusuarios).
  Sin correo.
- **Un instalador por versión y plataforma**: APK para Android, DMG para macOS y EXE para
  Windows. iOS no se reparte como archivo (va por App Store o TestFlight).
- **La vigente de cada plataforma es la publicada más reciente.** Publicar otra la
  reemplaza; retirarla deja otra vez la anterior.
- El bucket sigue **privado**: la landing enlaza a una ruta del API que redirige a una URL
  firmada recién hecha, así el enlace nunca vence.

## Permisos

Cuatro permisos nuevos en el módulo "Sitio web" del catálogo ([Roles y permisos](roles.md)).
`manage` incluye el `view` de su área.

| Permiso           | Qué abre                                                       |
| ----------------- | -------------------------------------------------------------- |
| `demos.view`      | Ver la bandeja de solicitudes de demo                          |
| `demos.manage`    | Cambiar su estado y notas; recibe el aviso de cada una nueva   |
| `releases.view`   | Ver las versiones y descargar cualquier instalador para probar |
| `releases.manage` | Subir instaladores, crear, corregir, publicar, retirar, borrar |

## Solicitudes de demo

| Ruta                       | Quién                | Qué hace                                        |
| -------------------------- | -------------------- | ----------------------------------------------- |
| `POST demo-request/`       | Pública (sin sesión) | La landing manda la solicitud (`204`)           |
| `GET demo-request/`        | `demos.view`         | La bandeja, de la más nueva. Paginada           |
| `GET demo-request/{id}/`   | `demos.view`         | Una solicitud                                   |
| `PATCH demo-request/{id}/` | `demos.manage`       | Cambia `status` y `notes`; anota quién y cuándo |

Cuerpo del `POST`:

```json
{
  "name": "Lucía Martínez",
  "email": "lucia@ejemplo.com",
  "phone": "+505 8888 0000",
  "organization": "Café Sacuanjoche",
  "kind": "business",
  "city": "León",
  "message": "Queremos ver cómo se publican los cupones.",
  "website": ""
}
```

- `kind`: `business`, `municipality`, `institution`, `tour_operator` u `other`.
- `phone`, `city`, `message` y `website` son opcionales. `website` es la trampa: la landing
  lo manda vacío.
- Si el mismo correo ya tiene una solicitud `new` (sin atender), se corrige esa con lo
  nuevo y no sale otro aviso. Una vez atendida, otra solicitud abre una nueva.
- Un dato inválido responde `400` con `field_errors`; el límite, `429`.

`GET demo-request/` acepta `status`, `search` (nombre u organización sin importar tildes, o
correo), `page` y `page_size`. Cada solicitud:

```json
{
  "id": "…",
  "name": "Lucía Martínez",
  "email": "lucia@ejemplo.com",
  "phone": "+505 8888 0000",
  "organization": "Café Sacuanjoche",
  "kind": "business",
  "city": "León",
  "message": "…",
  "status": "new",
  "notes": "",
  "created_at": "…",
  "updated_at": null,
  "updated_by": null
}
```

`status`: `new` → `contacted` → `scheduled` → `done`, o `dismissed`. El API acepta pasar
de cualquiera a cualquiera (corregir un error también es un cambio). El aviso que llega a
la campana es `kind: "solicitud_demo"` con `data: { "demo_request_id" }`.

## Versiones de la app

| Ruta                                          | Quién             | Qué hace                                                       |
| --------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| `POST app-release/upload/`                    | `releases.manage` | URL firmada para subir el instalador (`201`)                   |
| `GET app-release/`                            | `releases.view`   | Todas las versiones, de la más nueva. Paginado                 |
| `POST app-release/`                           | `releases.manage` | Registra la versión con su instalador ya subido, como borrador |
| `PATCH app-release/{id}/`                     | `releases.manage` | Corrige `notes` (siempre) y `version` (solo en borrador)       |
| `DELETE app-release/{id}/`                    | `releases.manage` | Borra un borrador y su instalador (`204`)                      |
| `POST app-release/{id}/publish/`              | `releases.manage` | La publica: pasa a ser la vigente de su plataforma             |
| `POST app-release/{id}/withdraw/`             | `releases.manage` | La retira: vuelve la publicada anterior                        |
| `GET app-release/{id}/download/`              | `releases.view`   | `{ url }` firmada por cinco minutos; no cuenta como descarga   |
| `GET app-release/latest/`                     | Pública           | La vigente de cada plataforma (lista vacía si no hay)          |
| `GET app-release/latest/{platform}/download/` | Pública           | Redirige (`302`) al instalador vigente y cuenta la descarga    |

### Subir un instalador

1. `POST app-release/upload/` con `{ "platform": "android", "size": 41234567 }`. Responde
   como [`POST /upload/`](archivos.md): `{ key, url, method: "PUT", headers, expires_in,
max_bytes }`. La URL vive una hora (un instalador pesa cientos de MB).
2. El portal sube el archivo con un `PUT` a `url`, con las `headers` tal cual. El tipo lo
   fija la plataforma, no el navegador:

   | Plataforma | Archivo | `Content-Type`                                  |
   | ---------- | ------- | ----------------------------------------------- |
   | `android`  | `.apk`  | `application/vnd.android.package-archive`       |
   | `macos`    | `.dmg`  | `application/x-apple-diskimage`                 |
   | `windows`  | `.exe`  | `application/vnd.microsoft.portable-executable` |

   Hasta 500 MB por instalador.

3. `POST app-release/` con `{ "platform", "version", "notes"?, "file": key }`. El API
   comprueba que la clave sea un instalador de esa plataforma ya subido con su tipo y
   tamaño (`400` en `file` si no). `version` es `1.2.0`, `1.2.0-beta.1` o `1.2.0+14`;
   repetida en la misma plataforma responde `409` en `version`.

No es la ruta pública `POST /upload/`: esa la puede usar cualquiera y no admite
instaladores.

### Una versión

```json
{
  "id": "…",
  "platform": "android",
  "version": "1.2.0",
  "notes": "Corrige el inicio de sesión con Google.",
  "status": "published",
  "current": true,
  "file_name": "kplan-1.2.0.apk",
  "size": 41234567,
  "downloads": 18,
  "created_at": "…",
  "created_by": "Rosa",
  "published_at": "…",
  "withdrawn_at": null
}
```

- `status`: `draft`, `published` o `withdrawn`. `current` dice si es la que hoy se descarga
  desde la landing. Una publicada que ya no es la vigente sigue `published`: si se retira
  la vigente, vuelve a serlo.
- Publicar dos veces, o retirar algo que no está publicado, responde `409`. Publicar
  comprueba que el instalador siga en el bucket. Una retirada se puede volver a publicar.
- Solo un borrador se borra (`409` si no); el instalador se borra del bucket al confirmar.

### Lo que usa la landing

`GET app-release/latest/` devuelve, por plataforma, `{ platform, version, notes,
file_name, size, published_at }`. El botón de descarga es un enlace normal a
`GET app-release/latest/{platform}/download/`: responde `302` a una URL firmada por cinco
minutos con `Content-Disposition: attachment; filename="kplan-1.2.0.apk"`, y suma uno a
`downloads`. Sin versión publicada, `404`; una plataforma que no existe, `400`.

## Al desplegar

- **Bucket**: sin almacenamiento configurado, subir, publicar y descargar responden `503`.
  Las solicitudes de demo funcionan igual. El bucket es el mismo de [Archivos](archivos.md);
  su CORS ya permite el `PUT` desde el portal.
- **CORS del API**: el dominio de la landing tiene que estar en `CORS_ALLOWED_ORIGINS`
  (y en `CSRF_TRUSTED_ORIGINS` si esa variable está definida) para que el navegador deje
  mandar el formulario. Los enlaces de descarga no lo necesitan.
- Los permisos nuevos se siembran al migrar; el rol Administrador los recibe solo. Para
  otro rol del equipo se marcan en el portal ("Roles y permisos").
