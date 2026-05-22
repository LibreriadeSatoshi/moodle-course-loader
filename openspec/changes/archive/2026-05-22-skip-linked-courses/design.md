## Context

`SheetsSource.load()` reads every data row from the sheet and returns a `CourseSpec` for each valid row. The `Moodle Link` column is already read during `load()` (it's in the sheet headers), but its value is currently ignored. If a course was already created and its link written back, re-running the loader would attempt to create it again — caught only by the duplicate-check in the loader (which makes an extra Moodle API call per row).

Filtering at the source level is cheaper and more transparent: the operator sees clearly which rows are skipped and why, without touching Moodle at all.

## Goals / Non-Goals

**Goals:**
- Skip rows with a non-empty `Moodle Link` during `SheetsSource.load()`
- Log an info message for each skipped row (shortname + existing URL)
- Zero extra API calls for already-linked courses

**Non-Goals:**
- Validate that the URL in `Moodle Link` is reachable or correct
- Clear or overwrite the existing link
- Apply this filter when loading from YAML

## Decisions

### 1. Filter inside `SheetsSource.load()`, not in the CLI

**Decision**: Check the `Moodle Link` value during row iteration in `load()` and skip before building a `CourseSpec`.

**Alternative discarded**: Filter in the CLI after `source.load()`. Discarded because the CLI doesn't know about the `Moodle Link` column — it only sees `CourseSpec` objects. Keeping the filter at the source keeps the abstraction clean.

### 2. Log at INFO level, not WARNING

**Decision**: Use `logger.info` for skipped-because-linked rows, since this is expected normal operation (not a problem).

**Alternative discarded**: `logger.debug`. Discarded because operators running without `--verbose` still benefit from seeing which rows were filtered.

### 3. No new flag to disable the filter

**Decision**: Always skip rows with a non-empty `Moodle Link`. No opt-out flag.

**Reason**: The link is the authoritative signal that the course was created. If an operator needs to recreate a course, they should clear the link from the sheet manually. Adding a flag adds complexity with no real use case.

## Risks / Trade-offs

- **Manual link entries**: If an operator manually fills `Moodle Link` for a row, that course will be skipped. Acceptable — the column is the signal.
- **Partial links (typos, partial URLs)**: Any non-empty value skips the row. If someone types a partial URL by mistake, the course won't be created until the cell is cleared. Document clearly that the column must be empty to (re)create a course.
