## 1. SheetsSource — skip linked rows

- [x] 1.1 In `load()`, after reading each row, check if `COL_MOODLE_LINK` value is non-empty and skip the row if so, logging at INFO level with shortname and existing URL
- [x] 1.2 Ensure the skip happens before adding to `_row_map` (skipped rows should not be in the map)

## 2. Tests

- [x] 2.1 Test: row with non-empty `Moodle Link` is excluded from returned specs
- [x] 2.2 Test: row with empty `Moodle Link` is included as normal
- [x] 2.3 Test: info log is emitted with shortname and URL when a row is skipped
- [x] 2.4 Test: all rows linked raises `SourceError` with "no valid course rows"
- [x] 2.5 Test: no `Moodle Link` column in sheet → all rows included (no filter applied)
