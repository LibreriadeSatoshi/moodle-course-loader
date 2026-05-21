## Context

`moodle-loader` ya tiene una abstracción `CourseSource` con `YamlSource` funcional y `SheetsSource` como stub. El equipo gestiona la programación de cursos en un Google Sheet con columnas operativas (Path, CODE, Course name Spanish/English, template_id). El cliente Moodle ya tiene un método `call()` genérico que puede invocar cualquier función de la API REST.

## Goals / Non-Goals

**Goals:**
- Implementar `SheetsSource.load()` que lea el Sheet y devuelva `list[CourseSpec]`
- Resolver nombres de categoría (columna `Path`) a IDs de Moodle via API en lugar de hardcodear un dict
- Hacer configurables los fallbacks (`DEFAULT_TEMPLATE_ID`, `DEFAULT_CATEGORY_NAME`) desde `.env`
- Añadir comando CLI `load-sheets` para invocar la nueva fuente

**Non-Goals:**
- Escribir de vuelta al Sheet (logs, resultados)
- Soporte OAuth interactivo (solo Service Account)
- Cachear categorías entre ejecuciones

## Decisions

### 1. Resolución de categorías via API, no dict hardcodeado

**Decisión**: Llamar a `core_course_category_get_categories` al inicio de `load()` y construir un dict `name → id` en memoria.

**Alternativa descartada**: Dict estático en config o código. Se descarta porque las categorías pueden cambiar y obligaría a mantener sincronización manual.

**Fallback**: Si `Path` no está en el dict, loguear warning y usar `DEFAULT_CATEGORY_NAME`. Si ese tampoco existe, lanzar `SourceError` (no hay default sensato).

### 2. Autenticación Google con Service Account

**Decisión**: Usar `gspread.service_account(filename=credentials_file)` donde `credentials_file` es configurable (default `credentials.json`).

**Alternativa descartada**: OAuth interactivo. Se descarta porque la herramienta es CLI automatizable; un flujo interactivo rompería pipelines.

### 3. Filas vacías: skip silencioso

**Decisión**: Filas donde `fullname` y `shortname` estén ambos vacíos se omiten sin error. Filas donde solo uno de los dos está vacío emiten warning y se saltan.

**Razón**: El Sheet tiene filas en blanco como separadores visuales. Fallar con error por ellas sería disruptivo.

### 4. Configurables desde `.env` con defaults razonables

**Decisión**: `DEFAULT_TEMPLATE_ID=20` y `DEFAULT_CATEGORY_NAME=Bitcoin 4 Everyone` como campos de `Settings` (pydantic-settings). Así se pueden sobreescribir por entorno sin tocar código.

## Risks / Trade-offs

- **Rate limits de Google Sheets API** → La carga completa es una sola llamada `get_all_records()`, no hay bucle de requests. Riesgo mínimo.
- **Cambio de nombre de columna en el Sheet** → Las constantes `COL_*` están agrupadas al inicio de `sheets_source.py` para facilitar el mantenimiento, pero siguen siendo hardcodeadas. Si cambia un header, hay que tocar código.
- **Credenciales de Service Account** → El archivo `credentials.json` no debe versionarse. Ya está en `.gitignore`. El error si no existe es claro via `SourceError`.

## Open Questions

- ¿El nombre de la hoja (worksheet) es siempre el mismo o varía? Por ahora se pasa como parámetro con default `"Sheet1"`. Podría moverse a `.env` si se necesita.
