## Context

`moodle-loader` carga todos los cursos de una fuente (YAML o Sheet) de una vez. No hay forma de cargar uno solo sin editar la fuente. Además, si se intenta duplicar un curso cuyo shortname ya existe en Moodle, la API falla con un error en lugar de dar un mensaje claro.

Moodle expone `core_course_get_courses_by_field` que permite buscar cursos por `shortname` — ya está habilitado en el servicio personalizado del cliente.

## Goals / Non-Goals

**Goals:**
- Filtrar por shortname antes de llamar al loader, tanto en `load` como en `load-sheets`
- Comprobar si el shortname ya existe en Moodle antes de intentar duplicar; devolver `skipped` si es así
- Dar un mensaje claro en la tabla de resultados cuando se salta un curso por duplicado

**Non-Goals:**
- Actualizar un curso existente si ya existe (eso es scope de una fase futura)
- Filtrar por otros campos (fullname, category, etc.)
- Soporte para múltiples shortnames en un mismo comando

## Decisions

### 1. Filtro en el CLI, no en la fuente

**Decisión**: El filtrado por `--shortname` se aplica en el CLI sobre la lista de `CourseSpec` ya cargados, no dentro de `YamlSource` o `SheetsSource`.

**Razón**: Las fuentes son responsables de leer datos, no de filtrarlos. Mantener el filtro en el CLI permite reutilizar las fuentes sin acoplamiento.

### 2. Comprobación de existencia en `CourseLoader._process()`

**Decisión**: Antes de llamar a `duplicate_course()`, `_process()` llama a `client.get_course_by_shortname()`. Si devuelve un curso, retorna `LoadResult(status="skipped")` con mensaje indicando el ID existente.

**Alternativa descartada**: Comprobar en el CLI antes de llamar al loader. Se descarta porque el loader ya encapsula la lógica de procesamiento por curso; añadirlo ahí mantiene la coherencia y beneficia también al comando `load` (YAML).

### 3. Un único método `get_course_by_shortname()` en el cliente

**Decisión**: Añadir `get_course_by_shortname(shortname) -> dict | None` que devuelve el primer resultado o `None`.

**Razón**: Encapsula la llamada a `core_course_get_courses_by_field` con `field=shortname` y oculta la estructura de respuesta al resto del código.

## Risks / Trade-offs

- **Race condition**: otro proceso podría crear un curso con el mismo shortname entre la comprobación y el duplicado → riesgo mínimo en este contexto de uso manual/operador.
- **Coste de API**: la comprobación añade una llamada por curso → aceptable dado el volumen (decenas, no miles).
