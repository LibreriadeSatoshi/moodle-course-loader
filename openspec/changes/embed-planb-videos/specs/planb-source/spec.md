## ADDED Requirements

### Requirement: Parsear el bloque `videos:` de `course.yml`
`PlanBSource` SHALL parsear el bloque `videos:` de `course.yml` y exponerlo en `PlanBCourseSpec.videos` como un mapa indexado por el UUID del vídeo.

Cada entrada del bloque tiene la forma:

```yaml
videos:
  - id: <UUID>
    youtube:
      - <idioma>: <id_en_youtube>
    peertube:
      - <idioma>: <id_en_peertube>
```

donde `youtube` y `peertube` son opcionales y cada uno es una lista de mapas de un solo par `{idioma: id}`. `PlanBSource` SHALL aplanar cada lista de proveedor a un mapa `{idioma → id}`.

#### Scenario: Vídeo solo en YouTube
- **WHEN** una entrada tiene `id: 758d7d3b-...` y `youtube: [{fr: PdiL6_1wbQY}]` sin `peertube`
- **THEN** `PlanBCourseSpec.videos["758d7d3b-..."]` tiene `youtube == {"fr": "PdiL6_1wbQY"}` y `peertube == {}`

#### Scenario: Vídeo solo en PeerTube
- **WHEN** una entrada tiene `id: 58e578ef-...` y `peertube: [{es: aee8...}, {it: 2Gq2...}]` sin `youtube`
- **THEN** `PlanBCourseSpec.videos["58e578ef-..."]` tiene `peertube == {"es": "aee8...", "it": "2Gq2..."}` y `youtube == {}`

#### Scenario: Vídeo en ambos proveedores
- **WHEN** una entrada tiene tanto `youtube` como `peertube`
- **THEN** la entrada resultante puebla ambos mapas, conservando todas las pistas de idioma

#### Scenario: Sin bloque `videos:`
- **WHEN** `course.yml` no contiene la clave `videos:`
- **THEN** `PlanBCourseSpec.videos` es un mapa vacío y `load()` no lanza error

#### Scenario: Entrada malformada
- **WHEN** una entrada del bloque `videos:` no tiene `id`, o tiene `id` pero ningún proveedor (`youtube`/`peertube`) con pistas
- **THEN** esa entrada se omite del mapa y se registra un warning, sin abortar el parseo del resto

#### Scenario: El bloque `videos:` no afecta a Partes/Capítulos/assets
- **WHEN** se parsea un curso con bloque `videos:`
- **THEN** el parseo de Partes, Capítulos y assets es idéntico al de un curso sin ese bloque (la única diferencia es `PlanBCourseSpec.videos`)
