## Context

`moodle-course-loader` actualmente solo soporta **duplicación desde plantilla** (`CourseSpec` requiere `template_id`, `CourseLoader._process` llama a `core_course_duplicate_course`). El repositorio `bitcoin-educational-content` (Plan ₿ Network) mantiene cursos como markdown estructurado en Git: cada curso vive en `courses/<slug>/` con un `course.yml` de metadatos, un único `en.md` con todo el contenido (Partes separadas por `+++` y Capítulos por encabezados `##` con marcadores `<partId>` / `<chapterId>`), una carpeta `assets/en/` con imágenes referenciadas desde el markdown, y `quizz/NNN/` por capítulo (fuera de alcance v1).

El plugin Moodle `local_moodlecourseloader` (ya instalado en el servidor) expone las funciones `local_moodlecourseloader_update_section`, `local_moodlecourseloader_create_page` y `local_moodlecourseloader_set_course_image`, además de funciones core como `core_course_create_courses` y `core_files_upload`. Existe un servicio Moodle pre-construido (`moodlecourseloader`) que ya las agrupa.

## Goals / Non-Goals

**Goals:**
- Importar un curso Plan ₿ inglés a Moodle en una sola ejecución (`moodle-loader import-planb <path>`).
- Mapear Parte → Section, Capítulo → Page activity.
- Subir los assets y reescribir las URLs del markdown apuntando al área de archivos del curso.
- Fijar la imagen del curso vía `local_moodlecourseloader_set_course_image`.
- Wipe-and-reload: re-ejecuciones son idempotentes borrando el curso anterior por `shortname`.
- Soportar `--dry-run` (parsea + valida pero no llama a Moodle).
- Reusar `MOODLE_URL` / `MOODLE_TOKEN` del `.env` vía `Settings` / `MoodleClient` existentes.

**Non-Goals:**
- Otros idiomas que no sean inglés (los `.md` por idioma se ignoran).
- Quizzes (`quizz/NNN/*.yml`).
- Mapeo enriquecido de `course.yml` (topic, level, hours, tags, professors, videos) a campos custom de Moodle. Sólo se usa para `fullname`, `summary` y el slug del directorio como `shortname` por defecto.
- Soporte multi-curso por ejecución (un `import-planb` = un curso).
- Confirmación interactiva del borrado. Es destructivo por diseño; quien lo invoca asume el riesgo.

## Decisions

### 1. Modelo separado, no extensión de `CourseSpec`

**Decisión**: Crear `PlanBCourseSpec`, `PlanBPart`, `PlanBChapter`, `PlanBAsset` como modelos nuevos. No tocar `CourseSpec` ni `CourseLoader`.

**Razón**: `CourseSpec` está acoplado al flujo de duplicación (`template_id` obligatorio, `LoadResult` con status `created/skipped/failed`). El flujo Plan ₿ es ortogonal: múltiples llamadas WS, resultado más rico (course_id + secciones + páginas creadas). Mezclar los dos rompe modelos existentes.

**Alternativa descartada**: Hacer `template_id` opcional y bifurcar dentro de `_process`. Acopla dos flujos muy distintos.

### 2. Parser de `en.md`: separación por `+++` + escaneo de encabezados

**Decisión**: 
1. Extraer frontmatter YAML (`---...---`) con `python-frontmatter` (nueva dependencia) o parser propio sobre el separador `---`.
2. Partir el resto por `\n+++\n`. Cada bloque resultante (excepto el primero, que es la introducción del curso) es una Parte.
3. Dentro de cada Parte: la primera línea `# Heading` es el título de la Parte. Buscar el siguiente `<partId>UUID</partId>` para el ID estable.
4. Dividir cada Parte por encabezados `## ` (de inicio de línea, no `###`). Cada bloque es un Capítulo. Su título es el texto del `##`, su ID el `<chapterId>` siguiente.
5. El cuerpo del Capítulo es todo lo que sigue al `<chapterId>` hasta el siguiente `##` o `+++`.

**Razón**: Estructura observada en `btc101/en.md`. Mantener el parser tonto y declarativo facilita debugging. UUIDs son opcionales: si faltan, se sintetizan a partir del título (slug).

**Alternativa descartada**: Parser completo de AST de markdown (`markdown-it-py`). Overkill: solo necesitamos detectar `#`, `##`, `+++` y tags inline. El cuerpo se pasa tal cual a Moodle (que renderiza markdown si se indica `contentformat=4` o HTML si se indica `1`).

### 3. Formato de contenido en Moodle: HTML pre-renderizado

**Decisión**: Convertir el markdown de cada capítulo a HTML antes de enviarlo a `local_moodlecourseloader_create_page`. Usar `markdown-it-py` (nueva dependencia).

**Razón**: Moodle Pages aceptan `contentformat` numérico (1=HTML, 4=markdown). Renderizar en cliente da control sobre cómo se reescriben las imágenes y evita depender del soporte de markdown del Moodle de destino, que varía por versión y filtros activos.

**Alternativa descartada**: Enviar markdown crudo con `contentformat=4`. Funciona pero introduce dependencia del filtro markdown de Moodle.

### 4. Subida de assets: una pasada, antes de crear páginas

**Decisión**: Antes de crear cualquier página:
1. Escanear todos los capítulos por referencias `![*](assets/en/...)`.
2. Subir cada asset único una sola vez vía `core_files_upload` al área `draft` y luego moverlo al área de archivos del curso (file area `course_summary` o equivalente para imágenes embebidas — a determinar en implementación).
3. Construir un mapa `{ruta_relativa → url_moodle}`.
4. Al renderizar cada capítulo, reescribir las URLs usando ese mapa.

**Razón**: Evita subir un mismo asset N veces si está referenciado en N capítulos. Permite fallar temprano si algún archivo del filesystem no existe.

**Riesgo**: El mecanismo exacto de Moodle para servir archivos embebidos en Page activities (`@@PLUGINFILE@@` vs URLs `pluginfile.php`) hay que confirmarlo durante implementación contra una instancia real.

### 5. Imagen de curso: primer asset referenciado en la introducción

**Decisión** (v1): Tomar el primer `![*](assets/en/...)` que aparezca en la sección de introducción (antes del primer `+++`). Si no hay ninguno, omitir `set_course_image`.

**Razón**: Heurística simple sin configurar nada. Suficiente para `btc101` (la intro tiene imágenes). En futuras versiones se puede leer `course.yml` para un campo dedicado.

### 6. Wipe-and-reload: borrar por shortname al inicio

**Decisión**: En `PlanBCourseBuilder.build()`, antes de crear, llamar a `get_course_by_shortname(shortname)`. Si existe, llamar a `core_course_delete_courses` con su ID. Continuar.

**Shortname por defecto**: nombre del directorio (`btc101`). Override con `--shortname`.

**Razón**: Es la idempotencia que pidió el usuario. Asume que ningún humano edita el curso a mano (sería sobreescrito en cada import). Documentar fuerte en el README.

### 7. `--dry-run` no abre conexión a Moodle

**Decisión**: Con `--dry-run`, el comando parsea el directorio, valida estructura, imprime un resumen (n partes, n capítulos, n assets) y termina sin instanciar `MoodleClient`.

**Razón**: Coincide con la semántica actual del flag en otros comandos (`load`, `load-sheets`).

### 8. Orquestación: `PlanBCourseBuilder` separado de `CourseLoader`

**Decisión**: Crear `src/moodle_loader/builder.py` con clase `PlanBCourseBuilder(client, spec)`. No reutilizar `CourseLoader` (que está atado a `CourseSpec` y resultado simple).

**Razón**: La operación es más compleja (varias llamadas WS encadenadas, estado intermedio: course_id, mapa de URLs de assets, IDs de secciones creadas). Un orquestador dedicado mantiene el código claro.

## Risks / Trade-offs

- **Borrado destructivo**: `wipe-and-reload` es peligroso si alguien lo ejecuta apuntando a producción contra un shortname que no esperaba. Mitigación: documentar en README, requerir `--shortname` explícito para anular el default, y considerar un futuro flag `--no-wipe` (no en v1).
- **`core_files_upload` y embed de imágenes**: El detalle de cómo se sirven archivos embebidos en Page activities depende de la versión de Moodle y de filtros activos. Requiere prueba contra el Moodle real del usuario antes de declarar v1 estable.
- **UUIDs como anclas**: El parser usa `<partId>` / `<chapterId>` si están presentes; si no, genera slugs. No se usan aún para nada (no hay sincronización incremental en v1), pero quedan registrados en el modelo para uso futuro.
- **Conversión markdown→HTML**: `markdown-it-py` no soporta todos los plugins de Moodle (`<partId>`, etc.). Las tags personalizadas se eliminan en pre-proceso antes de convertir.
- **Tamaño de assets**: `core_files_upload` espera base64; cursos con muchas imágenes podrían encontrarse con límites de payload del servidor. Para v1, dejar que falle ruidosamente.

## Open Questions

- ¿Categoría de Moodle donde crear el curso? Probablemente reutilizar `DEFAULT_CATEGORY_NAME` del `.env` y resolverla con `client.get_categories()`. ¿O añadir `--category-id` al comando? Por ahora: reutilizar `DEFAULT_CATEGORY_NAME` con fallback ID 1 si no existe.
- ¿Visibilidad del curso recién creado? `visible=False` por defecto, conservador. Añadir `--visible` si se necesita.
- ¿Necesitamos `local_moodlecourseloader_update_section` para *crear* secciones o solo para renombrarlas/actualizarlas? Moodle crea secciones implícitamente con `numsections`; revisar contra la firma real de la WS function durante implementación.
- ¿La regeneración de UUIDs cuando faltan debería ser determinística (hash del título) o random? Para v1: hash del título (estable).
