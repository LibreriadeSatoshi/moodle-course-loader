## Why

Los vídeos de los cursos Plan ₿ alojados en PeerTube (`peertube.planb.network`) no se pueden embeber en Moodle: su `<iframe>` lo elimina el HTMLPurifier de Moodle al renderizar (ver el cambio `embed-planb-videos`), y la instancia sólo sirve HLS (sin MP4 progresivo) con CORS cerrado para dominios externos, así que tampoco hay reproducción cliente. La estrategia acordada es **re-alojar** los vídeos: para ello primero hay que **descargarlos y archivarlos** como MP4. Esos MP4 son además el artefacto de **preservación** del contenido (tenemos permiso explícito del titular para copiarlos; el repositorio es CC BY-SA 4.0).

Este cambio cubre sólo la **descarga**. La publicación a una cuenta de vídeo y el consumo del mapeo desde el importador son cambios separados.

## What Changes

- Nuevo comando CLI `moodle-loader download-videos <courses_root> [--manifest PATH] [--archive-dir DIR] [--lang en] [--force] [--only <uuid> ...]`.
- Escanea cada `course.yml` bajo `<courses_root>` buscando entradas `videos:` con pista `peertube` en el idioma objetivo (sólo `en` en v1).
- Para cada vídeo: resuelve el master HLS (`.m3u8`) vía la API de PeerTube (`/api/v1/videos/<id>`), descarga y **remuxa a MP4** con `ffmpeg` (sin recodificar), lo guarda en el directorio de archivo y registra la entrada en un **manifiesto** compartido (YAML), indexado por el UUID Plan ₿ del vídeo.
- **Idempotente**: un vídeo ya descargado (manifiesto con `mp4` + `sha256` y fichero presente en disco) se omite, salvo `--force`.
- `ffmpeg` pasa a ser una dependencia externa del runtime (no de Python).

Fuera de alcance: idiomas distintos de inglés (la estructura del manifiesto los contempla para el futuro), publicación a YouTube/cuenta externa (cambio `publish-videos-youtube`), y el uso del manifiesto como override en el importador (cambio futuro). Vídeos sólo en YouTube en `course.yml` no se tocan (ya embeben vía el filtro multimedia de Moodle).

## Capabilities

### New Capabilities

- `video-download`: descarga y archiva como MP4 los vídeos PeerTube referenciados por los `course.yml` de Plan ₿, de forma idempotente, y los registra en un manifiesto compartido indexado por UUID Plan ₿.

## Impact

- **`src/moodle_loader/cli.py`**: nuevo comando `download-videos`.
- **`src/moodle_loader/videos/` (nuevo paquete)**: cliente de la API PeerTube (resolución del master HLS), invocación de `ffmpeg` (remux HLS→MP4), lectura/escritura del manifiesto, orquestación de descarga idempotente.
- **Reutiliza** el escaneo de `videos:` de `course.yml` ya implementado en `planb_source.py` (`_read_videos` / `PlanBCourseSpec.videos`) para enumerar los vídeos.
- **`pyproject.toml`**: sin nuevas deps Python obligatorias (PyYAML ya disponible); documentar `ffmpeg` como requisito del sistema.
- **README**: sección sobre el comando y el requisito de `ffmpeg`.
- **Tests**: escaneo, idempotencia (skip vs `--force`), manejo de pista de idioma ausente, fallo de `ffmpeg`/red registrado como `failed`; API PeerTube y `ffmpeg` mockeados.
- **Riesgo**: descarga depende de red (API PeerTube + S3). Volúmenes grandes de almacenamiento; en v1 sólo `en` para acotarlo.
