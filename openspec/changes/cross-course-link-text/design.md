## Context

`_rewrite_planb_links` (builder.py) reescribe enlaces planb.academy a cursos internos. Tras `cross-course-link-text`'s antecesor, las URLs son root-relative (`/course/view.php?id=N`). Para URLs **desnudas** resolubles emite un enlace markdown `[{url}]({url})`, así que el texto visible es la ruta — ilegible. Los enlaces markdown `[texto](url)` ya conservan el texto del autor.

## Goals / Non-Goals

**Goals:**
- URLs desnudas resolubles → texto `See course: {título}`.
- Conservar el texto de enlaces markdown con etiqueta.
- Resolver el título sin red extra cuando sea posible (curso actual desde el spec; otros desde el registro Moodle que ya se consulta).

**Non-Goals:**
- Reescribir etiquetas de enlaces markdown existentes.
- Resolver títulos de cursos aún no importados (no resolubles → se siguen tratando como hoy).

## Decisions

### 1. Mapa `course_titles` paralelo a `link_map`

**Decisión**: Añadir `course_titles: dict[str, str]` ({uuid → título}) y pasarlo a `_render_html`/`_rewrite_planb_links` junto a `link_map` (que sigue siendo {uuid → url}). El texto de una URL desnuda resoluble es `See course: {course_titles[uuid]}`; si el uuid no está en `course_titles`, se mantiene el render actual.

**Razón**: Mantiene `link_map` (url) sin cambiar de tipo, minimizando el churn en los tests existentes; el título es información ortogonal y opcional.

**Alternativa descartada**: enriquecer `link_map` a `{uuid → (url, título)}`. Más limpio en teoría pero obliga a tocar todos los tests de enlaces existentes.

### 2. Origen del título

**Decisión**: Curso actual (`uuid == spec.planb_id`) → `spec.fullname`. Otros → `fullname` del dict que devuelve `get_course_by_shortname` (la misma llamada que ya resuelve el id); si falta, *fallback* al shortname.

**Razón**: No añade llamadas de red (reutiliza la consulta de `_build_link_map`).

### 3. Sólo URLs desnudas

**Decisión**: El texto `See course: {título}` sólo aplica a URLs desnudas. Los enlaces `[texto](url)` conservan `texto`.

**Razón**: El problema ("enlace cortado") es exclusivo de las URLs desnudas; las etiquetas del autor son intencionadas y más informativas.

## Risks / Trade-offs

- Texto en inglés fijo (`See course:`). Coherente con el resto del contenido (curso en inglés); si se internacionaliza en el futuro, habría que parametrizarlo.
- `course_titles` y `link_map` son dos mapas paralelos por uuid; aceptable por el bajo acoplamiento.

## Open Questions

- ¿Aplicar también a enlaces markdown con etiqueta (sobrescribir su texto por `See course: {título}`)? Propuesto: **no** (conservar etiqueta). Confirmar.
