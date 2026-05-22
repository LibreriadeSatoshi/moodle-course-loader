## 1. OAuth scope upgrade

- [x] 1.1 Cambiar el scope en `_auth_with_adc()` de `cloud-platform` a `https://www.googleapis.com/auth/spreadsheets`
- [x] 1.2 Actualizar el README — instrucciones para borrar `authorized_user.json` y re-autenticar
- [x] 1.3 Actualizar `.gitignore` si es necesario (ya incluye `authorized_user.json`)

## 2. SheetsSource — row map y write-back

- [x] 2.1 Durante `load()`, construir `self._row_map: dict[str, int]` mapeando `shortname → row_number` (fila real en el Sheet, 1-based contando la cabecera)
- [x] 2.2 Guardar referencia `self._ws` al worksheet tras `_fetch_rows()`
- [x] 2.3 Detectar el índice de columna de `Moodle Link` en la cabecera durante `load()`
- [x] 2.4 Implementar `write_moodle_link(shortname: str, url: str) -> None` — busca en `_row_map`, actualiza la celda, loguea warning si falla o si el shortname no está en el mapa

## 3. CLI — write-back tras creación

- [x] 3.1 Añadir flag `--no-writeback` (default: False) al comando `load-sheets`
- [x] 3.2 Tras `loader.load_specs(specs)`, iterar resultados y llamar `source.write_moodle_link()` para cada `status="created"` (salvo `--no-writeback`)
- [x] 3.3 Construir la URL como `f"{settings.moodle_url}/course/view.php?id={r.course_id}"`

## 4. Tests

- [x] 4.1 Test: `write_moodle_link` actualiza la celda correcta cuando el shortname está en el mapa
- [x] 4.2 Test: `write_moodle_link` loguea warning cuando el shortname no está en el mapa
- [x] 4.3 Test: excepción en la escritura loguea warning sin propagar el error
