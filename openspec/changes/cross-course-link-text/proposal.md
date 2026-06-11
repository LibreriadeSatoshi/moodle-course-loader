## Why

Los enlaces a *otros cursos* que se resuelven a un curso interno de Moodle, cuando en el origen son una **URL desnuda** (sin texto de enlace propio), se renderizan hoy mostrando la ruta cruda como texto, p. ej. `/course/view.php?id=30` (el "enlace cortado"). Es poco legible. Deberían mostrar un texto humano: **`See course: {título del curso}`**.

## What Changes

- Para un enlace a curso planb.academy **resoluble** y **desnudo** (no `[texto](url)`), el contenido renderizado SHALL mostrar un enlace cuyo texto visible es `See course: {título}`, apuntando a la URL interna (root-relative) del curso.
- Los enlaces markdown con texto propio (`[texto](url)`) **conservan su texto** (no se tocan).
- El título se obtiene así: curso actual → `fullname` del propio spec; otros cursos → `fullname` del registro de Moodle (`get_course_by_shortname`), con *fallback* al shortname si no hay `fullname`.
- Si no se conoce el título de un curso resoluble, se mantiene el comportamiento actual (enlace con la ruta como texto).

Fuera de alcance: cambiar el texto de los enlaces markdown que ya traen etiqueta; enlaces no resolubles (se siguen eliminando dejando su texto).

## Capabilities

### Modified Capabilities

- `course-builder`: el render de enlaces a otros cursos usa `See course: {título}` como texto para URLs desnudas resolubles, en vez de la ruta cruda.

## Impact

- **`src/moodle_loader/builder.py`**: `_render_html` / `_rewrite_planb_links` aceptan un mapa `course_titles` ({uuid → título}) y lo usan para el texto de URLs desnudas; `PlanBCourseBuilder` construye ese mapa (curso actual = `fullname` del spec; otros = `fullname` de Moodle) y lo pasa al render.
- **Tests**: render de URL desnuda → `See course: {título}`; enlace markdown conserva etiqueta; end-to-end `build()` con título resuelto desde Moodle.
