## 1. Dependencias y configuración

- [ ] 1.1 Añadir `markdown-it-py>=3.0` y `python-frontmatter>=1.1` a `pyproject.toml` (dependencias base)
- [ ] 1.2 Verificar que `PyYAML` está disponible (ya transitivo vía `python-frontmatter`)
- [ ] 1.3 Documentar en README la nueva subcomanda `import-planb` y su naturaleza destructiva

## 2. Modelos

- [ ] 2.1 Añadir `PlanBAsset`, `PlanBChapter`, `PlanBPart`, `PlanBCourseSpec` y `PlanBBuildResult` a `models.py`
- [ ] 2.2 Tests unitarios de validación pydantic (campos requeridos, defaults)

## 3. Parser Plan ₿ (`PlanBSource`)

- [ ] 3.1 Crear `src/moodle_loader/sources/planb_source.py` con clase `PlanBSource(course_path: Path)`
- [ ] 3.2 Implementar `_load_course_yml()` que lee `course.yml` y devuelve un dict
- [ ] 3.3 Implementar `_parse_en_md()` que separa frontmatter, intro, y bloques `+++`
- [ ] 3.4 Implementar `_split_chapters(part_body)` que detecta encabezados `##` y extrae `<chapterId>` siguientes
- [ ] 3.5 Implementar `_extract_assets(body)` que devuelve lista de rutas relativas referenciadas
- [ ] 3.6 Implementar `load()` que devuelve un `PlanBCourseSpec` completo (con assets deduplicados)
- [ ] 3.7 Sintetizar UUIDs deterministas (UUIDv5 desde slug del título) cuando falten `<partId>` / `<chapterId>`
- [ ] 3.8 Exponer `PlanBSource` desde `sources/__init__.py`

## 4. Extensiones del cliente Moodle

- [ ] 4.1 `MoodleClient.create_course(*, fullname, shortname, categoryid, summary, visible) -> dict`
- [ ] 4.2 `MoodleClient.upload_file(*, contextid, component, filearea, itemid, filepath, filename, filecontent_base64) -> dict`
- [ ] 4.3 `MoodleClient.set_course_image(course_id, draft_item_id) -> Any` (vía `local_moodlecourseloader_set_course_image`)
- [ ] 4.4 `MoodleClient.update_section(course_id, section_number, name, summary, summaryformat) -> Any` (vía `local_moodlecourseloader_update_section`)
- [ ] 4.5 `MoodleClient.create_page(course_id, section_number, name, content, contentformat) -> Any` (vía `local_moodlecourseloader_create_page`)
- [ ] 4.6 Confirmar firmas reales de las WS functions del plugin contra `db/services.php` del plugin antes de mergear
- [ ] 4.7 Tests con `responses` o stub HTTP para cada método nuevo

## 5. Orquestador (`PlanBCourseBuilder`)

- [ ] 5.1 Crear `src/moodle_loader/builder.py` con clase `PlanBCourseBuilder(client, spec)`
- [ ] 5.2 Implementar `_wipe_existing(shortname)` que borra el curso si existe
- [ ] 5.3 Implementar `_create_course(spec, category_id)` que llama a `create_course`
- [ ] 5.4 Implementar `_upload_assets(course_id, assets)` y devolver mapa `{ruta → url}`
- [ ] 5.5 Implementar `_render_chapter_html(chapter, asset_url_map)`: limpia tags Plan ₿, convierte markdown a HTML, reescribe URLs
- [x] 5.5b Habilitar la regla `table` en el renderizador markdown-it para que las tablas GFM (sintaxis de pipes) se conviertan a HTML `<table>`
- [ ] 5.6 Implementar `_create_sections(course_id, parts)`
- [ ] 5.7 Implementar `_create_pages(course_id, parts, asset_url_map)`
- [ ] 5.8 Implementar `_set_image(course_id, asset_url_map)` (primer asset de la intro, si existe)
- [ ] 5.9 Implementar `build() -> PlanBBuildResult` con orquestación completa y resumen
- [ ] 5.10 Resolver categoría desde `DEFAULT_CATEGORY_NAME` con fallback a ID 1

## 6. CLI

- [ ] 6.1 Añadir comando `import-planb` en `cli.py` con args `course_path`, `--shortname`, `--dry-run`, `--visible`
- [ ] 6.2 Modo `--dry-run`: parsea + imprime resumen (partes, capítulos, assets) sin abrir cliente
- [ ] 6.3 Modo normal: instancia cliente, invoca `PlanBCourseBuilder`, imprime tabla resultados

## 7. Tests

- [ ] 7.1 Test parser: fixture mínimo (1 parte, 2 capítulos, 1 asset) → `PlanBCourseSpec` correcto
- [ ] 7.2 Test parser: `btc101` real → cuenta esperada de partes (6) y capítulos (≥20)
- [ ] 7.3 Test parser: UUIDs faltantes se sintetizan deterministamente
- [ ] 7.4 Test parser: assets se deduplican entre capítulos
- [x] 7.4b Test `_render_html`: tabla GFM en pipes → `<table>`/`<thead>`/`<tbody>`/`<td>`, sin pipes crudos en `<p>`
- [ ] 7.5 Test builder con `MoodleClient` mockeado: secuencia correcta de llamadas
- [ ] 7.6 Test builder: wipe llama a `delete_course` solo si existe el shortname
- [ ] 7.7 Test builder: imagen de curso se omite si no hay assets en la intro
- [ ] 7.8 Test CLI `import-planb --dry-run` no invoca cliente
- [ ] 7.9 Test CLI `import-planb`: salida de tabla con sección creadas y páginas creadas

## 8. Documentación

- [ ] 8.1 Actualizar README con sección "Importing Plan ₿ courses" (uso, requisitos, advertencia destructiva)
- [ ] 8.2 Actualizar `Layout` del README con `planb_source.py` y `builder.py`
