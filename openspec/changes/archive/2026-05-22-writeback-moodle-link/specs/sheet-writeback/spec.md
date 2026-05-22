## ADDED Requirements

### Requirement: Write Moodle URL back to Sheet after course creation
After successfully creating a course from Google Sheets data, the system SHALL write the Moodle course URL to the `Moodle Link` column of the corresponding row.

The URL format SHALL be `https://<MOODLE_URL>/course/view.php?id=<course_id>`.

#### Scenario: Course created successfully
- **WHEN** a course is created with `status="created"` and `course_id=25`
- **THEN** the `Moodle Link` cell in the corresponding Sheet row is updated to `https://moodle.libreriadesatoshi.com/course/view.php?id=25`

#### Scenario: Course skipped or failed — no write-back
- **WHEN** a course result has `status="skipped"` or `status="failed"`
- **THEN** the `Moodle Link` cell is left unchanged

#### Scenario: Write-back disabled with --no-writeback
- **WHEN** the `load-sheets` command is run with `--no-writeback`
- **THEN** no cells are updated in the Sheet regardless of results

#### Scenario: Write-back fails gracefully
- **WHEN** the Sheet write call raises an exception
- **THEN** a warning is logged with the shortname and error details
- **THEN** the command continues and exits successfully if courses were created

### Requirement: Row lookup by shortname
`SheetsSource` SHALL maintain a mapping of `shortname → row_number` built during `load()`, used by `write_moodle_link()` to locate the correct row.

#### Scenario: Shortname found in row map
- **WHEN** `write_moodle_link("G&GI-ES-2026-1", url)` is called
- **THEN** the correct row in the Sheet is updated

#### Scenario: Shortname not in row map
- **WHEN** `write_moodle_link` is called with a shortname not present in the map
- **THEN** a warning is logged and no write is attempted

### Requirement: Google OAuth scope allows writes
The Google OAuth credentials SHALL use `https://www.googleapis.com/auth/spreadsheets` (read+write) instead of a readonly scope.

#### Scenario: Write succeeds with correct scope
- **WHEN** the user has authenticated with the `spreadsheets` scope
- **THEN** cell updates succeed without a 403 error

#### Scenario: Re-authentication required after scope change
- **WHEN** an existing `authorized_user.json` was created with a readonly scope
- **THEN** deleting `authorized_user.json` and re-authenticating grants write access
