## ADDED Requirements

### Requirement: Parsear directorio de curso Plan ₿
`PlanBSource` SHALL aceptar una ruta a un directorio de curso Plan ₿ y devolver un `PlanBCourseSpec` que represente el curso en inglés.

El directorio MUST contener:
- `course.yml` (metadatos)
- `en.md` (contenido completo del curso)
- `assets/en/` (opcional; imágenes referenciadas desde `en.md`)

#### Scenario: Directorio válido
- **WHEN** `PlanBSource(Path("courses/btc101")).load()` se invoca
- **THEN** devuelve un `PlanBCourseSpec` con `fullname`, `summary`, `parts` (lista de `PlanBPart`) y `assets` (lista deduplicada de `PlanBAsset`)

#### Scenario: Falta `course.yml`
- **WHEN** el directorio no contiene `course.yml`
- **THEN** `load()` lanza `SourceError` indicando el archivo faltante

#### Scenario: Falta `en.md`
- **WHEN** el directorio no contiene `en.md`
- **THEN** `load()` lanza `SourceError` indicando que el contenido en inglés no existe

### Requirement: Separar contenido en Partes
`PlanBSource` SHALL dividir el contenido de `en.md` (tras el frontmatter) en Partes separadas por la secuencia `\n+++\n` y crear un `PlanBPart` por cada bloque excepto el primero (que es la introducción del curso).

#### Scenario: Múltiples partes
- **WHEN** `en.md` contiene N separadores `+++` después de la introducción
- **THEN** `PlanBCourseSpec.parts` tiene N elementos en orden de aparición

#### Scenario: Una sola parte sin separadores
- **WHEN** `en.md` contiene contenido pero ningún `+++`
- **THEN** `PlanBCourseSpec.parts` está vacío y todo el contenido se asigna a `PlanBCourseSpec.intro`

#### Scenario: Título y partId de cada parte
- **WHEN** un bloque de Parte empieza con `# <título>` y contiene `<partId>UUID</partId>`
- **THEN** el `PlanBPart` resultante tiene `title=<título>` y `part_id=UUID`

#### Scenario: PartId ausente
- **WHEN** un bloque de Parte no contiene `<partId>...</partId>`
- **THEN** `part_id` se sintetiza como UUIDv5 deterministico desde el slug del título

### Requirement: Separar Partes en Capítulos
`PlanBSource` SHALL dividir el cuerpo de cada Parte en Capítulos delimitados por encabezados de segundo nivel (`## ` al inicio de línea).

#### Scenario: Capítulos en una parte
- **WHEN** una Parte contiene 3 encabezados `## <título>` con sus correspondientes `<chapterId>`
- **THEN** la Parte tiene 3 `PlanBChapter`, cada uno con `title`, `chapter_id` y `body`

#### Scenario: Body del capítulo
- **WHEN** se extrae el body de un capítulo
- **THEN** incluye todo el contenido desde después del `<chapterId>` hasta el siguiente `##` (o el final de la parte) sin incluir el encabezado siguiente

#### Scenario: ChapterId ausente
- **WHEN** un capítulo no contiene `<chapterId>...</chapterId>`
- **THEN** `chapter_id` se sintetiza como UUIDv5 deterministico desde el slug del título

#### Scenario: Encabezados de tercer nivel y más profundos
- **WHEN** el body del capítulo contiene `### Subsection`
- **THEN** el `###` y siguientes permanecen como parte del body sin disparar nueva división

### Requirement: Detectar y deduplicar assets
`PlanBSource` SHALL escanear el cuerpo de la introducción y de todos los capítulos buscando referencias `![<alt>](assets/en/<file>)` y construir una lista única de `PlanBAsset(relative_path, absolute_path)`.

#### Scenario: Asset referenciado en múltiples capítulos
- **WHEN** la misma ruta `assets/en/001.webp` aparece en 3 capítulos diferentes
- **THEN** `PlanBCourseSpec.assets` contiene una sola entrada para esa ruta

#### Scenario: Asset no existe en disco
- **WHEN** una referencia apunta a `assets/en/missing.webp` y el archivo no existe
- **THEN** `load()` lanza `SourceError` indicando la ruta faltante

#### Scenario: Asset fuera del directorio del curso
- **WHEN** una referencia es absoluta o usa `..` para salir del directorio del curso
- **THEN** `load()` lanza `SourceError` por ruta inválida

### Requirement: Metadatos básicos del curso desde `course.yml` y frontmatter
`PlanBSource` SHALL combinar el frontmatter de `en.md` (`name`, `goal`, `objectives`) y el `course.yml` para poblar `fullname` y `summary` del `PlanBCourseSpec`.

Mapeo v1:
- `fullname` ← frontmatter `name`
- `summary` ← frontmatter `goal` + lista de `objectives` formateada como HTML/markdown
- `default_shortname` ← nombre del directorio del curso (e.g. `btc101`)

#### Scenario: Frontmatter presente
- **WHEN** `en.md` tiene un bloque `---...---` con `name: "..."`, `goal: "..."` y `objectives: [...]`
- **THEN** `PlanBCourseSpec.fullname == name` y `PlanBCourseSpec.summary` incluye `goal` y los `objectives` enumerados

#### Scenario: Frontmatter parcial
- **WHEN** `name` está pero `goal` y `objectives` faltan
- **THEN** `fullname` se rellena y `summary` queda vacío sin error

#### Scenario: Frontmatter ausente
- **WHEN** `en.md` no tiene frontmatter
- **THEN** `load()` lanza `SourceError` indicando que falta `name` del curso

### Requirement: Idempotencia del parseo
`PlanBSource.load()` MUST ser idempotente: invocaciones repetidas sobre el mismo directorio devuelven el mismo `PlanBCourseSpec` (mismos UUIDs sintéticos, mismo orden de partes/capítulos, mismo orden de assets).

#### Scenario: Dos invocaciones consecutivas
- **WHEN** se llama `load()` dos veces sin modificar el directorio
- **THEN** los dos `PlanBCourseSpec` resultantes son iguales campo a campo
