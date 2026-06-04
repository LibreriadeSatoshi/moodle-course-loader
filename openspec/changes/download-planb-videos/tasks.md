## 1. Manifiesto

- [ ] 1.1 Definir el modelo del manifiesto (entrada por UUID Plan ₿: `peertube_id`, `lang`, `title`, `mp4`, `sha256`, `bytes`, `status`, `source_url`)
- [ ] 1.2 Cargar/crear el manifiesto YAML (default `video_manifest.yml`, override `--manifest`); rutas `mp4` relativas al manifiesto
- [ ] 1.3 Guardado atómico (escribir a temporal + rename) para no corromper el manifiesto si se interrumpe
- [ ] 1.4 Tests: round-trip de carga/guardado, manifiesto ausente → vacío

## 2. Cliente PeerTube

- [ ] 2.1 `get_video(peertube_id)` → `GET /api/v1/videos/<id>` (host `peertube.planb.network`), devolver `title` y `playlistUrl` (master HLS)
- [ ] 2.2 Error claro si el vídeo no existe / sin `streamingPlaylists`
- [ ] 2.3 Tests con HTTP mockeado (respuesta real de ejemplo)

## 3. Remux con ffmpeg

- [ ] 3.1 Comprobar `ffmpeg` en el `PATH` al inicio; abortar con mensaje claro si falta
- [ ] 3.2 `download_to_mp4(master_url, out_path)`: `ffmpeg -i <m3u8> -map 0:v:0 -map 0:a:0 -c copy -bsf:a aac_adtstoasc <out>.mp4`
- [ ] 3.3 Capturar fallo de `ffmpeg` (código ≠ 0) y propagarlo como error de vídeo
- [ ] 3.4 Tests: invocación de `ffmpeg` mockeada (subprocess), ruta de éxito y de fallo

## 4. Orquestación de descarga

- [ ] 4.1 Enumerar vídeos: escanear `course.yml` bajo `<courses_root>` (reutilizar `PlanBSource`/`_read_videos`), filtrar entradas con pista `peertube[en]`, deduplicar por UUID
- [ ] 4.2 Idempotencia: omitir si `status: downloaded` + `mp4` existe + `sha256` coincide; `--force` re-descarga; `--only <uuid> ...` limita el conjunto
- [ ] 4.3 Por vídeo: resolver master → remux a `<archive>/<uuid>.<lang>.mp4` → calcular `sha256`+`bytes` → actualizar manifiesto (`downloaded`)
- [ ] 4.4 Vídeo sin pista `en` → omitir con warning; fallo de red/ffmpeg → `status: failed` + warning, continuar
- [ ] 4.5 Resumen final (descargados / omitidos / fallidos); exit ≠ 0 si hubo `failed`

## 5. CLI

- [ ] 5.1 Comando `download-videos <courses_root> [--manifest PATH] [--archive-dir DIR] [--lang en] [--force] [--only <uuid> ...]`
- [ ] 5.2 `--lang` acepta sólo `en` en v1 (validar/avisar si se pide otro)
- [ ] 5.3 Salida de progreso por vídeo + tabla/resumen final

## 6. Tests de orquestación

- [ ] 6.1 Curso con un vídeo peertube `en` → descarga, MP4 y entrada de manifiesto creados
- [ ] 6.2 Segunda ejecución → omitido (sin invocar ffmpeg); con `--force` → re-descarga
- [ ] 6.3 Vídeo sólo-YouTube → ignorado (no entra al manifiesto)
- [ ] 6.4 Vídeo peertube sin pista `en` → omitido con warning
- [ ] 6.5 Fallo de ffmpeg → `status: failed`, lote continúa, exit ≠ 0
- [ ] 6.6 `--only` limita a los UUIDs indicados

## 7. Documentación

- [ ] 7.1 README: comando `download-videos`, requisito de `ffmpeg`, formato del manifiesto
- [ ] 7.2 README: aclarar que sólo descarga PeerTube en inglés; los vídeos YouTube no se tocan
