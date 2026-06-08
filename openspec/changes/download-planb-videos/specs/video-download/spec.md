## ADDED Requirements

### Requirement: Comando CLI `download-videos`
La aplicación SHALL exponer un comando `moodle-loader download-videos <courses_root>` que descarga, como MP4, los vídeos PeerTube en inglés referenciados por los `course.yml` bajo `<courses_root>`, y los registra en un manifiesto.

Opciones:
- `--manifest PATH` (opcional): ruta del manifiesto YAML. Default `video_manifest.yml`.
- `--archive-dir DIR` (opcional): directorio donde guardar los MP4. Default `videos/`.
- `--lang LANG` (opcional): idioma a descargar. En v1 sólo se admite `en`.
- `--force` (opcional): re-descarga vídeos ya descargados.
- `--only <uuid> ...` (opcional): limita la descarga a los UUID Plan ₿ indicados.

#### Scenario: Invocación normal
- **WHEN** el usuario ejecuta `moodle-loader download-videos /path/to/courses`
- **THEN** se descargan los vídeos PeerTube `en` aún no archivados, se escriben sus MP4 en el directorio de archivo y se actualiza el manifiesto
- **THEN** se imprime un resumen con descargados, omitidos y fallidos

#### Scenario: `ffmpeg` ausente
- **WHEN** `ffmpeg` no está en el `PATH`
- **THEN** el comando termina con código ≠ 0 y un mensaje claro antes de intentar descargas

#### Scenario: Idioma no soportado
- **WHEN** se pasa `--lang` distinto de `en`
- **THEN** el comando avisa de que en v1 sólo se soporta inglés y no descarga otros idiomas

### Requirement: Enumeración de vídeos PeerTube desde `course.yml`
`download-videos` SHALL escanear cada `course.yml` bajo `<courses_root>`, leer su bloque `videos:` y seleccionar las entradas que tengan una pista `peertube` en el idioma objetivo (`en`). Las entradas sólo-YouTube SHALL ignorarse. Los vídeos SHALL deduplicarse por UUID Plan ₿.

#### Scenario: Mezcla de proveedores
- **WHEN** un `course.yml` tiene vídeos peertube-only, youtube-only y mixtos
- **THEN** sólo se consideran para descarga los que tienen pista `peertube[en]` (los mixtos incluidos)
- **THEN** los youtube-only no entran al manifiesto

#### Scenario: Vídeo peertube sin pista en inglés
- **WHEN** un vídeo tiene `peertube` pero sin entrada `en`
- **THEN** se omite con un warning y no se descarga

#### Scenario: Mismo UUID en varios cursos
- **WHEN** el mismo UUID aparece en más de un `course.yml`
- **THEN** se descarga una sola vez (deduplicado)

### Requirement: Seleccionar la resolución nativa (máxima) del vídeo
`download-videos` SHALL descargar la variante de **mayor resolución** disponible. Como el master HLS de PeerTube lista las variantes en orden ascendente (144p → 240p → 360p…), `download-videos` SHALL parsear el master, elegir la variante con mayor área de píxeles (`RESOLUTION=<w>x<h>`), resolver su URI relativa contra la del master, y descargar esa media playlist. La altura elegida SHALL registrarse en el manifiesto (`resolution`, p. ej. `360p`).

#### Scenario: Varias variantes en el master
- **WHEN** el master ofrece variantes 144p, 240p y 360p
- **THEN** se descarga la de 360p (no la primera/menor) y `resolution` queda en `360p`

#### Scenario: Master sin variantes
- **WHEN** el master no contiene líneas `#EXT-X-STREAM-INF` con `RESOLUTION`
- **THEN** se usa la URL del master tal cual y `resolution` queda sin definir

#### Scenario: URI de variante relativa
- **WHEN** la variante elegida es una URI relativa (p. ej. `…-360.m3u8`)
- **THEN** se resuelve contra la URL del master para obtener una URL absoluta

### Requirement: Descarga y remux a MP4
Para cada vídeo seleccionado, `download-videos` SHALL resolver la media playlist de mayor resolución (ver requisito anterior) y remuxarla a un fichero MP4 con `ffmpeg` sin recodificar.

#### Scenario: Remux correcto
- **WHEN** la variante elegida es una media playlist `.m3u8` válida
- **THEN** se genera `<archive-dir>/<uuid>.<lang>.mp4` mediante `ffmpeg ... -c copy`
- **THEN** la entrada del manifiesto queda con `status: downloaded`, `mp4`, `sha256`, `bytes` y `resolution`

#### Scenario: Fallo de descarga/remux
- **WHEN** la API no responde, no hay `streamingPlaylists`, no se puede obtener el master, o `ffmpeg` devuelve error
- **THEN** la entrada se marca `status: failed` con el motivo logueado
- **THEN** el lote continúa con el resto y el comando termina con código ≠ 0

### Requirement: Manifiesto de vídeos indexado por UUID Plan ₿
`download-videos` SHALL mantener un manifiesto YAML indexado por el UUID Plan ₿ del vídeo (la clave usada en `:::video id=UUID:::`). Por entrada descargada SHALL registrar al menos: `peertube_id`, `lang`, `title`, `resolution`, `mp4` (ruta relativa al manifiesto), `sha256`, `bytes`, `status` y `source_url`.

El manifiesto SHALL guardarse de forma atómica (fichero temporal + rename) para no corromperse ante interrupciones.

#### Scenario: Creación del manifiesto
- **WHEN** el manifiesto no existe en la ruta indicada
- **THEN** se crea con las entradas de los vídeos descargados

#### Scenario: Actualización incremental
- **WHEN** el manifiesto ya tiene entradas de una ejecución anterior
- **THEN** una nueva ejecución añade/actualiza entradas sin perder las existentes

### Requirement: Fichero de metadatos por vídeo
Por cada vídeo descargado, `download-videos` SHALL escribir un fichero de metadatos `{uuid}.yml` (donde `{uuid}` es el UUID Plan ₿) junto al MP4 en el directorio de archivo, con la información del vídeo obtenida de la API de PeerTube. El fichero SHALL incluir al menos:

- `title` — título del vídeo
- `description` — descripción completa (campo `description` de la API, que ya es el texto completo; `truncatedDescription` es la versión corta y no se usa)
- `license` — licencia (etiqueta)
- `language` — idioma del vídeo
- `category` — categoría (si existe)
- `tags` — etiquetas (si existen)
- `channel` / `author` — canal o cuenta de origen
- `duration` — duración en segundos
- `peertube_id` y `source_url` — id y URL original en PeerTube
- `resolution` — resolución descargada (p. ej. `360p`)
- `published_at` — fecha de publicación (si existe)

El fichero se escribe en la descarga (y se sobrescribe con `--force`); en una omisión idempotente no se reescribe.

#### Scenario: Metadatos creados junto al MP4
- **WHEN** se descarga un vídeo con UUID `<uuid>`
- **THEN** se crea `<archive-dir>/<uuid>.yml` con `title`, `description`, `license` y los demás campos
- **THEN** el MP4 y su `{uuid}.yml` quedan en el mismo directorio

#### Scenario: Descripción completa (no truncada)
- **WHEN** la API devuelve `description` (completa) y `truncatedDescription` (corta)
- **THEN** el fichero de metadatos usa la `description` completa, no `truncatedDescription`

#### Scenario: Re-descarga forzada sobrescribe metadatos
- **WHEN** se ejecuta con `--force` sobre un vídeo ya descargado
- **THEN** su `{uuid}.yml` se regenera con los metadatos actuales

#### Scenario: Omisión idempotente no reescribe metadatos
- **WHEN** un vídeo se omite por estar ya descargado (sin `--force`)
- **THEN** su `{uuid}.yml` no se reescribe

### Requirement: Idempotencia de la descarga
`download-videos` SHALL omitir cualquier vídeo cuyo manifiesto indique `status: downloaded`, cuyo fichero `mp4` exista en disco y cuyo `sha256` coincida; `--force` SHALL forzar la re-descarga.

#### Scenario: Segunda ejecución sin cambios
- **WHEN** se ejecuta el comando dos veces seguidas sin `--force`
- **THEN** la segunda no invoca `ffmpeg` para los vídeos ya descargados y los reporta como omitidos

#### Scenario: Re-descarga forzada
- **WHEN** se ejecuta con `--force`
- **THEN** los vídeos ya descargados se vuelven a descargar y sus MP4 se sobrescriben

#### Scenario: Fichero archivado ausente o corrupto
- **WHEN** el manifiesto dice `downloaded` pero el `mp4` no existe o su `sha256` no coincide
- **THEN** el vídeo se vuelve a descargar aunque no se pase `--force`
