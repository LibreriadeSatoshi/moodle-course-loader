## Why

El equipo quiere reutilizar los cursos del repositorio `bitcoin-educational-content` (Plan ₿ Network) dentro de Moodle sin re-introducir manualmente el contenido. Hoy el loader solo sabe duplicar cursos desde plantillas: no puede construir un curso desde cero a partir de markdown estructurado. Añadir `import-planb` permite importar un curso (empezando por `btc101`, inglés) en una sola ejecución y mantener la fuente de verdad en Git.

## What Changes

- Nueva fuente `PlanBSource` que parsea un directorio de curso Plan ₿ (`course.yml` + `en.md` + `assets/en/*`) en un modelo intermedio con Partes y Capítulos.
- Nuevo orquestador `PlanBCourseBuilder` que construye el curso en Moodle desde cero: crea el curso, sube los assets, fija la imagen del curso, crea una sección por Parte y una página por Capítulo.
- Nuevo modelo `PlanBCourseSpec` (paralelo a `CourseSpec`) para representar cursos construidos desde cero, sin `template_id`. El flujo existente de duplicación de plantillas no se toca.
- Nuevo comando CLI `moodle-loader import-planb <course_path> [--shortname X] [--dry-run]`.
- Estrategia de idempotencia "wipe and reload": antes de importar se borra el curso existente con el mismo `shortname` (si lo hay) vía `core_course_delete_courses`. Destructivo por diseño.
- Extensiones a `MoodleClient` para llamar a las nuevas WS functions: `core_course_create_courses`, `core_files_upload`, `local_moodlecourseloader_update_section`, `local_moodlecourseloader_create_page`, `local_moodlecourseloader_set_course_image`.
- Inglés único en v1. El mapeo enriquecido de `course.yml` (topic, level, hours, tags, professors) y los quizzes quedan fuera de alcance.

## Capabilities

### New Capabilities

- `planb-source`: Parseo de un directorio de curso Plan ₿ (`course.yml` + `en.md` + `assets/en/*`) a un modelo `PlanBCourseSpec` con Partes y Capítulos delimitados por `+++`, `<partId>` y `<chapterId>`.
- `course-builder`: Construcción de un curso Moodle desde cero a partir de `PlanBCourseSpec`: wipe-and-reload, creación del curso, subida de assets, fijado de imagen, creación de secciones (una por Parte) y páginas (una por Capítulo).

### Modified Capabilities

- `moodle-client`: Se añaden métodos para `core_course_create_courses`, `core_files_upload`, `local_moodlecourseloader_update_section`, `local_moodlecourseloader_create_page` y `local_moodlecourseloader_set_course_image`. Extensión sin cambio de comportamiento previo.

## Impact

- **`src/moodle_loader/sources/planb_source.py`**: nueva implementación (parser markdown + course.yml).
- **`src/moodle_loader/builder.py`** (nuevo): `PlanBCourseBuilder` con el flujo de construcción desde cero.
- **`src/moodle_loader/client.py`**: cinco métodos nuevos (ver Modified Capabilities).
- **`src/moodle_loader/models.py`**: nuevos modelos `PlanBCourseSpec`, `PlanBPart`, `PlanBChapter`, `PlanBAsset`, `PlanBBuildResult`.
- **`src/moodle_loader/cli.py`**: nuevo comando `import-planb`.
- **`src/moodle_loader/sources/__init__.py`**: exponer `PlanBSource`.
- **`pyproject.toml`**: dependencia nueva `python-frontmatter` (o `PyYAML` + parser propio) para el frontmatter de `en.md`. `PyYAML` ya está en uso indirectamente.
- **Tests**: cobertura para parser (estructura Plan ₿ fija + casos límite), builder (mocking del cliente), CLI.
- **Riesgo destructivo**: `import-planb` borra el curso con el mismo `shortname` sin confirmación interactiva. Debe documentarse en el README.
