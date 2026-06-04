## Why

Los cursos Plan ₿ incrustan vídeos, pero el importador `import-planb` no los reconoce: el contenido llega a Moodle roto.

Plan ₿ usa **dos sintaxis** de vídeo (documentadas en `bitcoin-educational-content/docs/PBN-template-repo/courses/course-content-scheme.json`):

1. **Directiva interna** `:::video id=<UUID>:::`. Hoy `markdown-it` no la reconoce y la deja pasar como **texto plano** literal en la página.
2. **Imagen markdown apuntando a YouTube** `![desc](https://youtu.be/<ID>)` / `![desc](https://www.youtube.com/watch?v=<ID>)`. Hoy se renderiza como un `<img>` cuyo `src` es una URL de YouTube → **imagen rota**. (Ej.: el vídeo de BTC Map en `btc101/en.md`.)

El `<UUID>` de la directiva **no** es un id de YouTube: es una clave interna. El mapeo vive en `course.yml` bajo el bloque `videos:`, que asocia cada UUID a uno o más proveedores (`youtube`, `peertube`) y, dentro de cada proveedor, a un id por idioma. Toda esa información está en el mismo repositorio que importamos y los embeds (YouTube y la instancia PeerTube de Plan ₿, `peertube.planb.network`) son públicos, así que podemos resolverlos nosotros mismos sin depender de ninguna API de Plan ₿.

## What Changes

- `PlanBSource` SHALL parsear el bloque `videos:` de `course.yml` a un nuevo modelo y exponerlo en `PlanBCourseSpec` (`{UUID → proveedores → {idioma → id}}`).
- `builder._render_html` SHALL convertir **ambas** sintaxis de vídeo en un `<iframe>` responsive 16:9 antes/después del render markdown:
  - YouTube → `https://www.youtube.com/embed/<id>`
  - PeerTube → `https://peertube.planb.network/videos/embed/<id>`
- Reglas de resolución, alineadas con el frontend de Plan ₿:
  - **Preferencia de proveedor**: `youtube` por encima de `peertube` cuando ambos existen.
  - **Idioma**: el importador es solo-inglés (`en.md`), así que se prefiere la pista `en`; si no hay pista `en` para ningún proveedor, se usa la primera pista disponible y se registra un warning; si el vídeo no tiene ninguna pista (o el UUID no está en `course.yml`), se degrada con gracia (se conserva el texto/descripción) y se registra un warning — nunca se deja `:::video ...:::` crudo ni un `<img>` roto.
- Documentar en el README que el HTMLPurifier de Moodle elimina `<iframe>` salvo que los dominios `youtube.com` y `peertube.planb.network` estén permitidos como orígenes de iframe en la configuración del Moodle de destino.

Fuera de alcance: vídeos en la introducción del curso (no se renderiza como página), proveedores distintos de YouTube/PeerTube (Rumble, MakerTube, BigBlueButton), y selección de idioma multi-idioma (el importador sigue siendo solo-inglés).

## Capabilities

### Modified Capabilities

- `planb-source`: además de Partes, Capítulos y assets, SHALL parsear el bloque `videos:` de `course.yml` y exponerlo en `PlanBCourseSpec`.
- `course-builder`: el render de la página de cada Capítulo SHALL reconocer las dos sintaxis de vídeo Plan ₿ y emitir un `<iframe>` responsive en lugar de texto crudo o `<img>` roto.

## Impact

- **`src/moodle_loader/models.py`**: nuevo modelo `PlanBVideo` (id + `youtube`/`peertube` como `{idioma → id}`); nuevo campo `videos` en `PlanBCourseSpec`.
- **`src/moodle_loader/sources/planb_source.py`**: parseo del bloque `videos:` de `course.yml` (vía el `PyYAML` ya disponible); poblar `PlanBCourseSpec.videos`.
- **`src/moodle_loader/builder.py`**: nuevo paso en `_render_html` que resuelve y sustituye las dos sintaxis de vídeo por `<iframe>`; helper de construcción de URL de embed por proveedor; helper de resolución proveedor/idioma.
- **`README.md`**: sección sobre vídeos y el requisito de permitir orígenes de iframe en Moodle.
- **Tests**: parser del bloque `videos:` (proveedores presentes/ausentes, varias pistas de idioma); render de directiva (youtube, peertube, fallback de idioma, UUID desconocido) y de la forma imagen-YouTube (`youtu.be`, `watch?v=`).
- **Riesgo de configuración**: si el plugin `local_moodlecourseloader_create_page` o el `format_text` de Moodle purifican el HTML, los `<iframe>` se eliminan salvo allowlist de dominios. Ver `design.md` (Riesgos y Preguntas abiertas).
