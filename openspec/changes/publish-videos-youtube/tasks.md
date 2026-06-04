## 1. Dependencias y autenticación

- [ ] 1.1 Añadir `google-api-python-client`, `google-auth`, `google-auth-oauthlib` a `pyproject.toml`
- [ ] 1.2 Flujo OAuth2 (scope `youtube.upload`): cargar `client_secrets` + `token` refrescable; primer uso = consentimiento, después refresco silencioso
- [ ] 1.3 Configuración de rutas de credenciales (flags/entorno) y mensaje claro si faltan
- [ ] 1.4 Tests: refresco de token y manejo de credenciales ausentes (mock)

## 2. Cliente YouTube

- [ ] 2.1 `upload_video(mp4_path, *, title, description, language, privacy, embeddable)` con `videos.insert` y `MediaFileUpload(resumable=True)`
- [ ] 2.2 Devolver el `youtube_id` del recurso creado
- [ ] 2.3 Detectar `quotaExceeded`/`uploadLimitExceeded` (HTTP 403) y exponerlo como excepción tipada
- [ ] 2.4 Reintentos en errores reanudables transitorios
- [ ] 2.5 Tests con la API mockeada: subida correcta → id; error de cuota → excepción tipada

## 3. Manifiesto (campos de publicación)

- [ ] 3.1 Reutilizar el cargador/guardador atómico del manifiesto (de `download-planb-videos`)
- [ ] 3.2 Seleccionar entradas `status: downloaded` y sin `youtube_id`
- [ ] 3.3 Tras cada subida: escribir `youtube_id`, `uploaded_at`, `status: uploaded` y **guardar inmediatamente**
- [ ] 3.4 Tests: selección de pendientes, persistencia incremental

## 4. Orquestación de publicación

- [ ] 4.1 Recorrer pendientes; construir snippet (título = `title` del manifiesto; descripción = atribución Plan ₿ + `source_url` + licencia CC BY-SA; idioma `en`; `unlisted`; `embeddable`)
- [ ] 4.2 Idempotencia: omitir entradas con `youtube_id` salvo `--force`
- [ ] 4.3 `--limit N`: parar tras N subidas
- [ ] 4.4 Parada con gracia ante `quotaExceeded`: persistir progreso, resumen, mensaje de reanudar
- [ ] 4.5 Validar que el `mp4` existe antes de subir (si falta → `failed`/aviso, no abortar el lote)
- [ ] 4.6 Resumen final (subidos / omitidos / pendientes por cuota / fallidos)

## 5. CLI

- [ ] 5.1 Comando `publish-videos [--manifest PATH] [--limit N] [--privacy unlisted] [--force] [--client-secrets PATH] [--token PATH]`
- [ ] 5.2 Salida de progreso por vídeo + resumen final

## 6. Tests de orquestación

- [ ] 6.1 Entrada descargada sin `youtube_id` → se sube y se registra `youtube_id`/`uploaded_at`/`uploaded`
- [ ] 6.2 Entrada con `youtube_id` → omitida; con `--force` → re-subida
- [ ] 6.3 `--limit 1` con varias pendientes → sube una, deja el resto
- [ ] 6.4 `quotaExceeded` a mitad de lote → para con gracia, lo ya subido queda persistido, exit informativo
- [ ] 6.5 `mp4` ausente en disco → entrada marcada/avisada, lote continúa
- [ ] 6.6 Manifiesto inexistente o sin pendientes → no-op con mensaje

## 7. Documentación

- [ ] 7.1 README: comando `publish-videos`, alta OAuth en Google Cloud, scopes y rutas de credenciales
- [ ] 7.2 README: cuota (~6/día), reanudación, y requisito de **cuenta verificada** (>15 min y embeddable)
