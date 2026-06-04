## Context

El importador Plan ₿ (`planb_source.py` + `builder.py`) ya convierte cada Capítulo en una página Moodle: `_render_html(chapter.body, asset_url_map, link_map)` limpia tags `<partId>`/`<chapterId>`, reescribe assets a data URIs, reescribe enlaces a planb.academy y convierte markdown a HTML con `markdown-it-py` (`_MD = MarkdownIt().enable("table")`).

Hoy ese pipeline ignora los vídeos. Plan ₿ los expresa de dos formas (ver `course-content-scheme.json` del repo de contenidos):

1. `:::video id=<UUID>:::` — referencia interna. El `<UUID>` se resuelve contra el bloque `videos:` de `course.yml`:

   ```yaml
   videos:
     - id: 58e578ef-bb3c-423d-8431-0c16db8e5f29
       peertube:
         - es: aee8BTojUSaDFnEPnoUUzC
         - it: 2Gq2JdsnSJJLc5BtPGe1kJ
     - id: 758d7d3b-84e6-4f52-bf43-967a2ce7e7ec
       youtube:
         - fr: PdiL6_1wbQY
   ```

   Cada vídeo tiene `youtube` y/o `peertube`; cada proveedor es una lista de mapas de un solo par `{idioma: id_en_el_proveedor}`.

2. `![desc](https://youtu.be/<ID>)` o `![desc](https://www.youtube.com/watch?v=<ID>)` — el id de YouTube está **inline**, no necesita `course.yml`. (Es así como `btc101/en.md` incrusta el vídeo de BTC Map.)

Reglas confirmadas en el frontend de Plan ₿ (`bitcoin-learning-management-system`):
- **Proveedor**: la query ordena `provider DESC`, es decir **YouTube gana a PeerTube** cuando ambos existen.
- **URL de embed** (`apps/academy/src/utils/misc.ts`, `fixEmbedUrl`): YouTube → `youtube.com/embed/<id>`; PeerTube → `peertube.planb.network/videos/embed/<id>` (host confirmado en `pear-sync/peertube-sync.js`).

## Goals / Non-Goals

**Goals:**
- Reconocer las dos sintaxis de vídeo y renderizarlas como un reproductor embebido responsive 16:9 en la página del Capítulo.
- Resolver la directiva `:::video id=<UUID>:::` vía el bloque `videos:` de `course.yml`.
- Resolver la forma imagen-YouTube directamente desde la URL.
- Degradar con gracia (texto/enlace, nunca `:::video` crudo ni `<img>` roto) cuando no haya pista resoluble.

**Non-Goals:**
- Vídeos en la introducción del curso (no se renderiza como página en v1).
- Proveedores ajenos a YouTube/PeerTube que el frontend de Plan ₿ también soporta (Rumble, MakerTube, `live.planb.academy`/BigBlueButton).
- Selección de idioma distinta de inglés (el importador sigue leyendo solo `en.md`).
- Descargar/rehospedar vídeos. Solo se embeben fuentes públicas.
- Cualquier cambio en cómo el plugin Moodle almacena el HTML (ver Riesgos).

## Decisions

### 1. Modelo `PlanBVideo` con proveedores como `{idioma → id}`

**Decisión**: Añadir `PlanBVideo(video_id: str, youtube: dict[str, str], peertube: dict[str, str])` a `models.py`, y `PlanBCourseSpec.videos: dict[str, PlanBVideo]` indexado por UUID (acceso O(1) desde el render).

**Razón**: Indexar por UUID es lo que necesita la resolución de la directiva. Aplanar las listas `- en: ID` de YAML a un dict por proveedor simplifica el lookup por idioma. Mantener `youtube` y `peertube` separados conserva la preferencia de proveedor.

**Alternativa descartada**: guardar el YAML crudo (lista de dicts) en el spec. Empuja el aplanado al builder y duplica lógica.

### 2. Parseo del bloque `videos:` en `PlanBSource`

**Decisión**: En `load()`, leer `course.yml` (ya se lee para `id:`) y parsear `videos:` con `PyYAML`. Por cada entrada: `id` obligatorio; `youtube`/`peertube` opcionales; aplanar cada lista `[{lang: id}, ...]` a `{lang: id}`. Entradas sin `id` o con proveedores vacíos se omiten (con warning). El resultado puebla `PlanBCourseSpec.videos`.

**Razón**: La fuente de verdad del mapeo es `course.yml`. `PyYAML` ya está disponible (transitivo vía `python-frontmatter`).

**Nota**: parsear el bloque `videos:` NO es lo mismo que validar que cada UUID referenciado en `en.md` exista en el mapa; esa validación es responsabilidad del render (que degrada con warning), no del parser.

### 3. Sustitución en dos pasadas alrededor del render markdown

**Problema**: `markdown-it` está configurado con `html` desactivado (preset CommonMark), así que inyectar HTML de `<iframe>` en el markdown lo escaparía. Y `:::video ...:::` debe interceptarse antes de que markdown-it lo trate como texto; la forma imagen-YouTube debe interceptarse antes de que se convierta en `<img>`.

**Decisión**: 
1. **Pre-render**: una pasada sobre el markdown (antes de `_MD.render`) detecta ambas sintaxis, resuelve cada una a una URL de embed (o a una degradación), y la reemplaza por un marcador único en su propia línea, p. ej. `@@PLANB_VIDEO_0@@`. Las URLs/HTML resueltos se acumulan en una lista indexada.
2. **Post-render**: tras `_MD.render` (que envuelve el marcador en `<p>@@PLANB_VIDEO_0@@</p>`), se sustituye cada marcador — desenvolviendo su `<p>` contenedor — por el bloque `<iframe>` final.

**Razón**: Es el mismo patrón seguro que evita la escapada de HTML y no requiere activar `html=true` globalmente (que dejaría pasar HTML arbitrario del contenido fuente). El orden importa: la detección de la imagen-YouTube debe ocurrir antes que `_ASSET_IMG_RE`/render para no producir `<img>`.

**Alternativa descartada**: activar `html=true` en markdown-it e inyectar el `<iframe>` directo. Cambia el comportamiento de render para todo el contenido y abre la puerta a HTML del origen.

### 4. Resolución proveedor + idioma (directiva)

**Decisión**: Dado el `PlanBVideo` del UUID, elegir en este orden (idioma primero, proveedor como desempate, igual que Plan ₿ pero fijando idioma a `en`):
1. `youtube["en"]` si existe.
2. `peertube["en"]` si existe.
3. Primera pista de `youtube` (cualquier idioma) → warning "vídeo no disponible en inglés".
4. Primera pista de `peertube` (cualquier idioma) → warning.
5. Ninguna pista / UUID ausente en `course.yml` → degradación (ver Decisión 6) + warning.

**Razón**: El importador es solo-inglés, así que `en` es la pista correcta. La preferencia `youtube > peertube` replica el `provider DESC` del frontend y es lo que el usuario ve hoy en planb.network. El fallback a otro idioma evita perder el vídeo cuando aún no hay doblaje/subtítulo en inglés (caso real: `58e578ef…` en `btc102`, solo `es`/`it`).

### 5. Construcción de la URL de embed y del `<iframe>`

**Decisión**:
- YouTube: `https://www.youtube.com/embed/<id>`. Para la forma imagen, extraer `<id>` de `youtu.be/<id>`, `watch?v=<id>`, `youtube.com/embed/<id>` o `youtube.com/live/<id>` (replicando `fixEmbedUrl`).
- PeerTube: `https://peertube.planb.network/videos/embed/<id>`.
- Envoltura responsive 16:9, con el mismo límite de ancho que las imágenes (75%) para coherencia visual:

  ```html
  <div style="max-width: 75%; margin: 1em auto;">
    <div style="position: relative; padding-bottom: 56.25%; height: 0;">
      <iframe src="<URL>" title="<alt|título>"
              style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;"
              allow="fullscreen" allowfullscreen></iframe>
    </div>
  </div>
  ```

**Razón**: `padding-bottom: 56.25%` (relativo al ancho del contenedor) da el 16:9; el envoltorio externo limita el ancho sin romper el ratio. Inline styles porque Moodle conserva `style` pero elimina `<style>` (mismo motivo que en tablas/imágenes).

### 6. Degradación con gracia

**Decisión**: Cuando un vídeo no se puede resolver (UUID ausente, sin pistas), NO dejar `:::video ...:::` ni `<img>` roto. En su lugar:
- Si había texto/`alt` o título, conservarlo como párrafo o enlace.
- Registrar un warning con el UUID/URL y el motivo.

**Razón**: Una página con un texto o enlace es mejor que un marcador roto. El warning hace visible el contenido a corregir en el origen.

## Risks / Trade-offs

- **HTMLPurifier de Moodle elimina `<iframe>`**: Es el riesgo principal. Moodle (y posiblemente el propio `local_moodlecourseloader_create_page`) puede pasar el contenido por un purificador que elimina `<iframe>` salvo que su dominio esté en la allowlist de orígenes de iframe del sitio (incluir `youtube.com` y `peertube.planb.network`). El comentario existente en `builder.py` ("Moodle strips `<style>` blocks but keeps inline `style`") sugiere que SÍ hay purificación. **Mitigación**: (a) documentar el requisito de allowlist en el README; (b) validar contra el Moodle real del usuario antes de declarar v1 estable; (c) si los iframes resultan inviables, fallback de YouTube a enlace plano (el filtro multimedia de Moodle auto-embebe enlaces de YouTube) — PeerTube no se auto-embebería. Ver Preguntas abiertas.
- **PeerTube solo cubre algunos idiomas**: varios vídeos `btc102` solo tienen pistas `es`/`it`. Con la regla de fallback se embeben en idioma no-inglés (con warning), lo que puede no ser deseable. Trade-off aceptado en v1; alternativa (omitir y enlazar) queda como opción futura.
- **Dependencia del host PeerTube**: `peertube.planb.network` es un valor fijo. Si Plan ₿ migra de instancia, habría que actualizar la constante. Aceptable: es la misma suposición que hace el frontend de Plan ₿.
- **IDs malformados en `course.yml`**: un id de proveedor erróneo produce un embed que no carga. El importador no puede validar la existencia remota sin llamadas de red; se asume el `course.yml` como fuente de verdad.

## Open Questions

- ¿`local_moodlecourseloader_create_page` almacena el HTML verbatim o lo pasa por `format_text`/HTMLPurifier? Determina si los `<iframe>` sobreviven sin configuración. **A confirmar contra el plugin/instancia real durante implementación.**
- Si los iframes se purifican: ¿preferimos (a) pedir al admin que añada los dominios a "orígenes de iframe permitidos", o (b) caer a enlace plano para YouTube + enlace para PeerTube? Recomendación: (a) como primario por paridad con Plan ₿; (b) como fallback documentado.
- ¿Debe el fallback de idioma (Decisión 4, pasos 3-4) embeber el vídeo en otro idioma, o mejor omitirlo y dejar un enlace? v1: embeber con warning; revisable según feedback.
