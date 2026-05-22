## ADDED Requirements

### Requirement: Skip rows with an existing Moodle Link
During `SheetsSource.load()`, the system SHALL skip any row whose `Moodle Link` column is non-empty, treating it as already created.

An info-level log message SHALL be emitted for each skipped row, including the shortname and the existing URL.

#### Scenario: Row with Moodle Link is skipped
- **WHEN** a sheet row has `Moodle Link` = `https://moodle.libreriadesatoshi.com/course/view.php?id=25`
- **THEN** no `CourseSpec` is produced for that row
- **THEN** an info log is emitted containing the shortname and the existing URL

#### Scenario: Row without Moodle Link is included
- **WHEN** a sheet row has `Moodle Link` = `""` (empty)
- **THEN** a `CourseSpec` is produced for that row as normal

#### Scenario: All rows have Moodle Link filled
- **WHEN** every data row in the sheet has a non-empty `Moodle Link`
- **THEN** `load()` raises `SourceError` with a message indicating no valid rows remain

#### Scenario: Moodle Link column absent from sheet
- **WHEN** the sheet has no `Moodle Link` column header
- **THEN** all rows are included as normal (no column → no filter applied)
