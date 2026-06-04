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

### 3. Descarga: API PeerTube → master HLS → `ffmpeg -c copy` → MP4

**Decisión**: Por vídeo: `GET /api/v1/videos/<peertube_id>` → tomar `streamingPlaylists[0].playlistUrl`. Invocar `ffmpeg -i <master.m3u8> -map 0:v:0 -map 0:a:0 -c copy -bsf:a aac_adtstoasc <out>.mp4` (remux sin recodificar; selecciona la mejor pista de vídeo/audio). Si el remux falla, registrar `failed` (no recodificar en v1).

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

## Risks / Trade-offs

- **Red y disponibilidad**: depende de la API PeerTube y del S3 de HLS en el momento de descarga. Reintentos simples; los fallos quedan como `failed` y se reintentan en la siguiente ejecución.
- **Almacenamiento**: vídeos de curso completos suman muchos GB. v1 sólo `en` para acotar; el operador asume el espacio.
- **Selección de resolución**: `ffmpeg` con master HLS elige según `-map`; podríamos no obtener siempre la máxima. Aceptable para v1; afinable con un selector de resolución futuro.
- **Cambios en el origen**: si PlanB recorta/actualiza un vídeo, el MP4 archivado queda desfasado hasta un `--force`. No hay sync incremental por contenido en v1.

## Open Questions

- ¿Resolución objetivo fija (p. ej. 720p) o siempre la máxima disponible? v1: máxima vía `-map 0:v:0`.
- ¿Guardar también subtítulos/capítulos de PeerTube? Fuera de v1.
