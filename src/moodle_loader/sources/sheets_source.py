from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import gspread

from moodle_loader.client import MoodleClient
from moodle_loader.config import Settings
from moodle_loader.exceptions import SourceError
from moodle_loader.models import CourseSpec
from moodle_loader.sources.base import CourseSource

logger = logging.getLogger(__name__)

# Column names as they appear in the sheet header row
COL_FULLNAME = "Course name (Spanish)"
COL_SHORTNAME = "CODE"
COL_SUMMARY = "Course Name (English)"
COL_PATH = "Path"
COL_TEMPLATE_ID = "template_id"
COL_MOODLE_LINK = "Moodle Link"


class SheetsSource(CourseSource):
    """Read courses from a Google Sheet.

    Requires: `pip install moodle-loader[sheets]`

    The sheet must have a header row with at least:
      - Course name (Spanish)  → fullname
      - CODE                   → shortname
      - Course Name (English)  → summary
      - Path                   → category (resolved via Moodle API)
      - template_id            → template course ID (optional, defaults to DEFAULT_TEMPLATE_ID)

    Rows missing both fullname and shortname are skipped (treated as blank).
    Configurable via .env:
      DEFAULT_TEMPLATE_ID=20
      DEFAULT_CATEGORY_NAME=Bitcoin 4 Everyone
    """

    def __init__(
        self,
        spreadsheet_id: str,
        client: MoodleClient,
        settings: Settings,
        worksheet: str = "Sheet1",
        credentials_file: str = "credentials.json",
        oauth_secrets_file: str = "client_secrets.json",
        authorized_user_file: str = "authorized_user.json",
    ):
        self.spreadsheet_id = spreadsheet_id
        self.moodle = client
        self.settings = settings
        self.worksheet = worksheet
        self.credentials_file = credentials_file
        self.oauth_secrets_file = oauth_secrets_file
        self.authorized_user_file = authorized_user_file

        self._ws: gspread.Worksheet | None = None
        self._row_map: dict[str, int] = {}
        self._moodle_link_col: int | None = None

    def load(self) -> list[CourseSpec]:
        category_map = self._build_category_map()
        rows, headers = self._fetch_rows()

        # Detect Moodle Link column index (1-based for gspread)
        self._moodle_link_col = next(
            (i + 1 for i, h in enumerate(headers) if h == COL_MOODLE_LINK), None
        )
        if self._moodle_link_col is None:
            logger.warning("Column %r not found in sheet — write-back will be skipped", COL_MOODLE_LINK)

        specs: list[CourseSpec] = []
        for data_idx, row in enumerate(rows):
            sheet_row = data_idx + 2  # row 1 is header; data starts at row 2
            fullname = row.get(COL_FULLNAME, "").strip()
            shortname = row.get(COL_SHORTNAME, "").strip()

            if not fullname and not shortname:
                continue

            if not fullname:
                logger.warning("row %d: missing '%s', skipping", data_idx, COL_FULLNAME)
                continue
            if not shortname:
                logger.warning("row %d: missing '%s', skipping", data_idx, COL_SHORTNAME)
                continue

            existing_link = row.get(COL_MOODLE_LINK, "").strip()
            if existing_link:
                logger.info("row %d: %r already linked (%s), skipping", data_idx, shortname, existing_link)
                continue

            self._row_map[shortname] = sheet_row

            path = row.get(COL_PATH, "").strip()
            category_id = self._resolve_category(path, category_map, row=data_idx)

            raw_template = row.get(COL_TEMPLATE_ID, "").strip()
            try:
                template_id = int(raw_template) if raw_template else self.settings.default_template_id
            except ValueError:
                logger.warning(
                    "row %d: invalid template_id %r, using default %d",
                    data_idx, raw_template, self.settings.default_template_id,
                )
                template_id = self.settings.default_template_id

            specs.append(
                CourseSpec(
                    template_id=template_id,
                    fullname=fullname,
                    shortname=shortname,
                    category_id=category_id,
                    summary=row.get(COL_SUMMARY, "").strip(),
                    visible=False,
                )
            )

        if not specs:
            raise SourceError("Google Sheet produced no valid course rows")

        return specs

    def write_moodle_link(self, shortname: str, url: str) -> None:
        if self._ws is None:
            logger.warning("write_moodle_link: worksheet not available, skipping write for %r", shortname)
            return
        if self._moodle_link_col is None:
            logger.warning("write_moodle_link: '%s' column not found, skipping write for %r", COL_MOODLE_LINK, shortname)
            return
        row = self._row_map.get(shortname)
        if row is None:
            logger.warning("write_moodle_link: shortname %r not in row map, skipping", shortname)
            return
        try:
            self._ws.update_cell(row, self._moodle_link_col, url)
            logger.info("Updated Moodle Link for %r → %s", shortname, url)
        except Exception as e:
            logger.warning("write_moodle_link: failed to update %r: %s", shortname, e)

    # ------------------------------------------------------------------

    def _build_category_map(self) -> dict[str, int]:
        categories = self.moodle.get_categories()
        return {c["name"]: c["id"] for c in categories}

    def _resolve_category(
        self, path: str, category_map: dict[str, int], *, row: int
    ) -> int:
        if path in category_map:
            return category_map[path]

        default = self.settings.default_category_name
        logger.warning(
            "row %d: category %r not found in Moodle, falling back to %r",
            row, path, default,
        )

        if default not in category_map:
            raise SourceError(
                f"Default category {default!r} not found in Moodle either"
            )

        return category_map[default]

    def _fetch_rows(self) -> tuple[list[dict[str, str]], list[str]]:
        try:
            if self.credentials_file and Path(self.credentials_file).is_file():
                gc = gspread.service_account(filename=self.credentials_file)
            elif self.oauth_secrets_file and Path(self.oauth_secrets_file).is_file():
                gc = gspread.oauth(
                    credentials_filename=self.oauth_secrets_file,
                    authorized_user_filename=self.authorized_user_file,
                )
            else:
                raise SourceError(
                    "No Google credentials found. Provide 'client_secrets.json' (OAuth) "
                    "or 'credentials.json' (service account) in the project directory."
                )
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f"Could not authenticate with Google: {e}") from e

        try:
            sh = gc.open_by_key(self.spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound as e:
            raise SourceError(f"Spreadsheet not found: {self.spreadsheet_id}") from e
        except gspread.exceptions.APIError as e:
            raise SourceError(
                f"Cannot access spreadsheet {self.spreadsheet_id}: {e.response.status_code} — "
                f"make sure the sheet is shared with your Google account"
            ) from e

        try:
            self._ws = sh.worksheet(self.worksheet)
        except gspread.exceptions.WorksheetNotFound as e:
            raise SourceError(
                f"Worksheet {self.worksheet!r} not found in {self.spreadsheet_id}"
            ) from e

        all_values = self._ws.get_all_values()
        if not all_values:
            return [], []

        headers = all_values[0]
        rows = []
        for raw_row in all_values[1:]:
            row: dict[str, str] = {}
            for col_idx, header in enumerate(headers):
                if not header:
                    continue
                value = raw_row[col_idx] if col_idx < len(raw_row) else ""
                if header not in row:
                    row[header] = value
            rows.append(row)

        return rows, headers
