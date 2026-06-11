## ADDED Requirements

### Requirement: Texto legible para enlaces a otros cursos
Cuando un enlace a curso de planb.academy se resuelve a un curso interno de Moodle y se conoce su título, una **URL desnuda** (sin texto de enlace propio) SHALL renderizarse como un enlace cuyo **texto visible es `See course: {título}`**, apuntando a la URL interna (root-relative) del curso, en lugar de mostrar la ruta cruda (`/course/view.php?id=N`).

Los enlaces markdown con texto propio (`[texto](url)`) SHALL conservar su `texto`. Si el curso es resoluble pero no se conoce su título, SHALL mantenerse el comportamiento actual (enlace con la ruta como texto).

El título se obtiene del mapa `course_titles` ({uuid → título}), poblado por `PlanBCourseBuilder`: el curso actual usa el `fullname` de su propio spec; los demás usan el `fullname` del registro de Moodle (`get_course_by_shortname`), con *fallback* al shortname.

#### Scenario: URL desnuda con título conocido
- **WHEN** el cuerpo contiene una URL desnuda `https://planb.academy/courses/<uuid>` resoluble y `course_titles[<uuid>]` es `"Bitcoin History"`
- **THEN** el HTML contiene `<a href="/course/view.php?id=<n>">See course: Bitcoin History</a>`
- **THEN** no aparece la ruta cruda como texto visible

#### Scenario: Enlace markdown conserva su etiqueta
- **WHEN** el cuerpo contiene `[miner chapter](https://planb.academy/courses/<uuid>)` resoluble
- **THEN** el texto del enlace sigue siendo `miner chapter` (no `See course: ...`)

#### Scenario: URL desnuda sin título conocido
- **WHEN** una URL desnuda es resoluble pero su `<uuid>` no está en `course_titles`
- **THEN** se mantiene el comportamiento actual (enlace cuya etiqueta es la ruta)

#### Scenario: Título resuelto desde Moodle (end-to-end)
- **WHEN** `build()` procesa un capítulo con una URL desnuda a otro curso ya existente en Moodle cuyo `fullname` es `"Bitcoin History"`
- **THEN** el contenido de la página creada contiene `See course: Bitcoin History` enlazando a `/course/view.php?id=<n>`
