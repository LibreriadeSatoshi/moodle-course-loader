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
    ):
        self.spreadsheet_id = spreadsheet_id
        self.moodle = client
        self.settings = settings
        self.worksheet = worksheet
        self.credentials_file = credentials_file

    def load(self) -> list[CourseSpec]:
        category_map = self._build_category_map()
        rows = self._fetch_rows()

        specs: list[CourseSpec] = []
        for i, row in enumerate(rows):
            fullname = row.get(COL_FULLNAME, "").strip()
            shortname = row.get(COL_SHORTNAME, "").strip()

            if not fullname and not shortname:
                continue

            if not fullname:
                logger.warning("row %d: missing '%s', skipping", i, COL_FULLNAME)
                continue
            if not shortname:
                logger.warning("row %d: missing '%s', skipping", i, COL_SHORTNAME)
                continue

            path = row.get(COL_PATH, "").strip()
            category_id = self._resolve_category(path, category_map, row=i)

            raw_template = row.get(COL_TEMPLATE_ID, "").strip()
            try:
                template_id = int(raw_template) if raw_template else self.settings.default_template_id
            except ValueError:
                logger.warning(
                    "row %d: invalid template_id %r, using default %d",
                    i, raw_template, self.settings.default_template_id,
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

    def _fetch_rows(self) -> list[dict[str, str]]:
        try:
            if self.credentials_file and Path(self.credentials_file).is_file():
                gc = gspread.service_account(filename=self.credentials_file)
            else:
                gc = self._auth_with_adc()
        except SourceError:
            raise
        except Exception as e:
            raise SourceError(f"Could not authenticate with Google: {e}") from e

        try:
            sh = gc.open_by_key(self.spreadsheet_id)
            ws = sh.worksheet(self.worksheet)
        except gspread.exceptions.SpreadsheetNotFound as e:
            raise SourceError(f"Spreadsheet not found: {self.spreadsheet_id}") from e
        except gspread.exceptions.WorksheetNotFound as e:
            raise SourceError(
                f"Worksheet {self.worksheet!r} not found in {self.spreadsheet_id}"
            ) from e

        return ws.get_all_records(default_blank="")

    def _auth_with_adc(self) -> gspread.Client:
        try:
            import google.auth
            from google.auth.transport.requests import Request
        except ImportError as e:
            raise SourceError(
                "google-auth is required for ADC. Run: pip install moodle-loader[sheets]"
            ) from e

        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        try:
            credentials, _ = google.auth.default(scopes=scopes)
            credentials.refresh(Request())
        except Exception as e:
            raise SourceError(
                f"Application Default Credentials not found or expired. "
                f"Run: gcloud auth application-default login "
                f"--scopes=https://www.googleapis.com/auth/spreadsheets.readonly\n{e}"
            ) from e

        return gspread.authorize(credentials)
