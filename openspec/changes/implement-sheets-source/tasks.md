## 1. Configuración y dependencias

- [x] 1.1 Añadir `DEFAULT_TEMPLATE_ID` y `DEFAULT_CATEGORY_NAME` a `Settings` en `config.py`
- [x] 1.2 Actualizar `.env.example` con las nuevas variables y sus valores por defecto
- [x] 1.3 Verificar que `gspread` y `google-auth` están en los extras `[sheets]` de `pyproject.toml`

## 2. Cliente Moodle

- [x] 2.1 Añadir método `get_categories()` a `MoodleClient` que llame a `core_course_category_get_categories`
- [x] 2.2 Añadir test para `get_categories()` en `test_client.py`

## 3. Implementación de SheetsSource

- [x] 3.1 Implementar `SheetsSource.__init__` con parámetros: `spreadsheet_id`, `client`, `settings`, `worksheet`, `credentials_file`
- [x] 3.2 Implementar `_build_category_map()` usando `client.get_categories()`
- [x] 3.3 Implementar `_resolve_category()` con fallback a `DEFAULT_CATEGORY_NAME` y warning en log
- [x] 3.4 Implementar `_fetch_rows()` con autenticación Service Account y manejo de errores de acceso
- [x] 3.5 Implementar `load()` con skip de filas vacías, warnings por campos faltantes y construcción de `CourseSpec`

## 4. CLI

- [x] 4.1 Añadir comando `load-sheets <spreadsheet_id>` en `cli.py` con opciones `--worksheet`, `--credentials-file` y `--dry-run`

## 5. Tests

- [x] 5.1 Test: carga exitosa con todas las columnas presentes
- [x] 5.2 Test: `template_id` vacío usa `DEFAULT_TEMPLATE_ID`
- [x] 5.3 Test: `Path` desconocido hace fallback a `DEFAULT_CATEGORY_NAME` y loguea warning
- [x] 5.4 Test: `Path` desconocido y default también inexistente lanza `SourceError`
- [x] 5.5 Test: filas vacías se omiten silenciosamente
- [x] 5.6 Test: sin filas válidas lanza `SourceError`
- [x] 5.7 Test: error de autenticación Google lanza `SourceError`
