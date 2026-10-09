---
icon: lucide/globe
---

# Landing: solicitudes de demo y versiones de la app

Lo que alimenta el sitio público de K'Plan (repo `landing-page`): el formulario para pedir
una demostración, que es también la forma de recibir la app. El equipo atiende las
solicitudes y registra las versiones desde el portal, en el grupo "Sitio web". Es la fase
F9 de la [hoja de ruta](hoja-de-ruta.md).

## Lo que se decidió

- **El API guarda todo; la landing solo llama a rutas públicas.** El portal es el panel
  privado: ahí se ven las solicitudes y se registran y publican las versiones.
- **La app se entrega con el formulario.** Quien pide una demo deja nombre, correo,
  organización y qué es; en la misma respuesta recibe el link de cada versión publicada.
  La landing no tiene descarga directa.
- **Entregada o pendiente.** Si al pedirla había una versión publicada, la solicitud queda
  entregada; si no, queda pendiente y la landing le dice que se le avisará. No sale ningún
  correo: el equipo le hace llegar el link por fuera y la marca como entregada.
- **Cada versión es un link de Drive**, no un archivo en el bucket: una por versión y
  plataforma (Android, macOS, Windows). iOS no se reparte así (va por App Store o
  TestFlight).
- **La vigente de cada plataforma es la publicada más reciente.** Publicar otra la
  reemplaza; retirarla deja otra vez la anterior.
- **Contra el abuso**, sin servicios externos: el límite estricto de peticiones (10 por
  minuto por dirección) y un campo trampa (`website`) que la landing esconde. Si llega
  lleno se responde igual que a una persona y no se guarda nada.
- **Aviso en la campana del portal** a quien tenga `demos.manage` (y a los superusuarios),
  diciendo si ya recibió el link o hay que hacérselo llegar.

## Permisos

Cuatro permisos en el módulo "Sitio web" del catálogo ([Roles y permisos](roles.md)).
`manage` incluye el `view` de su área.

| Permiso           | Qué abre                                                         |
| ----------------- | ---------------------------------------------------------------- |
| `demos.view`      | Ver la bandeja de solicitudes de demo                            |
| `demos.manage`    | Marcarlas entregadas o pendientes y anotar; recibe el aviso      |
| `releases.view`   | Ver las versiones con sus links                                  |
| `releases.manage` | Registrar versiones, corregirlas, publicarlas, retirarlas, borrar |

## Solicitudes de demo

| Ruta                       | Quién                | Qué hace                                             |
| -------------------------- | -------------------- | ---------------------------------------------------- |
| `POST demo-request/`       | Pública (sin sesión) | La landing manda la solicitud y recibe los links     |
| `GET demo-request/`        | `demos.view`         | La bandeja, de la más nueva. Paginada                |
| `GET demo-request/{id}/`   | `demos.view`         | Una solicitud                                        |
| `PATCH demo-request/{id}/` | `demos.manage`       | Cambia `status` y `notes`; anota quién y cuándo      |

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
- Un dato inválido responde `400` con `field_errors`; el límite, `429`.

Responde `200` con lo que la landing muestra en ese momento:

```json
{
  "delivered": true,
  "links": [
    {
      "platform": "android",
      "version": "1.2.0",
      "link": "https://drive.google.com/file/d/…/view"
    }
  ]
}
```

- `links` trae la versión vigente de cada plataforma; vacía (y `delivered: false`) si no
  hay ninguna publicada.
- Cada link entregado suma uno a las `deliveries` de su versión.
- Si el mismo correo ya tiene una solicitud pendiente, se corrige esa con lo nuevo (y
  queda entregada si ahora hay links) y no sale otro aviso. Una entregada no se corrige:
  otra solicitud abre una nueva.

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
  "status": "delivered",
  "delivered_at": "…",
  "notes": "",
  "created_at": "…",
  "updated_at": null,
  "updated_by": null
}
```

`status`: `pending` o `delivered`. Pasar a `delivered` anota `delivered_at`; volver a
`pending` lo borra. El aviso que llega a la campana es `kind: "solicitud_demo"` con
`data: { "demo_request_id" }`.

## Versiones de la app

| Ruta                              | Quién             | Qué hace                                               |
| --------------------------------- | ----------------- | ------------------------------------------------------ |
| `GET app-release/`                | `releases.view`   | Todas las versiones, de la más nueva. Paginado         |
| `POST app-release/`               | `releases.manage` | Registra una versión con su link, como borrador        |
| `PATCH app-release/{id}/`         | `releases.manage` | Corrige `notes` y `link` (siempre) y `version` (solo en borrador) |
| `DELETE app-release/{id}/`        | `releases.manage` | Borra un borrador (`204`)                              |
| `POST app-release/{id}/publish/`  | `releases.manage` | La publica: pasa a ser la vigente de su plataforma     |
| `POST app-release/{id}/withdraw/` | `releases.manage` | La retira: vuelve la publicada anterior                |
| `GET app-release/latest/`         | Pública           | Qué versión hay de cada plataforma, sin el link        |

Cuerpo del `POST`: `{ "platform", "version", "notes"?, "link" }`.

- `platform`: `android`, `macos` o `windows`.
- `version` es `1.2.0`, `1.2.0-beta.1` o `1.2.0+14`; repetida en la misma plataforma
  responde `409` en `version`.
- `link` es el link compartido de Drive (o de otro sitio) donde está el instalador; tiene
  que ser `https`. El API no comprueba que el archivo exista: el equipo prueba el link
  antes de publicar.

Una versión:

```json
{
  "id": "…",
  "platform": "android",
  "version": "1.2.0",
  "notes": "Corrige el inicio de sesión con Google.",
  "link": "https://drive.google.com/file/d/…/view",
  "status": "published",
  "current": true,
  "deliveries": 18,
  "created_at": "…",
  "created_by": "Rosa",
  "published_at": "…",
  "withdrawn_at": null
}
```

- `status`: `draft`, `published` o `withdrawn`. `current` dice si es la que hoy se entrega
  con el formulario. Una publicada que ya no es la vigente sigue `published`: si se retira
  la vigente, vuelve a serlo.
- Publicar dos veces, o retirar algo que no está publicado, responde `409`. Una retirada se
  puede volver a publicar.
- Solo un borrador se borra (`409` si no).

### Lo que usa la landing

- El formulario: `POST demo-request/`, y con la respuesta muestra los links o el aviso de
  que se le avisará.
- `GET app-release/latest/` devuelve, por plataforma, `{ platform, version, notes,
  published_at }`, para decir qué hay disponible. El link no está ahí: solo llega con la
  solicitud.

## Al desplegar

- **CORS del API**: el dominio de la landing tiene que estar en `CORS_ALLOWED_ORIGINS`
  (y en `CSRF_TRUSTED_ORIGINS` si esa variable está definida) para que el navegador deje
  mandar el formulario.
- No hace falta el bucket: las versiones son links.
- Los permisos se siembran al migrar; el rol Administrador los recibe solo. Para otro rol
  del equipo se marcan en el portal ("Roles y permisos").
