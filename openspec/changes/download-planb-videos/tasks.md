## 1. Manifiesto

- [x] 1.1 Definir el modelo del manifiesto (entrada por UUID Plan ₿: `peertube_id`, `lang`, `title`, `mp4`, `sha256`, `bytes`, `status`, `source_url`)
- [x] 1.2 Cargar/crear el manifiesto YAML (default `video_manifest.yml`, override `--manifest`); rutas `mp4` relativas al manifiesto
- [x] 1.3 Guardado atómico (escribir a temporal + rename) para no corromper el manifiesto si se interrumpe
- [x] 1.4 Tests: round-trip de carga/guardado, manifiesto ausente → vacío

## 2. Cliente PeerTube

- [x] 2.1 `get_video(peertube_id)` → `GET /api/v1/videos/<id>` (host `peertube.planb.network`), devolver `title` y `playlistUrl` (master HLS)
- [x] 2.2 Error claro si el vídeo no existe / sin `streamingPlaylists`
- [x] 2.3 Tests con HTTP mockeado (respuesta real de ejemplo)

## 3. Remux con ffmpeg

- [x] 3.1 `check_ffmpeg()`: comprobar `ffmpeg` en el `PATH` (la invocación al inicio del comando es tarea de CLI, 5.x)
- [x] 3.2 `remux_to_mp4(master_url, out_path)`: `ffmpeg -i <m3u8> -map 0:v:0 -map 0:a:0 -c copy -bsf:a aac_adtstoasc <out>.mp4`
- [x] 3.2b Seleccionar la variante de **mayor resolución** del master (`_select_best_variant`): parsear `RESOLUTION=<w>x<h>`, elegir máxima área, resolver URI relativa; registrar `resolution` en el manifiesto. Tests unitarios + cliente (variantes ascendentes → se elige la mayor)
- [x] 3.3 Capturar fallo de `ffmpeg` (código ≠ 0) y propagarlo como `FfmpegError`
- [x] 3.4 Tests: invocación de `ffmpeg` mockeada (subprocess), ruta de éxito y de fallo

## 4. Orquestación de descarga

- [x] 4.1 Enumerar vídeos: escanear `course.yml` bajo `<courses_root>` (reutiliza `_read_videos`), filtrar entradas con pista `peertube[en]`, deduplicar por UUID
- [x] 4.2 Idempotencia: omitir si `status: downloaded` + `mp4` existe + `sha256` coincide; `--force` re-descarga; `--only <uuid> ...` limita el conjunto
- [x] 4.3 Por vídeo: resolver master → remux a `<archive>/<uuid>.<lang>.mp4` → calcular `sha256`+`bytes` → actualizar manifiesto (`downloaded`)
- [x] 4.4 Fallo de red/ffmpeg → `status: failed` + warning, continuar; vídeo sin pista `en` no se enumera
- [x] 4.5 `DownloadResult` (descargados / omitidos / fallidos). NOTA: imprimir el resumen y `exit ≠ 0` si hubo `failed` es tarea de CLI (5.x)

## 5. CLI

- [x] 5.1 Comando `download-videos <courses_root> [--manifest PATH] [--archive-dir DIR] [--lang en] [--force] [--only <uuid> ...]`
- [x] 5.2 `--lang` acepta sólo `en` en v1 (validar/avisar si se pide otro); `check_ffmpeg()` al inicio
- [x] 5.3 Tabla/resumen final (descargados/omitidos/fallidos); exit ≠ 0 si hubo `failed`

## 6. Tests de orquestación

- [x] 6.1 Curso con un vídeo peertube `en` → descarga, MP4 y entrada de manifiesto creados
- [x] 6.2 Segunda ejecución → omitido (sin invocar ffmpeg); con `--force` → re-descarga
- [x] 6.3 Vídeo sólo-YouTube → ignorado (no entra al manifiesto)
- [x] 6.4 Vídeo peertube sin pista `en` → omitido (no se enumera)
- [x] 6.5 Fallo de ffmpeg → `status: failed`, lote continúa; exit ≠ 0 a nivel CLI
- [x] 6.6 `--only` limita a los UUIDs indicados
- [x] 6.7 Tests de CLI (validación de args, pre-check de ffmpeg, resumen, exit codes) en `test_cli_download_videos.py`

## 8. Fichero de metadatos por vídeo

- [x] 8.1 Extender el cliente PeerTube para devolver metadatos del objeto de vídeo: `description` (campo `description`, ya completo), `license` (`licence.label`), `language` (`language.label`), `category` (`category.label`), `tags`, `channel` (`channel.displayName`), `duration`, `published_at` (`publishedAt`)
- [x] 8.2 Escribir `<archive-dir>/<uuid>.yml` por vídeo descargado con esos campos + `peertube_id`, `source_url`, `resolution`
- [x] 8.3 Sobrescribir con `--force`; no reescribir en omisión idempotente (la omisión no entra al bloque de descarga)
- [ ] 8.4 (opcional) Registrar la ruta del fichero de metadatos en el manifiesto — no implementado (la ruta es derivable: `<archive>/<uuid>.yml`)
- [x] 8.5 Tests: metadatos creados junto al MP4 (title/description/license); `--force` regenera; omisión no reescribe (mtime); `get_video` puebla metadatos; `build_metadata`/`write_metadata`

## 7. Documentación

- [x] 7.1 README: comando `download-videos`, requisito de `ffmpeg`, formato del manifiesto
- [x] 7.2 README: aclarar que sólo descarga PeerTube en inglés; los vídeos YouTube no se tocan
