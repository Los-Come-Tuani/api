---
icon: lucide/log-in
---

# Inicio de sesión con Google

Guía para dejar funcionando "Continuar con Google" en la app y en el portal. El API
**no necesita ningún secreto de Google**: valida el token de identidad
con las llaves públicas de Google y comprueba que fue emitido para alguno de tus
Client ID. Los Client ID son públicos, pero las credenciales que Google te deja
descargar sí se tratan como secretas (ver [Qué no se versiona](#que-no-se-versiona)).

## Identificadores definitivos

Los Client ID de Android y de iOS quedan atados a identificadores de la app. K'Plan usa:

- **Android**: `dev.kplan.app`, y la huella SHA-1 de
  cada llave de firma (depuración, subida y la de Play App Signing).
- **iOS**: `dev.kplan.app`; su configuración de Google queda pendiente hasta trabajar
  la publicación para iPhone.

La SHA-1 de depuración se obtiene con:

```bash
keytool -list -v -alias androiddebugkey \
  -keystore ~/.android/debug.keystore -storepass android -keypass android
```

La de Play App Signing aparece en Play Console, en _Integridad de la app_.

## 1. Proyecto y pantalla de consentimiento

1. En [Google Cloud Console](https://console.cloud.google.com/) crea un proyecto
   (p. ej. `kplan`).
2. Abre **Google Auth Platform** (antes _Pantalla de consentimiento de OAuth_) y
   configura la **marca**: nombre de la app, correo de soporte, logo, dominio y los
   enlaces a la política de privacidad y a los términos.
3. En **Público**, elige _Externo_. Mientras el estado sea _En pruebas_ solo pueden
   entrar los correos que agregues como usuarios de prueba (hasta 100). Para abrirlo a
   todos, pasa a _En producción_.
4. En **Acceso a los datos** basta con `openid`, `email` y `profile`: no son alcances
   sensibles y no requieren la revisión extra de Google.

## 2. Client ID

En **Clientes** crea uno de cada tipo que vayas a usar:

| Tipo        | Datos que pide                                             | Para qué sirve                                                              |
| ----------- | ---------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Web**     | Orígenes de JavaScript autorizados (portal)                | Es el `aud` del token: lo validan el API, el portal y la app como `serverClientId` |
| **Android** | Nombre del paquete y SHA-1 (uno por llave de firma)        | Google comprueba que la firma de la app es la registrada                   |
| **iOS**     | _Bundle ID_                                                | Es el `GIDClientID` de la app en iOS                                        |

Para el Client ID Web, agrega como orígenes autorizados `http://localhost:5173` (portal
en desarrollo) y el origen del portal en producción cuando exista.

## 3. API

Una variable de entorno, sin secretos:

```bash
# uno o varios Client ID Web, separados por comas
GOOGLE_OAUTH_CLIENT_IDS="123456789-abc.apps.googleusercontent.com"
```

Vacía, el inicio de sesión con Google queda deshabilitado (`404`). En producción se
define como variable del servicio.

Rutas: `POST /auth/mobile/google/` y `POST /auth/web/google/` (esta última con la
cabecera CSRF y cookies, igual que el inicio de sesión del portal).

En la app móvil, el cuerpo es:

```json
{ "id_token": "<JWT de Google>", "birth_date": "1990-05-17", "nationality": "NI" }
```

- Si la persona ya entró con Google antes, se identifica por el `sub` del token y basta
  con `id_token`.
- Si no existe una cuenta con ese correo, hay que mandar también `birth_date` (mayor de
  18 años) y `nationality`, que Google no entrega. Sin ellos la respuesta es `400` con
  `body.birth_date` y `body.nationality` en `field_errors`: la app muestra el paso
  "completa tu perfil" y reintenta **con el mismo token**.
- Si existe una cuenta con ese correo, se **vincula** solo cuando su correo ya estaba
  verificado. Una cuenta sin verificar da `403`: de lo contrario, quien la creó con una
  contraseña propia se quedaría con la cuenta de quien entra con Google.
- En móvil solo entran turistas, guías y traductores.
- La respuesta es la misma del inicio de sesión: `200` con la sesión, o `202` con el
  reto si la cuenta tiene 2FA.

En el portal el cuerpo lleva solo `{ "id_token": "<JWT de Google>" }`. Google no crea
cuentas desde ahí: el negocio, la alcaldía o la institución primero completa su
postulación, y el equipo primero acepta su invitación. Después Google puede enlazar esa
cuenta existente, activa y con correo verificado. Una cuenta de la app o un correo que
todavía no tiene cuenta de portal recibe `403`. El segundo factor sigue aplicándose.

## 4. App (Flutter)

El paquete es [`google_sign_in`](https://pub.dev/packages/google_sign_in) (7.x). Los
Client ID se compilan en la app con `--dart-define-from-file` (`env/dev.json`...):

```json
{
  "API_BASE_URL": "http://10.0.2.2:8080",
  "GOOGLE_SERVER_CLIENT_ID": "123456789-abc.apps.googleusercontent.com",
  "GOOGLE_IOS_CLIENT_ID": "123456789-def.apps.googleusercontent.com"
}
```

- **Android**: no hace falta `google-services.json`; basta pasar el Client ID Web como
  `serverClientId`. Si "Continuar con Google" se cancela solo después de elegir la
  cuenta, casi siempre falta la SHA-1 de esa llave de firma o el nombre del paquete no
  coincide.
- **iOS**: en `ios/Runner/Info.plist` hay que registrar el _esquema de URL_ con el
  Client ID de iOS **invertido** (`com.googleusercontent.apps.123456789-def`), dentro de
  `CFBundleURLTypes`. El resto (`clientId` y `serverClientId`) se pasa en Dart.
- Si no hay `GOOGLE_SERVER_CLIENT_ID`, la app oculta el botón.
- **App Store**: Apple exige ofrecer también "Iniciar sesión con Apple" (u otra opción
  con las mismas garantías de privacidad) a las apps que incluyen Google. Hay que
  resolverlo antes de publicar en iOS.

## 5. Portal

El portal usa Google Identity Services con el Client ID Web. El botón oficial entrega
`credential`, que se manda como `id_token` a `POST /auth/web/google/`. La variable pública
del build es:

```bash
VITE_GOOGLE_CLIENT_ID="123456789-abc.apps.googleusercontent.com"
```

En desarrollo el origen autorizado es `http://localhost:5173`. Cuando exista el dominio
de producción hay que agregar su origen exacto al mismo Client ID.

## Firebase

Firebase, `google-services.json` y una cuenta de servicio no se usan para este inicio de
sesión. El cliente Android se registra directamente en Google Auth Platform con
`dev.kplan.app` y la SHA-1 de cada firma.

## Qué no se versiona

- **Sí es seguro versionar**: los Client ID (son públicos) en los archivos
  `env/*.example.json` y `.env.example`, con valores de ejemplo.
- **Nunca se versiona**: `client_secret*.json` (la descarga de un Client ID trae un
  secreto), `google-services.json`, `GoogleService-Info.plist`, llaves `*.jks` /
  `*.keystore` / `key.properties` y las cuentas de servicio. Los tres repositorios ya
  los ignoran en su `.gitignore`.
- El API **no usa** el secreto del Client ID: si Google te ofrece descargarlo, no lo
  necesitas. Solo haría falta con el flujo de código de autorización, que aquí no se usa.
