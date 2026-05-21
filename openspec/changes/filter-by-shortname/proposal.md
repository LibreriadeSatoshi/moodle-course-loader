## Why

Cuando el Sheet tiene decenas de cursos, a veces solo se quiere cargar uno concreto — ya sea para probar, para recargar un curso fallido, o para añadir un curso nuevo sin tocar los demás. Hoy no hay forma de hacerlo sin modificar el Sheet temporalmente.

## What Changes

- Añadir opción `--shortname` a `load-sheets` (y `load`) para filtrar y cargar un único curso por su shortname
- Antes de duplicar, comprobar via API si ya existe un curso con ese shortname en Moodle — si existe, devolver status `skipped` con mensaje explicativo en lugar de intentar la creación y fallar
- La comprobación de existencia también se aplica cuando no se usa `--shortname` (protección general contra duplicados)

## Capabilities

### New Capabilities

- `shortname-filter`: Filtrado por shortname en el comando de carga, permitiendo cargar un único curso del conjunto
- `duplicate-check`: Comprobación previa de existencia del shortname en Moodle antes de intentar duplicar

### Modified Capabilities

_(ninguna — los requisitos existentes no cambian, solo se añade comportamiento nuevo)_

## Impact

- **`src/moodle_loader/cli.py`**: nueva opción `--shortname` en `load-sheets` y `load`
- **`src/moodle_loader/client.py`**: nuevo método `get_course_by_shortname()` usando `core_course_get_courses_by_field`
- **`src/moodle_loader/loader.py`**: comprobar existencia antes de duplicar; devolver `skipped` si ya existe
- **`tests/`**: tests para el filtro y la comprobación de duplicados
