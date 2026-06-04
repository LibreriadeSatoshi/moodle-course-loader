## Why

Tras descargar y archivar los vídeos PeerTube como MP4 (cambio `download-planb-videos`), hay que **re-alojarlos** en una cuenta de vídeo propia para poder embeberlos en Moodle de forma trivial: Moodle embebe automáticamente un enlace de YouTube vía su filtro multimedia (sin plugin, sin whitelist, sin CORS), mientras que el `<iframe>` de PeerTube lo elimina el purificador. Tenemos permiso explícito del titular para re-publicar (contenido CC BY-SA 4.0).

Este cambio cubre sólo la **publicación**: subir los MP4 a YouTube como **no listados** y registrar el id de YouTube resultante en el manifiesto, ligado al UUID Plan ₿. La descarga y el consumo del mapeo por el importador son cambios separados.

## What Changes

- Nuevo comando CLI `moodle-loader publish-videos [--manifest PATH] [--limit N] [--privacy unlisted] [--force]`.
- Lee el manifiesto compartido; para cada entrada **descargada pero aún no publicada** (sin `youtube_id`), sube su MP4 a YouTube vía la Data API v3 (subida reanudable), con `privacy=unlisted`, título/descripción con atribución a Plan ₿ y enlace al original, e idioma por defecto `en`.
- Registra `youtube_id` + `uploaded_at` + `status: uploaded` en el manifiesto.
- **Idempotente**: entradas con `youtube_id` se omiten salvo `--force`.
- **Consciente de cuota y reanudable**: `--limit` acota subidas por ejecución; ante `quotaExceeded` se detiene con gracia dejando el progreso persistido; re-ejecutar continúa donde se quedó.
- Autenticación OAuth2 a la cuenta de destino (client secrets + token refrescable) vía configuración/entorno.

Fuera de alcance: descarga/transcodificado (cambio `download-planb-videos`), idiomas ≠ `en`, proveedores distintos de YouTube, y el consumo del manifiesto como override en el importador (cambio futuro).

## Capabilities

### New Capabilities

- `video-publish`: publica en una cuenta de YouTube (no listado) los MP4 archivados del manifiesto, de forma idempotente, reanudable y consciente de cuota, y registra el `youtube_id` ligado al UUID Plan ₿.

## Impact

- **`src/moodle_loader/cli.py`**: nuevo comando `publish-videos`.
- **`src/moodle_loader/videos/` (paquete compartido con la descarga)**: cliente YouTube Data API (OAuth2 + subida reanudable), lectura/actualización del manifiesto (sólo campos de publicación), orquestación idempotente/reanudable.
- **`pyproject.toml`**: nuevas deps Python `google-api-python-client`, `google-auth`, `google-auth-oauthlib`.
- **Configuración**: credenciales OAuth de la cuenta (client secret + token); documentar el alta de la app en Google Cloud y los scopes (`youtube.upload`).
- **README**: comando, autenticación, cuota y requisito de **cuenta verificada** (subidas > 15 min y `embeddable`).
- **Tests**: idempotencia (skip con `youtube_id`, `--force`), `--limit`, parada por `quotaExceeded`, mapeo escrito; API YouTube mockeada.
- **Riesgos**: cuota de la Data API (~1600 u/subida, ~6/día por defecto); posibles reclamaciones de Content ID; dependencia de un tercero (los MP4 archivados siguen siendo la copia de preservación). La compatibilidad de licencia está cubierta por permiso explícito del titular.
