## Why

When `load-sheets` is run, it processes all rows in the sheet including courses that have already been created (identified by a non-empty `Moodle Link` column). These rows should be skipped automatically — the link is the signal that the course exists and the write-back already happened.

## What Changes

- `SheetsSource.load()` skips rows where the `Moodle Link` column is non-empty
- A debug/info log is emitted for each skipped row so the operator knows why it was excluded
- The `--shortname` filter still works as before — but if the matching course already has a link, it is also skipped (with a clear message)

## Capabilities

### New Capabilities

- `skip-linked-courses`: Skip sheet rows whose `Moodle Link` cell is already filled in during `load()`

### Modified Capabilities

_(none — existing behavior is unchanged for rows without a Moodle Link)_

## Impact

- **`src/moodle_loader/sources/sheets_source.py`**: `load()` reads the `Moodle Link` value per row and skips non-empty ones
- **`tests/test_sheets_source.py`**: new tests for the skip logic
- No CLI or model changes needed
