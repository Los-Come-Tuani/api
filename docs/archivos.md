---
icon: lucide/file-up
---

# Archivos

Cómo se suben los documentos legales y las fotos de las solicitudes, y qué hay que
crear en el almacenamiento para que funcione. El API **nunca recibe el archivo**: le da
al cliente una URL firmada y el cliente lo sube directo a un bucket compatible con S3
(Cloudflare R2, AWS S3, MinIO).

## Cómo funciona

1. El cliente pide `POST /upload/` con `{ "kind", "content_type", "size" }`. La ruta es
   pública (quien se postula sube sus documentos antes de tener cuenta) y tiene el
   límite estricto de peticiones.
2. El API valida el tipo y el tamaño que admite esa clase de archivo y responde `201`
   con `{ "key", "url", "method", "headers", "expires_in", "max_bytes" }`.
3. El cliente sube con un `PUT` a `url`, con las `headers` tal cual (el `Content-Type`
   que declaró) y el archivo como cuerpo. El tipo y el peso van dentro de la firma: el
   bucket rechaza el `PUT` si el archivo no es del tipo ni del tamaño con que se pidió la
   URL (`403 SignatureDoesNotMatch`). Es un `PUT` y no un formulario `POST` porque R2 no
   admite los formularios firmados; el `PUT` firmado funciona igual en S3, R2 y MinIO.
4. Al mandar la solicitud, el cliente referencia el archivo por su `key`. El API
   comprueba que esa clave sea de la clase correcta y que el archivo ya esté en el
   bucket con el tipo y el tamaño permitidos. Con una clave inventada responde `400`.

| `kind`                 | Tipos admitidos                         | Máximo |
| ---------------------- | --------------------------------------- | ------ |
| `legal-document`       | PDF, JPEG, PNG                          | 10 MB  |
| `signature-dish-photo` | JPEG, PNG, WebP                         | 5 MB   |
| `provider-document`    | PDF, JPEG, PNG                          | 10 MB  |
| `provider-photo`       | JPEG, PNG, WebP                         | 5 MB   |

La URL firmada vive diez minutos (`STORAGE_UPLOAD_EXPIRES`) y sirve solo para esa clave.
Para ver un archivo (el equipo que revisa una solicitud) el API firma una URL de lectura
de cinco minutos (`STORAGE_DOWNLOAD_EXPIRES`); el bucket es **privado**.

Sin bucket configurado, `POST /upload/` responde `503` con
`"El almacenamiento de archivos no está configurado."`.

## Variables

| Variable                    | Qué es                                                              |
| --------------------------- | ------------------------------------------------------------------- |
| `STORAGE_BUCKET`            | Nombre del bucket                                                   |
| `STORAGE_ACCESS_KEY_ID`     | Identificador de la clave de acceso (secreto)                       |
| `STORAGE_SECRET_ACCESS_KEY` | Secreto de la clave de acceso (secreto)                             |
| `STORAGE_ENDPOINT_URL`      | URL del servicio. R2: la de la cuenta. Vacía: AWS                   |
| `STORAGE_REGION`            | `auto` en R2; la región real (`us-east-1`...) en AWS                |

Las tres primeras van juntas o ninguna: con alguna a medias el API no arranca y dice cuál
falta. Con `DEPLOY=True` el endpoint tiene que ser `https`. Los valores reales viven solo
en las variables del servicio (Railway) y en el `.env` local, que está ignorado; nunca en
git.

## Crear el bucket en Cloudflare R2

1. En Cloudflare, **R2 → Create bucket**. Un bucket por entorno (`kplan-dev`,
   `kplan-prod`), **sin** acceso público.
2. **R2 → Manage API tokens → Create API token** con permiso _Object Read & Write_ y
   limitado a ese bucket. Copia el _Access Key ID_ y el _Secret Access Key_ (solo se ven
   una vez) y la URL del servicio (`https://<cuenta>.r2.cloudflarestorage.com`).
3. Pon las variables del bucket en el servicio del API.
4. **CORS** del bucket (Settings → CORS policy), para que el navegador pueda subir desde
   el portal. Sustituye los orígenes por los reales:

   ```json
   [
     {
       "AllowedOrigins": ["https://portal.kplan.example"],
       "AllowedMethods": ["PUT"],
       "AllowedHeaders": ["Content-Type"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```

   En desarrollo agrega `http://localhost:5173`. La app móvil no necesita CORS.
5. Opcional: una regla de ciclo de vida que borre los objetos sin referencia. Hoy quien
   se postula puede subir un archivo y abandonar la solicitud, y el objeto queda en el
   bucket; limpiarlos es un trabajo programado pendiente (ver la hoja de ruta).

### AWS S3 o MinIO

Mismo esquema: bucket privado, clave con permiso de lectura y escritura sobre él, CORS
con `PUT` y, en MinIO, `STORAGE_ENDPOINT_URL` apuntando al servidor (en desarrollo
admite `http://localhost:9000`).

## Riesgos conocidos

- La ruta `POST /upload/` es pública: un tercero puede pedir URLs firmadas y llenar el
  bucket. Lo acotan el límite de 10 peticiones por minuto, los tipos y tamaños de cada
  clase y la vigencia de la URL; no el contenido. Antes de abrir el registro al público
  conviene revisar el contenido de lo subido (antivirus) y limpiar lo que nadie reclama.
- El tipo de archivo lo declara el cliente y lo hace cumplir el bucket por el
  `Content-Type` firmado; no se inspecciona el contenido real.
