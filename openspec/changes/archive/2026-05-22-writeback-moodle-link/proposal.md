## Why

After `moodle-loader` creates a course, the resulting Moodle URL is only visible in the terminal output. The Google Sheet (the source of truth for course scheduling) has a `Moodle Link` column that stays empty, requiring manual copy-paste. Writing back the URL automatically closes the loop between the Sheet and Moodle.

## What Changes

- After a course is successfully created, `SheetsSource` writes the Moodle course URL back to the `Moodle Link` column of the corresponding row in the Sheet
- The URL format is `https://<MOODLE_URL>/course/view.php?id=<course_id>`
- Only rows where a course was actually created (`status="created"`) are updated — skipped and failed rows are left untouched
- Write-back is only performed when loading from Sheets (not from YAML)
- A `--no-writeback` flag allows opting out

## Capabilities

### New Capabilities

- `sheet-writeback`: Write the Moodle course URL back to the `Moodle Link` column in the Google Sheet after successful creation

### Modified Capabilities

_(none — existing behaviour unchanged)_

## Impact

- **`src/moodle_loader/sources/sheets_source.py`**: new method `write_moodle_link(row_index, url)` using gspread; `SheetsSource` must retain a reference to the worksheet after `load()`
- **`src/moodle_loader/cli.py`**: pass results back to `SheetsSource` after loading; add `--no-writeback` flag
- **`src/moodle_loader/config.py`**: `MOODLE_URL` already available — used to build the course URL
- **No new dependencies** — gspread already supports cell writes with the existing OAuth scope (needs write scope, currently readonly)
- **Google OAuth scope**: must change from `spreadsheets.readonly` to `spreadsheets` to allow writes — requires re-authentication
