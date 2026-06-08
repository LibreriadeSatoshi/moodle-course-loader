"""CLI tests for the download-videos command.

The download engine is exercised in test_video_download.py; here we only test
the CLI wiring (arg validation, ffmpeg pre-check, summary, exit codes), so the
downloader and ffmpeg check are monkeypatched.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from moodle_loader.cli import app
from moodle_loader.videos.downloader import DownloadResult

runner = CliRunner()


def _courses(tmp_path: Path) -> Path:
    root = tmp_path / "courses"
    (root / "btc102").mkdir(parents=True)
    (root / "btc102" / "course.yml").write_text(
        "id: 00000000-0000-0000-0000-000000000000\n"
        "videos:\n"
        "  - id: 58e578ef-bb3c-423d-8431-0c16db8e5f29\n"
        "    peertube:\n"
        "      - en: aee8BTojUSaDFnEPnoUUzC\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def _no_ffmpeg_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make check_ffmpeg a no-op so tests don't require a real ffmpeg binary."""
    monkeypatch.setattr("moodle_loader.videos.ffmpeg.check_ffmpeg", lambda: None)


def test_download_videos_runs_and_prints_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_ffmpeg_check: None
) -> None:
    captured = {}

    def fake_run(self, *, force=False, only=None):  # type: ignore[no-untyped-def]
        captured["force"] = force
        captured["only"] = only
        return DownloadResult(downloaded=["58e578ef-bb3c-423d-8431-0c16db8e5f29"])

    monkeypatch.setattr(
        "moodle_loader.videos.downloader.VideoDownloader.run", fake_run
    )

    result = runner.invoke(
        app,
        [
            "download-videos",
            str(_courses(tmp_path)),
            "--manifest",
            str(tmp_path / "m.yml"),
            "--archive-dir",
            str(tmp_path / "archive"),
        ],
    )

    assert result.exit_code == 0
    assert "Downloaded" in result.stdout
    assert captured["force"] is False
    assert captured["only"] is None


def test_download_videos_passes_only_and_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_ffmpeg_check: None
) -> None:
    captured = {}

    def fake_run(self, *, force=False, only=None):  # type: ignore[no-untyped-def]
        captured["force"] = force
        captured["only"] = only
        return DownloadResult()

    monkeypatch.setattr(
        "moodle_loader.videos.downloader.VideoDownloader.run", fake_run
    )

    result = runner.invoke(
        app,
        [
            "download-videos",
            str(_courses(tmp_path)),
            "--force",
            "--only",
            "58e578ef-bb3c-423d-8431-0c16db8e5f29",
        ],
    )

    assert result.exit_code == 0
    assert captured["force"] is True
    assert captured["only"] == ["58e578ef-bb3c-423d-8431-0c16db8e5f29"]


def test_download_videos_nonzero_exit_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_ffmpeg_check: None
) -> None:
    monkeypatch.setattr(
        "moodle_loader.videos.downloader.VideoDownloader.run",
        lambda self, **kw: DownloadResult(failed=["58e578ef-bb3c-423d-8431-0c16db8e5f29"]),
    )

    result = runner.invoke(app, ["download-videos", str(_courses(tmp_path))])
    assert result.exit_code == 1


def test_download_videos_prints_saved_locations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_ffmpeg_check: None
) -> None:
    from moodle_loader.videos.manifest import VideoEntry

    uuid = "58e578ef-bb3c-423d-8431-0c16db8e5f29"

    def fake_run(self, *, force=False, only=None):  # type: ignore[no-untyped-def]
        self.manifest.entries[uuid] = VideoEntry(
            peertube_id="x", mp4=f"archive/{uuid}.en.mp4", status="downloaded"
        )
        return DownloadResult(downloaded=[uuid])

    monkeypatch.setattr(
        "moodle_loader.videos.downloader.VideoDownloader.run", fake_run
    )

    result = runner.invoke(
        app,
        [
            "download-videos",
            str(_courses(tmp_path)),
            "--manifest",
            str(tmp_path / "m.yml"),
        ],
    )

    assert result.exit_code == 0
    # The resolved MP4 path is printed on completion. Collapse whitespace so the
    # assertion is independent of terminal width (Rich may wrap long lines).
    flat = "".join(result.stdout.split())
    assert f"{uuid}.en.mp4" in flat


def test_download_videos_course_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _no_ffmpeg_check: None
) -> None:
    captured = {}

    def fake_run(self, *, force=False, only=None):  # type: ignore[no-untyped-def]
        captured["root"] = str(self.courses_root)
        return DownloadResult()

    monkeypatch.setattr(
        "moodle_loader.videos.downloader.VideoDownloader.run", fake_run
    )

    course_dir = _courses(tmp_path) / "btc102"
    result = runner.invoke(app, ["download-videos", "--course", str(course_dir)])

    assert result.exit_code == 0
    assert captured["root"] == str(course_dir)


def test_download_videos_requires_a_target(tmp_path: Path) -> None:
    # Neither a positional root nor --course → error.
    result = runner.invoke(app, ["download-videos"])
    assert result.exit_code == 1


def test_download_videos_rejects_both_targets(
    tmp_path: Path, _no_ffmpeg_check: None
) -> None:
    root = _courses(tmp_path)
    result = runner.invoke(
        app, ["download-videos", str(root), "--course", str(root / "btc102")]
    )
    assert result.exit_code == 1


def test_download_videos_unsupported_lang(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["download-videos", str(_courses(tmp_path)), "--lang", "fr"]
    )
    assert result.exit_code == 1


def test_download_videos_missing_ffmpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from moodle_loader.videos.ffmpeg import FfmpegError

    def boom() -> None:
        raise FfmpegError("ffmpeg not found on PATH")

    monkeypatch.setattr("moodle_loader.videos.ffmpeg.check_ffmpeg", boom)

    result = runner.invoke(app, ["download-videos", str(_courses(tmp_path))])
    assert result.exit_code == 1
    assert "ffmpeg" in result.stdout.lower() or "ffmpeg" in str(result.output).lower()


def test_download_videos_path_not_a_directory(tmp_path: Path) -> None:
    bogus = tmp_path / "nope"
    result = runner.invoke(app, ["download-videos", str(bogus)])
    assert result.exit_code == 1
