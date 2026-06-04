## ADDED Requirements

### Requirement: Embeber vídeos Plan ₿ en la página del Capítulo
Al renderizar el body de un Capítulo a HTML, `PlanBCourseBuilder` SHALL reconocer las dos sintaxis de vídeo de Plan ₿ y sustituirlas por un reproductor embebido (`<iframe>`), en lugar de dejar texto crudo o un `<img>` roto.

Las dos sintaxis son:
- **Directiva interna**: `:::video id=<UUID>:::`, resuelta contra `PlanBCourseSpec.videos`.
- **Imagen markdown a YouTube**: `![<alt>](<url>)` donde `<url>` es una URL de YouTube (`youtu.be/<id>`, `youtube.com/watch?v=<id>`, `youtube.com/embed/<id>` o `youtube.com/live/<id>`), con el id inline (no requiere `course.yml`).

La sustitución SHALL ocurrir de forma que el HTML del `<iframe>` no sea escapado por el conversor markdown ni el id de YouTube termine como `<img>`.

#### Scenario: Directiva resuelta a YouTube
- **WHEN** el body contiene `:::video id=<UUID>:::` y `videos[<UUID>].youtube["en"]` existe
- **THEN** el HTML resultante contiene un `<iframe>` con `src="https://www.youtube.com/embed/<id>"`
- **THEN** no aparece el texto `:::video` en el HTML

#### Scenario: Directiva resuelta a PeerTube
- **WHEN** el body contiene `:::video id=<UUID>:::`, no hay pista YouTube pero sí `videos[<UUID>].peertube["en"]`
- **THEN** el HTML contiene un `<iframe>` con `src="https://peertube.planb.network/videos/embed/<id>"`

#### Scenario: Preferencia de proveedor
- **WHEN** el `<UUID>` tiene pista `en` tanto en `youtube` como en `peertube`
- **THEN** se embebe la de **YouTube** (preferencia `youtube` > `peertube`)

#### Scenario: Imagen markdown a YouTube
- **WHEN** el body contiene `![BTC Map](https://youtu.be/2-fEEC9_YT8)` (o `https://www.youtube.com/watch?v=2-fEEC9_YT8`)
- **THEN** el HTML contiene un `<iframe>` con `src="https://www.youtube.com/embed/2-fEEC9_YT8"`
- **THEN** no se emite un `<img>` con la URL de YouTube como `src`

#### Scenario: Imagen de asset no se trata como vídeo
- **WHEN** el body contiene `![diagrama](assets/en/001.webp)`
- **THEN** se renderiza como `<img>` (data URI), sin convertirse en `<iframe>`

#### Scenario: Reproductor responsive
- **WHEN** se embebe cualquier vídeo
- **THEN** el `<iframe>` va dentro de una envoltura con relación de aspecto 16:9 y ancho limitado, usando estilos inline (Moodle conserva `style`, elimina `<style>`)

### Requirement: Resolución de proveedor e idioma de la directiva de vídeo
Para `:::video id=<UUID>:::`, `PlanBCourseBuilder` SHALL elegir la pista a embeber en este orden: (1) `youtube["en"]`, (2) `peertube["en"]`, (3) primera pista de `youtube` en cualquier idioma, (4) primera pista de `peertube` en cualquier idioma. El importador es solo-inglés, por lo que `en` es la pista preferida.

#### Scenario: Sin pista en inglés
- **WHEN** el `<UUID>` solo tiene pistas en idiomas distintos de `en` (p. ej. `peertube: {es, it}`)
- **THEN** se embebe la primera pista disponible (respetando la preferencia de proveedor) y se registra un warning indicando que no hay versión en inglés

#### Scenario: UUID ausente en `course.yml`
- **WHEN** el body referencia `:::video id=<UUID>:::` pero `<UUID>` no está en `PlanBCourseSpec.videos`
- **THEN** no se emite `<iframe>`; el vídeo se degrada (ver "Degradación") y se registra un warning con el UUID

### Requirement: Degradación con gracia de vídeos no resolubles
Cuando un vídeo no se puede resolver a una URL de embed (UUID ausente, o entrada sin pistas), `PlanBCourseBuilder` SHALL degradar con gracia y SHALL registrar un warning. En ningún caso SHALL dejar la directiva `:::video ...:::` como texto crudo ni emitir un `<img>` cuyo `src` sea una URL de YouTube.

#### Scenario: Directiva no resoluble conserva contexto
- **WHEN** una directiva `:::video id=<UUID>:::` no se puede resolver
- **THEN** la página no contiene el texto `:::video id=<UUID>:::`
- **THEN** se registra un warning con el UUID y el motivo

#### Scenario: Nunca un `<img>` de YouTube
- **WHEN** se procesa una forma imagen-YouTube
- **THEN** el HTML resultante nunca contiene `<img ... src="https://...youtu...">`
