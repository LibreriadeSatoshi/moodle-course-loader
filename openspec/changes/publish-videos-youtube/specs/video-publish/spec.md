## ADDED Requirements

### Requirement: Comando CLI `publish-videos`
La aplicación SHALL exponer un comando `moodle-loader publish-videos` que sube a una cuenta de YouTube, como vídeos **no listados**, los MP4 archivados que figuran en el manifiesto y aún no se han publicado, y registra el `youtube_id` resultante en el manifiesto.

Opciones:
- `--manifest PATH` (opcional): ruta del manifiesto YAML. Default `video_manifest.yml`.
- `--limit N` (opcional): número máximo de subidas en esta ejecución.
- `--privacy LEVEL` (opcional): privacidad de la subida. Default `unlisted`.
- `--force` (opcional): re-sube entradas que ya tienen `youtube_id`.
- `--client-secrets PATH` / `--token PATH` (opcional): credenciales OAuth.

#### Scenario: Invocación normal
- **WHEN** el usuario ejecuta `moodle-loader publish-videos`
- **THEN** se suben los vídeos descargados aún sin `youtube_id`, como no listados, y el manifiesto queda con su `youtube_id` y `status: uploaded`
- **THEN** se imprime un resumen con subidos, omitidos, pendientes y fallidos

#### Scenario: Credenciales ausentes
- **WHEN** no hay credenciales OAuth válidas/refrescables
- **THEN** el comando termina con código ≠ 0 y un mensaje claro de cómo configurarlas

### Requirement: Selección de vídeos pendientes desde el manifiesto
`publish-videos` SHALL tomar como cola de trabajo las entradas del manifiesto con `status: downloaded` y sin `youtube_id`. Las entradas sin `mp4` existente en disco SHALL marcarse/avisarse y no abortar el lote.

#### Scenario: Sólo se publican los descargados pendientes
- **WHEN** el manifiesto mezcla entradas `uploaded`, `downloaded` y `failed`
- **THEN** sólo se intentan subir las `downloaded` sin `youtube_id`

#### Scenario: MP4 archivado ausente
- **WHEN** una entrada pendiente apunta a un `mp4` que no existe en disco
- **THEN** se avisa/marca como fallida y el lote continúa con el resto

### Requirement: Subida a YouTube como no listado con atribución
Para cada vídeo pendiente, `publish-videos` SHALL subir su MP4 vía la YouTube Data API v3 (subida reanudable) con `privacyStatus` no listado (por defecto), `embeddable: true`, idioma `en`, y una descripción con atribución a Plan ₿, enlace al original (`source_url`) y la licencia CC BY-SA 4.0.

#### Scenario: Subida correcta
- **WHEN** la API acepta la subida de un MP4
- **THEN** se obtiene un `youtube_id` y se registra en el manifiesto junto a `uploaded_at` y `status: uploaded`
- **THEN** el vídeo queda como no listado y embebible

#### Scenario: Privacidad configurable
- **WHEN** se pasa `--privacy private` (o `public`)
- **THEN** la subida usa esa privacidad en lugar de `unlisted`

### Requirement: Idempotencia y registro del mapeo
`publish-videos` SHALL omitir las entradas que ya tengan `youtube_id`, salvo `--force`. El manifiesto SHALL guardarse de forma atómica **tras cada subida** para no perder progreso ni duplicar subidas ante una interrupción.

#### Scenario: Segunda ejecución sin cambios
- **WHEN** se ejecuta el comando dos veces seguidas sin `--force`
- **THEN** la segunda no vuelve a subir los vídeos con `youtube_id` y los reporta como omitidos

#### Scenario: Re-subida forzada
- **WHEN** se ejecuta con `--force` sobre una entrada con `youtube_id`
- **THEN** el vídeo se vuelve a subir y el `youtube_id` se actualiza al nuevo

#### Scenario: Persistencia incremental
- **WHEN** se suben varios vídeos en una ejecución
- **THEN** el manifiesto se actualiza tras cada subida (no sólo al final)

### Requirement: Consciencia de cuota y reanudación
`publish-videos` SHALL respetar `--limit` y SHALL detenerse con gracia ante un error de cuota de la API (`quotaExceeded` / `uploadLimitExceeded`), dejando persistido lo ya subido y permitiendo continuar en una ejecución posterior.

#### Scenario: Límite por ejecución
- **WHEN** hay 10 pendientes y se ejecuta con `--limit 3`
- **THEN** se suben 3 y las 7 restantes quedan pendientes en el manifiesto

#### Scenario: Cuota agotada a mitad de lote
- **WHEN** la API devuelve `quotaExceeded` tras subir algunas
- **THEN** el comando se detiene con gracia, las subidas ya hechas quedan registradas y se indica reanudar más tarde
- **THEN** una ejecución posterior continúa con las pendientes
