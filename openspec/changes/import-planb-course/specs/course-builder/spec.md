## ADDED Requirements

### Requirement: Comando CLI `import-planb`
La aplicación SHALL exponer un comando `moodle-loader import-planb <course_path>` que importa un curso Plan ₿ desde un directorio local a Moodle.

Opciones:
- `--shortname X` (opcional): sobrescribe el shortname por defecto (nombre del directorio).
- `--dry-run` (opcional): parsea y valida sin llamar a Moodle.
- `--visible` (opcional): crea el curso con `visible=True`. Default: `False`.

#### Scenario: Invocación normal
- **WHEN** el usuario ejecuta `moodle-loader import-planb /path/to/btc101`
- **THEN** se crea (o re-crea) el curso en Moodle y se imprime un resumen con `course_id`, número de secciones y páginas creadas

#### Scenario: Dry-run
- **WHEN** el usuario ejecuta `moodle-loader import-planb /path/to/btc101 --dry-run`
- **THEN** el comando parsea el directorio, imprime un resumen (partes, capítulos, assets) y termina con código 0 sin abrir cliente Moodle

#### Scenario: Path inválido
- **WHEN** el `course_path` no existe o no es directorio
- **THEN** el comando termina con código distinto de 0 y un mensaje claro

### Requirement: Wipe-and-reload por shortname
`PlanBCourseBuilder` SHALL borrar el curso existente con el mismo `shortname` antes de crear el nuevo, si existe.

#### Scenario: Curso con ese shortname ya existe
- **WHEN** `build()` se invoca y `get_course_by_shortname(shortname)` devuelve un curso
- **THEN** se llama a `delete_course(existing.id)` antes de continuar

#### Scenario: Shortname no existe
- **WHEN** `get_course_by_shortname(shortname)` devuelve `None`
- **THEN** no se llama a `delete_course` y el flujo continúa directamente con la creación

#### Scenario: Borrado falla
- **WHEN** `delete_course` devuelve un `MoodleAPIError`
- **THEN** `build()` propaga el error sin intentar crear el curso nuevo

### Requirement: Crear el curso vía `core_course_create_courses`
`PlanBCourseBuilder` SHALL crear el curso en Moodle con `fullname`, `shortname`, `summary` y `categoryid` derivados del `PlanBCourseSpec` y la configuración.

#### Scenario: Creación exitosa
- **WHEN** se llama a `_create_course()` con un spec válido
- **THEN** se invoca `core_course_create_courses` con los campos correctos
- **THEN** se almacena el `course_id` devuelto en el estado del builder

#### Scenario: Resolución de categoría
- **WHEN** se construye un curso
- **THEN** se resuelve `category_id` consultando `client.get_categories()` con `DEFAULT_CATEGORY_NAME`
- **THEN** si la categoría no existe, se usa ID `1` como fallback y se loguea warning

### Requirement: Embeber assets como data URIs
`PlanBCourseBuilder` SHALL construir un mapa `{ruta_relativa → data_uri}` antes de crear cualquier página, leyendo cada `PlanBAsset` del disco y codificándolo en base64.

`local_moodlecourseloader_create_page` almacena el HTML sin área de archivos asociada, por lo que las imágenes se incrustan como data URIs (`data:<mime>;base64,<b64>`) para garantizar que se visualicen correctamente en Moodle sin depender de rutas externas.

#### Scenario: Varios assets
- **WHEN** el spec contiene 5 assets únicos
- **THEN** el mapa resultante contiene 5 entradas, cada una con un data URI válido
- **THEN** no se realiza ninguna llamada de subida de archivos para el contenido de páginas

#### Scenario: Sin assets
- **WHEN** el spec no tiene assets
- **THEN** el mapa queda vacío y ninguna página contiene data URIs

### Requirement: Crear una sección por Parte
`PlanBCourseBuilder` SHALL crear/actualizar una sección de Moodle por cada `PlanBPart` del spec, usando el título de la Parte como nombre de la sección.

#### Scenario: Mapeo Parte → sección
- **WHEN** el spec tiene 6 partes
- **THEN** se crean/actualizan 6 secciones en el curso, con números de sección 1..6 (sección 0 es la general de Moodle, reservada)
- **THEN** el nombre de cada sección coincide con `PlanBPart.title`

### Requirement: Crear una página por Capítulo
`PlanBCourseBuilder` SHALL crear una actividad Page por cada `PlanBChapter`, dentro de la sección correspondiente a su Parte.

#### Scenario: Mapeo Capítulo → Page
- **WHEN** una Parte (sección N) contiene 4 capítulos
- **THEN** se crean 4 actividades Page en la sección N
- **THEN** el nombre de cada Page es `PlanBChapter.title`
- **THEN** el contenido de cada Page es el body del capítulo convertido a HTML

#### Scenario: Reescritura de URLs de assets en el contenido
- **WHEN** el body de un capítulo contiene `![image](assets/en/001.webp)`
- **THEN** el HTML resultante incrusta el asset como data URI (`data:image/webp;base64,...`), no la ruta original

#### Scenario: Eliminación de tags Plan ₿ en el contenido
- **WHEN** el body contiene `<partId>...</partId>` o `<chapterId>...</chapterId>`
- **THEN** esas tags se eliminan antes de convertir a HTML y no aparecen en el contenido subido

### Requirement: Renderizado de tablas Markdown (GFM)
`PlanBCourseBuilder` SHALL convertir las tablas escritas en sintaxis de pipes (GFM) a HTML `<table>` al renderizar el body de un capítulo, en lugar de dejarlas como texto plano. El renderizador de Markdown SHALL tener habilitada la regla `table`, que markdown-it-py deja deshabilitada en el preset CommonMark por defecto.

Dado que Moodle almacena el HTML de la página tal cual y su tema no dibuja bordes de celda por defecto, `PlanBCourseBuilder` SHALL añadir estilos inline (atributos `style`) a la tabla y a sus celdas para que la rejilla sea visible. Cuando una celda ya tiene un `style` (p. ej. `text-align` por alineación de columna), el borde SHALL fusionarse con el estilo existente sin sobrescribirlo.

#### Scenario: Tabla en sintaxis de pipes
- **WHEN** el body de un capítulo contiene una tabla GFM (fila de cabecera, fila separadora `|---|---|` y filas de datos)
- **THEN** el HTML resultante contiene un elemento `<table>` con `<thead>`, `<tbody>` y celdas `<th>`/`<td>` con el contenido de cada columna
- **THEN** el HTML no deja la sintaxis de pipes cruda (`| ... |`) dentro de un párrafo `<p>`

#### Scenario: Bordes visibles en la tabla
- **WHEN** se renderiza una tabla GFM
- **THEN** el `<table>` lleva un `style` inline con `border-collapse: collapse`
- **THEN** cada celda `<th>`/`<td>` lleva un `style` inline con `border: 1px solid` y `padding`

#### Scenario: Alineación de columna preservada
- **WHEN** una columna usa alineación GFM (`:---:`, `---:`) y markdown-it emite `style="text-align:..."` en la celda
- **THEN** el estilo de borde se fusiona con el `text-align` existente y ambos se conservan en el mismo atributo `style`

#### Scenario: Contenido sin tablas no se ve afectado
- **WHEN** el body no contiene ninguna tabla
- **THEN** el HTML se renderiza igual que antes (la regla `table` no altera párrafos, listas, énfasis ni imágenes)

### Requirement: Fijar imagen del curso
`PlanBCourseBuilder` SHOULD fijar la imagen del curso usando el primer asset referenciado en la introducción, si existe.

#### Scenario: Introducción contiene una imagen
- **WHEN** la sección de introducción de `en.md` referencia `assets/en/001.webp` como primera imagen
- **THEN** tras crear el curso se llama a `local_moodlecourseloader_set_course_image` con ese asset

#### Scenario: Introducción sin imágenes
- **WHEN** la introducción no contiene ninguna referencia `![*](assets/en/*)`
- **THEN** no se llama a `set_course_image` y el curso queda con la imagen por defecto

### Requirement: Resultado estructurado de la construcción
`PlanBCourseBuilder.build()` SHALL devolver un `PlanBBuildResult` con `course_id`, `sections_created` (lista de ids/nombres), `pages_created` (lista de ids/títulos), `assets_uploaded` (count) y `wiped` (bool indicando si hubo borrado previo).

#### Scenario: Resultado de build exitoso
- **WHEN** `build()` termina sin error
- **THEN** devuelve un `PlanBBuildResult` con todos los campos poblados

#### Scenario: Resultado tras wipe
- **WHEN** existía un curso con el mismo shortname y fue borrado
- **THEN** el `PlanBBuildResult.wiped` es `True`
