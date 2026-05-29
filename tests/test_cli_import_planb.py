"""CLI tests for the import-planb command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from moodle_loader.cli import app

runner = CliRunner()

_BTC101 = (
    Path(__file__).parent.parent.parent
    / "bitcoin-educational-content"
    / "courses"
    / "btc101"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FM = "name: Test Course\ngoal: Learn things.\nobjectives:\n  - Obj A"
_BODY = """\
# Intro

+++

# Part One

<partId>11111111-0000-0000-0000-000000000000</partId>

## Chapter A

<chapterId>aaaaaaaa-0000-0000-0000-000000000000</chapterId>

Body.

# Part Two

<partId>22222222-0000-0000-0000-000000000000</partId>

## Chapter B

<chapterId>bbbbbbbb-0000-0000-0000-000000000000</chapterId>

Body.
"""


def _make_course(tmp_path: Path, slug: str = "test101") -> Path:
    d = tmp_path / slug
    d.mkdir()
    (d / "course.yml").write_text(
        "id: 00000000-0000-0000-0000-000000000000\n", encoding="utf-8"
    )
    (d / "en.md").write_text(f"---\n{_FM}\n---\n\n{_BODY}", encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_dry_run_exits_zero(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    result = runner.invoke(app, ["import-planb", str(course_dir), "--dry-run"])
    assert result.exit_code == 0, result.output


def test_dry_run_shows_course_name(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    result = runner.invoke(app, ["import-planb", str(course_dir), "--dry-run"])
    assert "Test Course" in result.output


def test_dry_run_shows_parts_and_chapters(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    result = runner.invoke(app, ["import-planb", str(course_dir), "--dry-run"])
    assert "Part One" in result.output
    assert "Part Two" in result.output
    # Stats row values
    assert "2" in result.output  # 2 parts
    assert "Chapters" in result.output


def test_dry_run_shows_completion_message(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path)
    result = runner.invoke(app, ["import-planb", str(course_dir), "--dry-run"])
    assert "Dry run complete" in result.output


def test_dry_run_shortname_override(tmp_path: Path) -> None:
    course_dir = _make_course(tmp_path, slug="test101")
    result = runner.invoke(
        app, ["import-planb", str(course_dir), "--dry-run", "--shortname", "custom99"]
    )
    assert result.exit_code == 0
    assert "custom99" in result.output


def test_dry_run_does_not_instantiate_client(tmp_path: Path, monkeypatch) -> None:
    """MoodleClient must never be constructed during --dry-run."""
    instantiated = []

    import moodle_loader.cli as cli_module

    original = cli_module.MoodleClient

    def spy(*args, **kwargs):
        instantiated.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(cli_module, "MoodleClient", spy)

    course_dir = _make_course(tmp_path)
    runner.invoke(app, ["import-planb", str(course_dir), "--dry-run"])
    assert instantiated == [], "MoodleClient was constructed during --dry-run"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_nonexistent_path_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["import-planb", str(tmp_path / "nope"), "--dry-run"])
    assert result.exit_code != 0


def test_file_instead_of_dir_exits_nonzero(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    result = runner.invoke(app, ["import-planb", str(f), "--dry-run"])
    assert result.exit_code != 0


def test_invalid_course_source_error_exits_nonzero(tmp_path: Path) -> None:
    d = tmp_path / "bad"
    d.mkdir()
    # Missing course.yml
    (d / "en.md").write_text("---\nname: X\n---\n\nHi", encoding="utf-8")
    result = runner.invoke(app, ["import-planb", str(d), "--dry-run"])
    assert result.exit_code != 0


def test_normal_mode_exits_nonzero(tmp_path: Path) -> None:
    """Without --dry-run the command should fail until the builder is implemented."""
    course_dir = _make_course(tmp_path)
    result = runner.invoke(app, ["import-planb", str(course_dir)])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Integration: real btc101
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_dry_run() -> None:
    result = runner.invoke(app, ["import-planb", str(_BTC101), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "The Bitcoin Journey" in result.output
    assert "btc101" in result.output
    assert "Dry run complete" in result.output


@pytest.mark.skipif(
    not _BTC101.is_dir(), reason="bitcoin-educational-content repo not present"
)
def test_btc101_shortname_override() -> None:
    result = runner.invoke(
        app, ["import-planb", str(_BTC101), "--dry-run", "--shortname", "mybtc101"]
    )
    assert result.exit_code == 0
    assert "mybtc101" in result.output
