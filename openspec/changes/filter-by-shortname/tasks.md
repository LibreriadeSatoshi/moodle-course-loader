## 1. Cliente Moodle

- [x] 1.1 Añadir `get_course_by_shortname(shortname: str) -> dict | None` a `MoodleClient` usando `core_course_get_courses_by_field`
- [x] 1.2 Añadir test para `get_course_by_shortname` cuando el curso existe
- [x] 1.3 Añadir test para `get_course_by_shortname` cuando el curso no existe

## 2. Comprobación de duplicados en el loader

- [x] 2.1 En `CourseLoader._process()`, llamar a `client.get_course_by_shortname()` antes de `duplicate_course()`
- [x] 2.2 Si ya existe, retornar `LoadResult(status="skipped", message="already exists: course_id=<id>")`
- [x] 2.3 Añadir test: curso ya existente devuelve `skipped` y no llama a `duplicate_course`
- [x] 2.4 Añadir test: curso inexistente continúa con el flujo normal

## 3. Filtro --shortname en el CLI

- [x] 3.1 Añadir opción `--shortname` (opcional) a `load` en `cli.py`
- [x] 3.2 Añadir opción `--shortname` (opcional) a `load-sheets` en `cli.py`
- [x] 3.3 Tras cargar los specs de la fuente, filtrar por shortname si se especificó
- [x] 3.4 Si el shortname no se encuentra en la fuente, terminar con error y mensaje claro
- [x] 3.5 Añadir test: `--shortname` filtra correctamente y solo procesa el curso indicado
- [x] 3.6 Añadir test: `--shortname` no encontrado en la fuente termina con error
