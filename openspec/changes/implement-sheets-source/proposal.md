## Why

El equipo gestiona la programación de cursos en un Google Sheet centralizado. Introducir cursos manualmente en Moodle desde esa hoja es lento y propenso a errores. Implementar `SheetsSource` elimina ese trabajo manual permitiendo cargar cursos directamente desde el Sheet.

## What Changes

- Implementar `SheetsSource` (actualmente stub) para leer cursos desde Google Sheets via `gspread`
- Añadir `get_categories()` al `MoodleClient` para resolver nombres de categoría a IDs dinámicamente
- Añadir `DEFAULT_TEMPLATE_ID` y `DEFAULT_CATEGORY_NAME` a `Settings` como variables configurables desde `.env`
- Añadir comando CLI `moodle-loader load-sheets <spreadsheet_id>` para invocar la nueva fuente

## Capabilities

### New Capabilities

- `sheets-source`: Lectura de `CourseSpec` desde Google Sheets con resolución dinámica de categorías y fallback configurable

### Modified Capabilities

- `moodle-client`: Se añade `get_categories()` para consultar categorías via API (extensión sin cambio de requisitos existentes)

## Impact

- **`src/moodle_loader/sources/sheets_source.py`**: implementación completa
- **`src/moodle_loader/client.py`**: nuevo método `get_categories()`
- **`src/moodle_loader/config.py`**: dos nuevos campos con defaults
- **`src/moodle_loader/cli.py`**: nuevo comando `load-sheets`
- **`.env.example`**: documentar nuevas variables
- **Dependencia nueva**: `gspread>=6.0` + `google-auth>=2.27` (ya en extras opcionales `[sheets]`)
- **Requiere**: archivo `credentials.json` de Google Service Account en el directorio de trabajo
