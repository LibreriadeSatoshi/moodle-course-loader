## ADDED Requirements

### Requirement: Comprobar existencia del shortname antes de duplicar
El loader SHALL comprobar si ya existe un curso con el mismo shortname en Moodle antes de intentar duplicarlo. Si existe, devuelve `skipped` en lugar de llamar a `duplicate_course`.

#### Scenario: Curso ya existe en Moodle
- **WHEN** se procesa un `CourseSpec` cuyo `shortname` ya está en Moodle
- **THEN** el resultado es `LoadResult(status="skipped")` con mensaje que incluye el ID del curso existente
- **THEN** no se llama a `duplicate_course` ni a `update_course`

#### Scenario: Curso no existe en Moodle
- **WHEN** se procesa un `CourseSpec` cuyo `shortname` no existe en Moodle
- **THEN** se continúa con el flujo normal de duplicación

#### Scenario: Dry-run no llama a la API de comprobación
- **WHEN** el comando se ejecuta con `--dry-run`
- **THEN** no se llama a `get_course_by_shortname` ni a ningún otro endpoint de Moodle
- **THEN** todos los cursos aparecen como `skipped` con mensaje `dry-run: API not called`

### Requirement: Método get_course_by_shortname en MoodleClient
`MoodleClient` SHALL exponer `get_course_by_shortname(shortname: str) -> dict | None` que devuelve los datos del curso si existe o `None` si no.

#### Scenario: Shortname existe
- **WHEN** se llama a `get_course_by_shortname("codigo-existente")`
- **THEN** devuelve un dict con los datos del curso (al menos `id` y `shortname`)

#### Scenario: Shortname no existe
- **WHEN** se llama a `get_course_by_shortname("codigo-inexistente")`
- **THEN** devuelve `None`
