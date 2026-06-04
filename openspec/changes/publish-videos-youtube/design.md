## Context

El cambio `download-planb-videos` deja MP4 archivados y un manifiesto YAML indexado por UUID Plan ₿, con `peertube_id`, `lang`, `title`, `mp4`, `sha256`, `status: downloaded`, `source_url`. Este comando recorre ese manifiesto y publica los MP4 en una cuenta de YouTube como no listados, de modo que el importador (cambio futuro) pueda preferir el `youtube_id` propio sobre el `course.yml` de Plan ₿ y Moodle los embeba vía su filtro multimedia.

La subida usa la **YouTube Data API v3** (`videos.insert`, subida reanudable). Es una herramienta batch, ocasional, separada de `import-planb` y de la descarga.

## Goals / Non-Goals

**Goals:**
- Subir los MP4 archivados a una cuenta de YouTube como `unlisted`, con metadatos y atribución.
- Idempotencia: no re-subir lo ya subido (salvo `--force`).
- Reanudable y consciente de cuota: parar con gracia ante `quotaExceeded`, persistir progreso, continuar en la siguiente ejecución; `--limit` por ejecución.
- Registrar `youtube_id` ligado al UUID Plan ₿ en el manifiesto compartido.

**Non-Goals:**
- Descargar/transcodificar (cambio aparte).
- Idiomas ≠ `en`.
- Que el importador consuma el mapeo (cambio futuro).
- Gestionar playlists, miniaturas o capítulos en YouTube.

## Decisions

### 1. El manifiesto es la cola de trabajo y el registro de salida

**Decisión**: No hay estado aparte. `publish-videos` selecciona las entradas con `status: downloaded` y sin `youtube_id`. Al subir con éxito, **añade** `youtube_id`, `uploaded_at` y pone `status: uploaded`. Sólo toca campos de publicación; los de descarga son de `download-planb-videos`.

```yaml
58e578ef-…:
  # … campos de descarga (peertube_id, lang, title, mp4, sha256, status) …
  youtube_id: dQw4w9WgXcQ
  uploaded_at: 2026-06-04
  status: uploaded
```

**Razón**: Una sola fuente de verdad; idempotencia y reanudación salen gratis del propio manifiesto. Guardado atómico (igual que en la descarga) para no corromperlo a mitad de un lote.

### 2. Idempotencia y reanudación

**Decisión**: Se omiten entradas con `youtube_id` presente (salvo `--force`). El manifiesto se **guarda tras cada subida** (no al final), de modo que una interrupción no pierde lo ya subido ni provoca duplicados. `--limit N` corta tras N subidas en una ejecución.

**Razón**: Las subidas son caras (cuota) y lentas; guardar incrementalmente es lo único seguro.

**Riesgo asumido**: si el proceso muere entre que YouTube acepta la subida y el manifiesto se guarda, podría re-subirse (duplicado) en la siguiente ejecución. Ventana pequeña; mitigable a futuro consultando por título antes de subir.

### 3. Cuota: parada con gracia

**Decisión**: `videos.insert` cuesta ~1600 unidades; la cuota diaria por defecto es 10 000 → ~6 subidas/día. Ante un error `quotaExceeded` (HTTP 403, reason `quotaExceeded`/`uploadLimitExceeded`), el comando **se detiene con gracia**: registra cuántas subió, deja el resto pendiente y termina con un mensaje indicando reanudar más tarde. `--limit` permite autolimitarse por debajo de la cuota.

**Razón**: La cuota es el cuello de botella real; el flujo normal es "ejecutar a diario hasta vaciar el manifiesto".

### 4. Subida reanudable + metadatos

**Decisión**: `MediaFileUpload(resumable=True)` con reintentos. Snippet por defecto:
- `title`: el `title` del manifiesto (nombre del vídeo en PeerTube).
- `description`: atribución a Plan ₿ + `source_url` + nota de licencia CC BY-SA 4.0.
- `defaultLanguage`/`defaultAudioLanguage`: `en`.
- `status.privacyStatus`: `unlisted` (override con `--privacy`); `embeddable: true`.

**Razón**: No listado evita ruido en el canal y reduce exposición; embeddable explícito garantiza que Moodle pueda embeberlo.

### 5. Autenticación OAuth2

**Decisión**: OAuth2 de aplicación instalada con scope `https://www.googleapis.com/auth/youtube.upload`. `client_secret` y `token` (refrescable) vía fichero/entorno configurable (p. ej. `--client-secrets`, `--token`, o variables). El primer uso hace el flujo de consentimiento; después se refresca el token.

**Razón**: `videos.insert` requiere OAuth de usuario (no basta una API key). El token refrescable permite ejecuciones batch desatendidas tras el alta inicial.

**Requisito externo**: la cuenta/canal debe estar **verificada** para subir vídeos de más de 15 min (los de curso lo son) y para `embeddable`. Se documenta; el comando no puede sortearlo.

## Risks / Trade-offs

- **Cuota**: limita el ritmo a ~6/día sin ampliación. Mitigación: idempotencia + reanudación + `--limit`; opción de solicitar aumento de cuota a Google.
- **Content ID / strikes**: re-subir vídeos puede generar reclamaciones (música/clips de terceros) contra el canal. Riesgo operativo; fuera del control del comando.
- **Dependencia de tercero**: YouTube puede retirar vídeos o suspender el canal. Por eso los **MP4 archivados** (cambio de descarga) son la copia de preservación; YouTube es sólo la capa de entrega.
- **Ventana de duplicado** ante crash entre subida y guardado (ver Decisión 2).

## Open Questions

- ¿Plantilla exacta de `title`/`description`? Propuesto: título = nombre PeerTube; descripción = atribución + enlace + licencia. Ajustable.
- ¿`--limit` por defecto (p. ej. 6, acorde a cuota) o sin límite? Propuesto: sin límite, parando por `quotaExceeded`; `--limit` para control fino.
- ¿Verificar duplicados consultando el canal por título antes de subir? Fuera de v1 (cierra la ventana de la Decisión 2).
