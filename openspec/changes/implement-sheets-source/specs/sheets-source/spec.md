## ADDED Requirements

### Requirement: Leer cursos desde Google Sheets
`SheetsSource` SHALL leer filas de un Google Sheet y devolver una lista de `CourseSpec` usando las columnas definidas en el mapeo canónico.

Mapeo de columnas:
- `Course name (Spanish)` → `fullname`
- `CODE` → `shortname`
- `Course Name (English)` → `summary`
- `Path` → `category_id` (resuelto via API)
- `template_id` → `template_id` (opcional, default configurable)
- `visible` → siempre `False`

#### Scenario: Carga exitosa con todas las columnas
- **WHEN** el Sheet tiene filas con `Course name (Spanish)`, `CODE`, `Course Name (English)`, `Path` válido y `template_id`
- **THEN** `load()` devuelve una lista de `CourseSpec` con los campos mapeados correctamente

#### Scenario: template_id vacío usa default
- **WHEN** una fila tiene la columna `template_id` vacía
- **THEN** el `CourseSpec` resultante usa el valor de `DEFAULT_TEMPLATE_ID` del `.env`

### Requirement: Resolución de categoría via API de Moodle
`SheetsSource` SHALL consultar `core_course_category_get_categories` al inicio de `load()` y construir un dict `nombre → id` para resolver la columna `Path`.

#### Scenario: Path existe como categoría en Moodle
- **WHEN** el valor de `Path` en una fila coincide exactamente con el nombre de una categoría en Moodle
- **THEN** `category_id` del `CourseSpec` es el ID de esa categoría

#### Scenario: Path no existe, fallback a default
- **WHEN** el valor de `Path` no coincide con ninguna categoría en Moodle
- **THEN** se emite un warning en el log con el nombre de categoría no encontrado
- **THEN** `category_id` usa el ID de la categoría `DEFAULT_CATEGORY_NAME`

#### Scenario: Path no existe y default tampoco existe en Moodle
- **WHEN** ni `Path` ni `DEFAULT_CATEGORY_NAME` existen como categorías en Moodle
- **THEN** `load()` lanza `SourceError` con mensaje descriptivo

### Requirement: Omitir filas vacías
`SheetsSource` SHALL omitir silenciosamente las filas donde tanto `fullname` como `shortname` estén vacíos.

#### Scenario: Fila completamente vacía
- **WHEN** una fila tiene `Course name (Spanish)` y `CODE` ambos vacíos
- **THEN** la fila se omite sin error ni warning

#### Scenario: Fila con solo uno de los dos campos requeridos
- **WHEN** una fila tiene `Course name (Spanish)` vacío pero `CODE` presente, o viceversa
- **THEN** se emite un warning en el log indicando qué campo falta y el número de fila
- **THEN** la fila se omite

### Requirement: Fallo si no hay ningún curso válido
`SheetsSource` SHALL lanzar `SourceError` si tras procesar todas las filas no se obtuvo ningún `CourseSpec` válido.

#### Scenario: Sheet sin filas válidas
- **WHEN** todas las filas del Sheet están vacías o son inválidas
- **THEN** `load()` lanza `SourceError` con mensaje indicando que no se encontraron cursos

### Requirement: Errores de autenticación y acceso al Sheet
`SheetsSource` SHALL lanzar `SourceError` con mensaje claro ante fallos de autenticación Google o acceso al spreadsheet/worksheet.

#### Scenario: Archivo de credenciales no encontrado
- **WHEN** `credentials_file` no existe en disco
- **THEN** `load()` lanza `SourceError` indicando el problema de autenticación

#### Scenario: Spreadsheet no encontrado
- **WHEN** el `spreadsheet_id` no existe o el Service Account no tiene acceso
- **THEN** `load()` lanza `SourceError` con el ID del spreadsheet

#### Scenario: Worksheet no encontrada
- **WHEN** el nombre de worksheet no existe en el spreadsheet
- **THEN** `load()` lanza `SourceError` indicando el nombre de worksheet buscado
