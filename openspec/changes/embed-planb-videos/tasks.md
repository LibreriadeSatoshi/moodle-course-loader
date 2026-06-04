## 1. Modelos

- [x] 1.1 Añadir `PlanBVideo(video_id: str, youtube: dict[str, str] = {}, peertube: dict[str, str] = {})` a `models.py`
- [x] 1.2 Añadir campo `videos: dict[str, PlanBVideo] = {}` (indexado por UUID) a `PlanBCourseSpec`
- [x] 1.3 Tests pydantic: defaults vacíos, construcción con uno/ambos proveedores

## 2. Parser del bloque `videos:` (`PlanBSource`)

- [x] 2.1 En `load()`, parsear `course.yml` con `PyYAML` y leer el bloque `videos:` (reutilizar la lectura ya existente para `id:`)
- [x] 2.2 Por entrada: `id` obligatorio; aplanar listas `youtube`/`peertube` (`[{lang: id}, ...]` → `{lang: id}`); entradas sin `id` o sin proveedores se omiten con warning
- [x] 2.3 Poblar `PlanBCourseSpec.videos`
- [x] 2.4 Tests: course.yml con youtube-only, peertube-only, ambos, varias pistas de idioma, bloque `videos:` ausente (→ dict vacío), entrada malformada (omitida)

## 3. Render de vídeos (`builder._render_html`)

- [x] 3.1 Compilar patrones: directiva `:::video id=<UUID>:::` y forma imagen-YouTube `![alt](<youtube-url>)` (hosts `youtu.be`, `youtube.com/watch?v=`, `/embed/`, `/live/`)
- [x] 3.2 Helper `_youtube_id(url) -> str | None`: extraer el id de las variantes de URL de YouTube
- [x] 3.3 Helper `_embed_url(provider, id) -> str`: `youtube.com/embed/<id>` / `peertube.planb.network/videos/embed/<id>`
- [x] 3.4 Helper `_resolve_directive(uuid, videos) -> (url|None, warning|None)`: orden idioma (`en`) → proveedor (`youtube`>`peertube`) → fallback primera pista → None
- [x] 3.5 Helper `_video_iframe(url, title) -> str`: bloque `<div>`+`<iframe>` responsive 16:9 con inline styles
- [x] 3.6 Pasada pre-render: sustituir ambas sintaxis por marcadores `@@PLANB_VIDEO_n@@`, acumulando HTML/degradación resueltos; ejecutar ANTES de `_ASSET_IMG_RE`/`_MD.render`
- [x] 3.7 Pasada post-render: sustituir cada marcador (desenvolviendo el `<p>` contenedor) por su `<iframe>` o degradación
- [x] 3.8 Degradación: UUID ausente o sin pistas → `log.warning` y se descarta; nunca dejar `:::video` crudo ni `<img>` de YouTube
- [x] 3.9 Pasar `self._spec.videos` a `_render_html` desde `_create_pages`

## 4. Tests de render

- [x] 4.1 Directiva con youtube `en` → `<iframe src=".../embed/<id>">`, sin `:::video` crudo
- [x] 4.2 Directiva con peertube `en` → `<iframe src="peertube.planb.network/videos/embed/<id>">`
- [x] 4.3 Directiva con ambos proveedores → gana youtube
- [x] 4.4 Directiva sin pista `en` (solo `es`/`it`) → embebe primera pista + warning
- [x] 4.5 Directiva con UUID ausente en `course.yml` → degradación + warning, sin texto crudo
- [x] 4.6 Imagen-YouTube `![x](https://youtu.be/<id>)` y `watch?v=<id>` → `<iframe>`, no `<img>`
- [x] 4.7 Imagen normal de asset (`assets/en/...`) sigue produciendo `<img>` (no se trata como vídeo)
- [x] 4.8 Caso real `btc101`: el vídeo de BTC Map se embebe; caso `btc102`: la directiva `58e578ef…` se embebe (verificado end-to-end)

## 5. Documentación

- [x] 5.1 README: sección "Plan ₿ videos" explicando ambas sintaxis y el mapeo `course.yml`
- [x] 5.2 README: requisito de permitir `www.youtube.com` y `peertube.planb.network` como orígenes de iframe en el Moodle de destino (y el comportamiento si se purifican)
