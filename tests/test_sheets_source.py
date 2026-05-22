from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from moodle_loader.config import Settings
from moodle_loader.exceptions import SourceError
from moodle_loader.sources.sheets_source import SheetsSource

CATEGORIES = [
    {"id": 2, "name": "Bitcoin 4 Everyone"},
    {"id": 3, "name": "Bitcoin Dev"},
    {"id": 4, "name": "Sovereignty"},
]

VALID_ROW = {
    "Course name (Spanish)": "Iníciate en tecnología con GitHub",
    "CODE": "G&GI-ES-2026-1",
    "Course Name (English)": "Get started with GitHub",
    "Path": "Bitcoin 4 Everyone",
    "template_id": "10",
}

VALID_ROW_WITH_LINK = {**VALID_ROW, "Moodle Link": ""}


@pytest.fixture
def settings() -> Settings:
    return Settings(
        moodle_url="https://moodle.test",
        moodle_token="test-token",
        default_template_id=20,
        default_category_name="Bitcoin 4 Everyone",
    )


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.get_categories.return_value = CATEGORIES
    return client


def _make_source(mock_client: MagicMock, settings: Settings, rows: list[dict]) -> SheetsSource:
    source = SheetsSource(
        spreadsheet_id="fake-sheet-id",
        client=mock_client,
        settings=settings,
    )
    headers = list(rows[0].keys()) if rows else []
    source._fetch_rows = lambda: (rows, headers)  # type: ignore[method-assign]
    return source


def test_load_successful_with_all_columns(mock_client: MagicMock, settings: Settings) -> None:
    source = _make_source(mock_client, settings, [VALID_ROW])
    specs = source.load()
    assert len(specs) == 1
    s = specs[0]
    assert s.fullname == "Iníciate en tecnología con GitHub"
    assert s.shortname == "G&GI-ES-2026-1"
    assert s.summary == "Get started with GitHub"
    assert s.category_id == 2
    assert s.template_id == 10
    assert s.visible is False


def test_empty_template_id_uses_default(mock_client: MagicMock, settings: Settings) -> None:
    row = {**VALID_ROW, "template_id": ""}
    source = _make_source(mock_client, settings, [row])
    specs = source.load()
    assert specs[0].template_id == 20


def test_unknown_path_falls_back_to_default_and_warns(
    mock_client: MagicMock, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    row = {**VALID_ROW, "Path": "Categoria Inexistente"}
    source = _make_source(mock_client, settings, [row])
    with caplog.at_level(logging.WARNING):
        specs = source.load()
    assert specs[0].category_id == 2  # Bitcoin 4 Everyone
    assert "Categoria Inexistente" in caplog.text
    assert "Bitcoin 4 Everyone" in caplog.text


def test_unknown_path_and_unknown_default_raises(mock_client: MagicMock) -> None:
    settings = Settings(
        moodle_url="https://moodle.test",
        moodle_token="test-token",
        default_template_id=20,
        default_category_name="Categoria Que No Existe",
    )
    row = {**VALID_ROW, "Path": "Otra Inexistente"}
    source = _make_source(mock_client, settings, [row])
    with pytest.raises(SourceError, match="not found in Moodle either"):
        source.load()


def test_blank_rows_are_skipped_silently(mock_client: MagicMock, settings: Settings) -> None:
    blank = {"Course name (Spanish)": "", "CODE": "", "Course Name (English)": "", "Path": "", "template_id": ""}
    source = _make_source(mock_client, settings, [blank, VALID_ROW, blank])
    specs = source.load()
    assert len(specs) == 1


def test_no_valid_rows_raises(mock_client: MagicMock, settings: Settings) -> None:
    blank = {"Course name (Spanish)": "", "CODE": "", "Course Name (English)": "", "Path": "", "template_id": ""}
    source = _make_source(mock_client, settings, [blank])
    with pytest.raises(SourceError, match="no valid course rows"):
        source.load()


def test_google_auth_error_raises_source_error(mock_client: MagicMock, settings: Settings) -> None:
    source = SheetsSource(
        spreadsheet_id="fake-sheet-id",
        client=mock_client,
        settings=settings,
        credentials_file="nonexistent_credentials.json",
        oauth_secrets_file="nonexistent_client_secrets.json",
    )
    with pytest.raises(SourceError, match="No Google credentials found"):
        source.load()


def test_write_moodle_link_updates_correct_cell(mock_client: MagicMock, settings: Settings) -> None:
    source = _make_source(mock_client, settings, [VALID_ROW_WITH_LINK])
    source.load()
    ws_mock = MagicMock()
    source._ws = ws_mock
    url = "https://moodle.test/course/view.php?id=25"
    source.write_moodle_link("G&GI-ES-2026-1", url)
    # row 2 (header is row 1), col 6 (1-based index of "Moodle Link" in VALID_ROW_WITH_LINK)
    ws_mock.update_cell.assert_called_once_with(2, 6, url)


def test_write_moodle_link_warns_when_shortname_missing(
    mock_client: MagicMock, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    source = _make_source(mock_client, settings, [VALID_ROW_WITH_LINK])
    source.load()
    ws_mock = MagicMock()
    source._ws = ws_mock
    with caplog.at_level(logging.WARNING):
        source.write_moodle_link("NONEXISTENT", "https://moodle.test/course/view.php?id=99")
    assert "NONEXISTENT" in caplog.text
    ws_mock.update_cell.assert_not_called()


def test_write_moodle_link_exception_warns_without_raising(
    mock_client: MagicMock, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    source = _make_source(mock_client, settings, [VALID_ROW_WITH_LINK])
    source.load()
    ws_mock = MagicMock()
    ws_mock.update_cell.side_effect = Exception("write failed")
    source._ws = ws_mock
    with caplog.at_level(logging.WARNING):
        source.write_moodle_link("G&GI-ES-2026-1", "https://moodle.test/course/view.php?id=25")
    assert "write failed" in caplog.text


# --- skip-linked-courses tests ---

LINKED_ROW = {**VALID_ROW, "Moodle Link": "https://moodle.test/course/view.php?id=25"}


def test_linked_row_is_excluded_from_specs(mock_client: MagicMock, settings: Settings) -> None:
    source = _make_source(mock_client, settings, [LINKED_ROW])
    with pytest.raises(SourceError, match="no valid course rows"):
        source.load()


def test_empty_moodle_link_row_is_included(mock_client: MagicMock, settings: Settings) -> None:
    row = {**VALID_ROW, "Moodle Link": ""}
    source = _make_source(mock_client, settings, [row])
    specs = source.load()
    assert len(specs) == 1
    assert specs[0].shortname == "G&GI-ES-2026-1"


def test_linked_row_logs_info(
    mock_client: MagicMock, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    source = _make_source(mock_client, settings, [LINKED_ROW, VALID_ROW])
    with caplog.at_level(logging.INFO):
        specs = source.load()
    assert len(specs) == 1
    assert "G&GI-ES-2026-1" in caplog.text
    assert "https://moodle.test/course/view.php?id=25" in caplog.text


def test_all_rows_linked_raises(mock_client: MagicMock, settings: Settings) -> None:
    source = _make_source(mock_client, settings, [LINKED_ROW])
    with pytest.raises(SourceError, match="no valid course rows"):
        source.load()


def test_no_moodle_link_column_includes_all_rows(mock_client: MagicMock, settings: Settings) -> None:
    source = _make_source(mock_client, settings, [VALID_ROW])
    specs = source.load()
    assert len(specs) == 1
