## Context

Los `course.yml` de Plan ₿ mapean cada UUID de vídeo a proveedores (`youtube`/`peertube`) y, por proveedor, a `{idioma → id}`. El parser ya expone esto en `PlanBCourseSpec.videos` (cambio `embed-planb-videos`). Los vídeos PeerTube viven en `peertube.planb.network`; su API (`/api/v1/videos/<id>`) devuelve `streamingPlaylists[0].playlistUrl` (master HLS `.m3u8`) y, por resolución, ficheros HLS fragmentados (no hay MP4 progresivo: `files: []`). Las fragmentaciones HLS son H.264/AAC, así que se pueden **remuxar** a un MP4 sin recodificar.

Este comando es una herramienta batch ocasional, independiente de `import-planb`. Produce dos artefactos: los **MP4 archivados** (preservación) y un **manifiesto** que es la única fuente de verdad del estado (qué se descargó, dónde, con qué checksum) y que el comando de publicación ampliará después.

## Goals / Non-Goals

**Goals:**
- Descargar todos los vídeos PeerTube (idioma `en`) referenciados por los `course.yml` bajo una raíz, como MP4.
- Idempotencia: no volver a descargar lo ya descargado salvo `--force`.
- Registrar todo en un manifiesto YAML indexado por UUID Plan ₿.
- Tolerar fallos por vídeo sin abortar el lote (estado `failed`, resumen final).

**Non-Goals:**
- Idiomas ≠ `en` (manifiesto preparado para extender por `(uuid, lang)`).
- Publicar a YouTube/cuenta externa (cambio aparte).
- Recodificar/normalizar resoluciones más allá de elegir una pista.
- Que el importador consuma el manifiesto (cambio futuro).

## Decisions

### 1. Manifiesto compartido, indexado por UUID Plan ₿

**Decisión**: Un único fichero YAML (default `video_manifest.yml`, configurable con `--manifest`), indexado por el UUID Plan ₿ (la clave de `:::video id=UUID:::`). Por entrada, este comando escribe:

```yaml
58e578ef-…:
  peertube_id: iNpp837YB47E9KCjJgXWoa   # id del proveedor (de course.yml)
  lang: en
  title: "[BTC 102] - 1.1 - Course overview"   # nombre del vídeo (de la API)
  mp4: archive/58e578ef.en.mp4          # ruta relativa al fichero archivado
  sha256: "…"
  bytes: 123456789
  status: downloaded                    # downloaded | failed
  source_url: https://peertube.planb.network/w/iNpp837YB47E9KCjJgXWoa
```

**Razón**: El UUID Plan ₿ es lo que liga la descarga, la futura publicación (`youtube_id`) y el override del importador. Guardar `peertube_id` aparte permite descargar; guardar `title`/`source_url` evita re-consultar la API en la publicación. El manifiesto es la unidad de idempotencia y de reanudación.

**Nota de propiedad del esquema**: este cambio **crea** el manifiesto y posee los campos de descarga. El cambio `publish-videos-youtube` sólo **añade** `youtube_id`/`uploaded_at`; no debe redefinir los campos de descarga.

### 2. Enumeración de vídeos desde `course.yml`

**Decisión**: Reutilizar `PlanBSource` / `_read_videos` para parsear cada `course.yml` bajo `<courses_root>` y quedarse con las entradas cuyo `peertube` tenga pista `en`. Vídeos sólo-YouTube se ignoran (ya embeben en Moodle). Deduplicar por UUID.

**Razón**: La fuente de verdad ya está parseada; no reimplementar el escaneo.

### 3. Descarga: API PeerTube → mejor variante HLS → `ffmpeg -c copy` → MP4

**Decisión**: Por vídeo: `GET /api/v1/videos/<peertube_id>` → tomar el master HLS (`streamingPlaylists[0].playlistUrl`). **Parsear el master y elegir la variante de mayor resolución** (PeerTube las lista ascendente —144p→240p→360p—, así que la "primera" de ffmpeg sería la *más baja*). Pasar la media playlist de esa variante a `ffmpeg -fflags +bitexact -i <variant.m3u8> -map 0:v:0 -map 0:a:0 -c copy -bsf:a aac_adtstoasc -flags +bitexact -map_metadata -1 <out>.mp4` (remux sin recodificar). Los flags `+bitexact` y `-map_metadata -1` hacen la salida **reproducible byte a byte**: sin tag de encoder ni timestamps de creación en el contenedor, así el `sha256` del manifiesto es portable entre máquinas (con la misma versión de ffmpeg). Sin ellos, el bitstream es idéntico pero el contenedor MP4 difiere por versión/hora. La altura elegida se guarda en el manifiesto (`resolution`, p. ej. `360p`). Si el remux falla, registrar `failed`.

**Razón**: Remux es rápido y sin pérdida. `ffmpeg` resuelve HLS, segmentos fragmentados y el `aac_adtstoasc` necesario para AAC en MP4.

**Alternativa descartada**: descargar segmentos a mano y concatenar — `ffmpeg` ya lo hace de forma robusta.

**Dependencia**: `ffmpeg` debe estar en el `PATH`. Si falta, el comando aborta con un mensaje claro antes de empezar.

### 4. Idempotencia e integridad

**Decisión**: Antes de descargar un vídeo, si el manifiesto tiene `status: downloaded` con `mp4` existente en disco y `sha256` coincide, se omite. `--force` re-descarga (sobrescribe). `--only <uuid>` limita a vídeos concretos. Tras descargar, calcular y guardar `sha256` + `bytes`.

**Razón**: Re-ejecuciones baratas y seguras; el checksum detecta archivos truncados/corruptos.

### 5. Layout del archivo

**Decisión**: Default `--archive-dir videos/` con ficheros `archive/<uuid>.<lang>.mp4` (plano por UUID+idioma; el UUID es único). Rutas en el manifiesto **relativas** al manifiesto para portabilidad.

### 6. Manejo de errores por vídeo

**Decisión**: Un vídeo sin pista `en`, o cuyo `GET`/`ffmpeg` falle, se marca `failed` (con motivo logueado) y el lote continúa. El comando termina con código ≠ 0 si hubo algún `failed`, e imprime un resumen (descargados / omitidos / fallidos).

### 7. Fichero de metadatos sidecar por vídeo

**Decisión**: Junto a cada MP4 se escribe `<archive-dir>/<uuid>.yml` con los metadatos del vídeo (título, descripción completa, licencia, idioma, categoría, tags, canal, duración, URL/uuid de PeerTube, resolución, fecha de publicación). Todos los datos vienen del objeto de vídeo de la API (`GET /api/v1/videos/<id>`): su campo `description` ya es el texto completo (1246 chars en el ejemplo; `truncatedDescription` es la versión corta de 250 y no se usa), así que no hace falta el endpoint `/description`. Se escribe en la descarga y se sobrescribe con `--force`; una omisión idempotente no lo reescribe.

**Razón**: Un sidecar legible hace que el MP4 archivado sea autodescriptivo (preservación) y aporta los textos que el paso de publicación reutilizará (título/descripción/atribución de licencia). YAML por coherencia con el manifiesto.

**Alternativa descartada**: meter todos los metadatos dentro del manifiesto. Lo infla y mezcla el estado de descarga (que el publish amplía) con metadatos de contenido inmutables; un fichero por vídeo es más limpio y portable junto al MP4.

## Risks / Trade-offs

- **Red y disponibilidad**: depende de la API PeerTube y del S3 de HLS en el momento de descarga. Reintentos simples; los fallos quedan como `failed` y se reintentan en la siguiente ejecución.
- **Almacenamiento**: vídeos de curso completos suman muchos GB. v1 sólo `en` para acotar; el operador asume el espacio.
- **Selección de resolución**: resuelto parseando el master y eligiendo la variante de mayor área de píxeles (ver Decisión 3). Nota: la "nativa" es la máxima que PlanB codificó; algunos vídeos sólo llegan a 360p y eso es lo esperado, no un fallo.
- **Cambios en el origen**: si PlanB recorta/actualiza un vídeo, el MP4 archivado queda desfasado hasta un `--force`. No hay sync incremental por contenido en v1.

## Open Questions

- ~~¿Resolución objetivo fija (p. ej. 720p) o siempre la máxima disponible?~~ Resuelto: siempre la máxima, parseando las variantes del master HLS.
- ¿Guardar también subtítulos/capítulos de PeerTube? Fuera de v1.
- Nombre del sidecar: se usa `{uuid}.yml` (lo pedido), pero el MP4 es `{uuid}.{lang}.mp4`. Si en el futuro se descargan varios idiomas, habría que pasar a `{uuid}.{lang}.yml` para no colisionar. v1 (sólo `en`): `{uuid}.yml`.
