## Context

`SheetsSource` currently reads rows from Google Sheets and returns `list[CourseSpec]`. After the loader processes those specs, the results (including `course_id`) are only in memory. Writing back to the Sheet requires knowing the row index of each spec and having write access to the worksheet.

The OAuth scope currently used is `cloud-platform`, which does not grant Sheets write access. The scope must be upgraded to include `https://www.googleapis.com/auth/spreadsheets` (read/write). This requires the user to re-authenticate once after the change is deployed.

## Goals / Non-Goals

**Goals:**
- Write `https://<MOODLE_URL>/course/view.php?id=<course_id>` to the `Moodle Link` column for each successfully created course
- Only write on `status="created"` — leave skipped/failed rows untouched
- Provide `--no-writeback` opt-out flag on `load-sheets`
- Degrade gracefully: if the write fails, log a warning but do not fail the overall command

**Non-Goals:**
- Write-back for YAML source
- Writing other result fields (status, course ID) to the Sheet
- Clearing the `Moodle Link` cell on failure

## Decisions

### 1. SheetsSource retains worksheet reference and row map

**Decision**: During `load()`, `SheetsSource` builds a dict `shortname → row_number` (1-based, accounting for the header row). After loading, the worksheet object is kept as `self._ws`. A new public method `write_moodle_link(shortname, url)` uses the row map to update the correct cell.

**Alternative discarded**: Pass row indices through `CourseSpec`. Discarded because `CourseSpec` is a pure data model shared with YAML source — polluting it with Sheet-specific metadata would break the abstraction.

### 2. Write-back called from the CLI after loader finishes

**Decision**: In `load_sheets` command, after `loader.load_specs(specs)`, iterate results and call `source.write_moodle_link(r.spec.shortname, url)` for each `status="created"` result.

**Reason**: The CLI already orchestrates source + loader + output. Keeping write-back there avoids coupling the loader to source internals.

### 3. OAuth scope upgrade: `spreadsheets` instead of `cloud-platform`

**Decision**: Change the ADC scope to `https://www.googleapis.com/auth/spreadsheets` (read+write). Delete `authorized_user.json` and re-authenticate once.

**Why not keep readonly**: gspread will raise a 403 on any write attempt with a readonly token.

### 4. Graceful degradation on write failure

**Decision**: Wrap `write_moodle_link` in try/except; log warning with the shortname and error. The command exits with code 0 if all courses were created even if write-back failed.

## Risks / Trade-offs

- **Re-auth required**: users must delete `authorized_user.json` and run `gcloud auth application-default login` (or re-do OAuth flow) after this change. Must be documented clearly.
- **Race condition**: if two operators run the loader simultaneously, the second write wins. Acceptable for this use case.
- **Column position changes**: `write_moodle_link` looks up the `Moodle Link` column by header name each time `load()` is called, not hardcoded by index. Resilient to column reordering.
