## 1. Render

- [x] 1.1 `_render_html` y `_rewrite_planb_links` aceptan `course_titles: dict[str, str] | None`
- [x] 1.2 URL desnuda resoluble con título conocido → enlace markdown `[See course: {título}]({url})`
- [x] 1.3 URL desnuda resoluble sin título → comportamiento actual (ruta como texto)
- [x] 1.4 Enlace markdown `[texto](url)` → conserva `texto`

## 2. Construcción del mapa de títulos

- [x] 2.1 `PlanBCourseBuilder._build_course_titles` ({uuid → título}): curso actual = `spec.fullname`; otros = `fullname` de `get_course_by_shortname` (fallback shortname)
- [x] 2.2 Pasar `course_titles` a `_render_html` desde `_create_pages`

## 3. Tests

- [x] 3.1 Render: URL desnuda resoluble + `course_titles` → `>See course: {título}</a>` con `href` root-relative
- [x] 3.2 Render: enlace markdown con etiqueta → conserva la etiqueta (no `See course:`)
- [x] 3.3 Render: URL desnuda sin título en `course_titles` → fallback actual
- [x] 3.4 End-to-end `build()`: título resuelto desde Moodle (`fullname`) aparece como `See course: {fullname}` en el contenido de la página

## 4. Documentación

- [ ] 4.1 No necesario: comportamiento interno del render, sin superficie de CLI/config nueva
