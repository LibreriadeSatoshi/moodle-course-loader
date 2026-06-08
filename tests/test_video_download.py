"""Tests for the download-videos pipeline (moodle_loader.videos).

These target the API specified in the OpenSpec change `download-planb-videos`.
Network (PeerTube) and ffmpeg are faked via injectable seams on
`VideoDownloader`; the PeerTube client and ffmpeg wrapper get their own
focused tests with `responses` / `monkeypatch`.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import responses

from moodle_loader.videos.downloader import DownloadResult, VideoDownloader
from moodle_loader.videos.ffmpeg import FfmpegError, check_ffmpeg, remux_to_mp4
from moodle_loader.videos.manifest import VideoEntry, VideoManifest
from moodle_loader.videos.peertube import (
    PEERTUBE_HOST,
    PeerTubeClient,
    PeerTubeError,
    PeerTubeVideo,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_UUID_A = "58e578ef-bb3c-423d-8431-0c16db8e5f29"
_UUID_B = "9f3a7b2e-2c4d-4c1e-8b1f-3a2c1d4e5f6a"

_PEERTUBE_EN = (
    f"  - id: {_UUID_A}\n"
    "    peertube:\n"
    "      - en: aee8BTojUSaDFnEPnoUUzC\n"
)
_PEERTUBE_NO_EN = (
    f"  - id: {_UUID_A}\n"
    "    peertube:\n"
    "      - es: esTrack\n"
    "      - it: itTrack\n"
)
_YOUTUBE_ONLY = (
    f"  - id: {_UUID_B}\n"
    "    youtube:\n"
    "      - en: ytEN\n"
)


def _course(root: Path, slug: str, videos_block: str) -> Path:
    """Write ``<root>/<slug>/course.yml`` carrying a videos block."""
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "course.yml").write_text(
        "id: 00000000-0000-0000-0000-000000000000\n"
        f"videos:\n{videos_block}",
        encoding="utf-8",
    )
    return d


class FakePeerTube:
    """Stand-in PeerTubeClient mapping peertube_id → a resolvable video."""

    def __init__(self, known: set[str] | None = None) -> None:
        self.known = known
        self.calls: list[str] = []

    def get_video(self, peertube_id: str) -> PeerTubeVideo:
        self.calls.append(peertube_id)
        if self.known is not None and peertube_id not in self.known:
            raise PeerTubeError(f"not found: {peertube_id}")
        return PeerTubeVideo(
            peertube_id=peertube_id,
            title=f"Title {peertube_id}",
            playlist_url=f"https://hls.example/{peertube_id}/v-360.m3u8",
            height=360,
            description=f"Description for {peertube_id}",
            license="CC BY-SA 4.0",
            language="English",
            category="Science & Technology",
            tags=["bitcoin"],
            channel="Main root channel",
            duration=267,
            published_at="2025-10-21T08:07:25.283Z",
        )


class RemuxRecorder:
    """Stand-in remux: records calls, writes deterministic fake MP4 bytes."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = fail

    def __call__(self, master_url: str, out_path: Path | str) -> None:
        self.calls.append((master_url, str(out_path)))
        if self.fail:
            raise FfmpegError("ffmpeg failed")
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"MP4:" + master_url.encode())


def _downloader(
    root: Path,
    tmp_path: Path,
    *,
    peertube: object | None = None,
    remux: object | None = None,
    lang: str = "en",
) -> VideoDownloader:
    manifest = VideoManifest(tmp_path / "video_manifest.yml", {})
    return VideoDownloader(
        root,
        manifest,
        tmp_path / "archive",
        lang=lang,
        peertube=peertube or FakePeerTube(),
        remux=remux or RemuxRecorder(),
    )


# ---------------------------------------------------------------------------
# Requirement: Manifiesto de vídeos indexado por UUID Plan ₿
# ---------------------------------------------------------------------------


def test_manifest_missing_returns_empty(tmp_path: Path) -> None:
    m = VideoManifest.load(tmp_path / "nope.yml")
    assert m.entries == {}


def test_manifest_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "m.yml"
    VideoManifest(
        path,
        {_UUID_A: VideoEntry(peertube_id="x", status="downloaded", mp4="archive/a.mp4")},
    ).save()

    again = VideoManifest.load(path)
    assert again.entries[_UUID_A].peertube_id == "x"
    assert again.entries[_UUID_A].status == "downloaded"
    assert again.entries[_UUID_A].mp4 == "archive/a.mp4"


def test_manifest_incremental_update(tmp_path: Path) -> None:
    path = tmp_path / "m.yml"
    VideoManifest(path, {_UUID_A: VideoEntry(peertube_id="x")}).save()

    m = VideoManifest.load(path)
    m.entries[_UUID_B] = VideoEntry(peertube_id="y")
    m.save()

    assert set(VideoManifest.load(path).entries) == {_UUID_A, _UUID_B}


# ---------------------------------------------------------------------------
# Requirement: Enumeración de vídeos PeerTube desde course.yml
# ---------------------------------------------------------------------------


def test_youtube_only_ignored(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _YOUTUBE_ONLY)
    pt = FakePeerTube()

    dl = _downloader(root, tmp_path, peertube=pt)
    result = dl.run()

    assert _UUID_B not in dl.manifest.entries
    assert pt.calls == []  # never even queried
    assert _UUID_B not in result.downloaded


def test_peertube_without_en_skipped(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _PEERTUBE_NO_EN)
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    dl.run()

    assert _UUID_A not in dl.manifest.entries
    assert remux.calls == []


def test_dedup_same_uuid_across_courses(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "a", _PEERTUBE_EN)
    _course(root, "b", _PEERTUBE_EN)
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    dl.run()

    assert len(remux.calls) == 1  # downloaded once despite two references


# ---------------------------------------------------------------------------
# Requirement: Descarga y remux a MP4
# ---------------------------------------------------------------------------


def test_downloads_peertube_en_video(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "btc102", _PEERTUBE_EN)
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    result = dl.run()

    assert _UUID_A in result.downloaded
    entry = dl.manifest.entries[_UUID_A]
    assert entry.status == "downloaded"
    assert entry.peertube_id == "aee8BTojUSaDFnEPnoUUzC"
    assert entry.lang == "en"
    assert entry.title == "Title aee8BTojUSaDFnEPnoUUzC"
    assert entry.resolution == "360p"
    assert entry.source_url and "aee8BTojUSaDFnEPnoUUzC" in entry.source_url

    mp4 = dl.manifest.path.parent / entry.mp4
    assert mp4.is_file()
    assert entry.sha256 == hashlib.sha256(mp4.read_bytes()).hexdigest()
    assert entry.bytes == mp4.stat().st_size
    assert len(remux.calls) == 1


def test_download_failure_marks_failed(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _PEERTUBE_EN)

    dl = _downloader(root, tmp_path, remux=RemuxRecorder(fail=True))
    result = dl.run()

    assert _UUID_A in result.failed
    assert dl.manifest.entries[_UUID_A].status == "failed"


def test_one_failure_does_not_abort_batch(tmp_path: Path) -> None:
    # _UUID_A resolves; _UUID_B's peertube id is unknown → its get_video raises.
    root = tmp_path / "courses"
    _course(root, "a", _PEERTUBE_EN)
    _course(root, "b", f"  - id: {_UUID_B}\n    peertube:\n      - en: missingId\n")
    pt = FakePeerTube(known={"aee8BTojUSaDFnEPnoUUzC"})

    dl = _downloader(root, tmp_path, peertube=pt)
    result = dl.run()

    assert _UUID_A in result.downloaded
    assert _UUID_B in result.failed


# ---------------------------------------------------------------------------
# Requirement: Idempotencia de la descarga
# ---------------------------------------------------------------------------


def test_idempotent_skip_second_run(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _PEERTUBE_EN)
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    dl.run()
    assert len(remux.calls) == 1

    result2 = dl.run()
    assert len(remux.calls) == 1  # not re-downloaded
    assert _UUID_A in result2.skipped


def test_force_redownloads(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _PEERTUBE_EN)
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    dl.run()
    dl.run(force=True)

    assert len(remux.calls) == 2


def test_missing_archived_file_redownloads(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _PEERTUBE_EN)
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    dl.run()
    # The manifest says downloaded but the file vanished from disk.
    (dl.manifest.path.parent / dl.manifest.entries[_UUID_A].mp4).unlink()

    dl.run()  # no --force, but integrity check forces a re-download
    assert len(remux.calls) == 2


def test_only_filters_to_named_uuids(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "a", _PEERTUBE_EN)
    _course(root, "b", f"  - id: {_UUID_B}\n    peertube:\n      - en: bTrack\n")
    remux = RemuxRecorder()

    dl = _downloader(root, tmp_path, remux=remux)
    dl.run(only=[_UUID_A])

    assert _UUID_A in dl.manifest.entries
    assert _UUID_B not in dl.manifest.entries
    assert len(remux.calls) == 1


def test_run_returns_download_result(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "c", _PEERTUBE_EN)

    result = _downloader(root, tmp_path).run()
    assert isinstance(result, DownloadResult)


def test_single_course_directory_is_scanned(tmp_path: Path) -> None:
    # Point the downloader at a course dir (course.yml directly inside),
    # not a courses root — only that course's videos are enumerated.
    root = tmp_path / "courses"
    course_dir = _course(root, "btc102", _PEERTUBE_EN)
    remux = RemuxRecorder()

    dl = _downloader(course_dir, tmp_path, remux=remux)
    result = dl.run()

    assert _UUID_A in result.downloaded
    assert len(remux.calls) == 1


# ---------------------------------------------------------------------------
# PeerTube client (HTTP mocked)
# ---------------------------------------------------------------------------


# A master playlist with variants in PeerTube's ascending order (144→240→360).
_MASTER_M3U8 = (
    "#EXTM3U\n"
    "#EXT-X-STREAM-INF:BANDWIDTH=212349,RESOLUTION=256x144\n"
    "v-144.m3u8\n"
    "#EXT-X-STREAM-INF:BANDWIDTH=239428,RESOLUTION=426x240\n"
    "v-240.m3u8\n"
    "#EXT-X-STREAM-INF:BANDWIDTH=280153,RESOLUTION=640x360\n"
    "v-360.m3u8\n"
)


def test_select_best_variant_picks_max_resolution() -> None:
    from moodle_loader.videos.peertube import _select_best_variant

    url, height = _select_best_variant(
        "https://hls.example/dir/master.m3u8", _MASTER_M3U8
    )
    assert url == "https://hls.example/dir/v-360.m3u8"  # highest, not first
    assert height == 360


def test_select_best_variant_no_variants_falls_back_to_master() -> None:
    from moodle_loader.videos.peertube import _select_best_variant

    url, height = _select_best_variant(
        "https://hls.example/m.m3u8", "#EXTM3U\n#EXT-X-ENDLIST\n"
    )
    assert url == "https://hls.example/m.m3u8"
    assert height is None


@responses.activate
def test_peertube_get_video_selects_highest_resolution_variant() -> None:
    pid = "abc123"
    master = "https://hls.example/dir/master.m3u8"
    responses.add(
        responses.GET,
        f"{PEERTUBE_HOST}/api/v1/videos/{pid}",
        json={"name": "My Video", "streamingPlaylists": [{"playlistUrl": master}]},
        status=200,
    )
    responses.add(responses.GET, master, body=_MASTER_M3U8, status=200)

    v = PeerTubeClient().get_video(pid)
    assert v.peertube_id == pid
    assert v.title == "My Video"
    assert v.playlist_url == "https://hls.example/dir/v-360.m3u8"
    assert v.height == 360


@responses.activate
def test_peertube_no_streaming_playlist_raises() -> None:
    pid = "abc123"
    responses.add(
        responses.GET,
        f"{PEERTUBE_HOST}/api/v1/videos/{pid}",
        json={"name": "x", "streamingPlaylists": []},
        status=200,
    )

    with pytest.raises(PeerTubeError):
        PeerTubeClient().get_video(pid)


# ---------------------------------------------------------------------------
# ffmpeg wrapper (subprocess / PATH mocked)
# ---------------------------------------------------------------------------


def test_check_ffmpeg_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(FfmpegError):
        check_ffmpeg()


def test_check_ffmpeg_present_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/ffmpeg")
    check_ffmpeg()  # must not raise


def test_remux_builds_copy_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, list[str]] = {}

    class _Completed:
        returncode = 0
        stderr = ""

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = list(cmd)
        return _Completed()

    monkeypatch.setattr("subprocess.run", _fake_run)
    out = tmp_path / "v.mp4"
    remux_to_mp4("https://hls/master.m3u8", out)

    cmd = captured["cmd"]
    assert "ffmpeg" in cmd[0]
    assert "https://hls/master.m3u8" in cmd
    assert str(out) in cmd
    assert "-c" in cmd and "copy" in cmd  # remux, no re-encode


def test_remux_nonzero_exit_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Completed:
        returncode = 1
        stderr = "boom"

    monkeypatch.setattr("subprocess.run", lambda cmd, **kwargs: _Completed())
    with pytest.raises(FfmpegError):
        remux_to_mp4("https://hls/master.m3u8", tmp_path / "v.mp4")


# ---------------------------------------------------------------------------
# Requirement: Fichero de metadatos por vídeo
# ---------------------------------------------------------------------------


def test_build_metadata_includes_core_fields() -> None:
    from moodle_loader.videos.metadata import build_metadata

    video = PeerTubeVideo(
        peertube_id="pid",
        title="T",
        playlist_url="u",
        height=360,
        description="the full description",
        license="CC BY-SA 4.0",
        language="English",
        category="Science & Technology",
        tags=["bitcoin", "intro"],
        channel="Main root channel",
        duration=267,
        published_at="2025-10-21T08:07:25.283Z",
    )
    data = build_metadata(video, planb_uuid=_UUID_A)

    assert data["title"] == "T"
    assert data["description"] == "the full description"
    assert data["license"] == "CC BY-SA 4.0"
    assert data["language"] == "English"
    assert data["category"] == "Science & Technology"
    assert data["tags"] == ["bitcoin", "intro"]
    assert data["channel"] == "Main root channel"
    assert data["duration"] == 267
    assert data["published_at"] == "2025-10-21T08:07:25.283Z"
    assert data["peertube_id"] == "pid"
    assert data["source_url"].endswith("/w/pid")
    assert data["resolution"] == "360p"
    assert data["planb_uuid"] == _UUID_A


def test_write_metadata_roundtrip(tmp_path: Path) -> None:
    import yaml

    from moodle_loader.videos.metadata import write_metadata

    path = tmp_path / "x.yml"
    write_metadata(path, {"title": "T", "license": "L"})
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {
        "title": "T",
        "license": "L",
    }


@responses.activate
def test_get_video_populates_metadata() -> None:
    pid = "abc123"
    master = "https://hls.example/dir/master.m3u8"
    responses.add(
        responses.GET,
        f"{PEERTUBE_HOST}/api/v1/videos/{pid}",
        json={
            "name": "My Video",
            "description": "the full description",
            "truncatedDescription": "the full des...",
            "licence": {"id": None, "label": "CC BY-SA 4.0"},
            "language": {"id": "en", "label": "English"},
            "category": {"id": 15, "label": "Science & Technology"},
            "tags": ["bitcoin"],
            "channel": {"displayName": "Main root channel"},
            "duration": 267,
            "publishedAt": "2025-10-21T08:07:25.283Z",
            "streamingPlaylists": [{"playlistUrl": master}],
        },
        status=200,
    )
    responses.add(responses.GET, master, body=_MASTER_M3U8, status=200)

    v = PeerTubeClient().get_video(pid)
    assert v.description == "the full description"  # not truncatedDescription
    assert v.license == "CC BY-SA 4.0"
    assert v.language == "English"
    assert v.category == "Science & Technology"
    assert v.tags == ["bitcoin"]
    assert v.channel == "Main root channel"
    assert v.duration == 267
    assert v.published_at == "2025-10-21T08:07:25.283Z"


def test_download_writes_metadata_file(tmp_path: Path) -> None:
    import yaml

    root = tmp_path / "courses"
    _course(root, "btc102", _PEERTUBE_EN)

    dl = _downloader(root, tmp_path)
    dl.run()

    meta = tmp_path / "archive" / f"{_UUID_A}.yml"
    assert meta.is_file()
    data = yaml.safe_load(meta.read_text(encoding="utf-8"))
    assert data["title"] == "Title aee8BTojUSaDFnEPnoUUzC"
    assert data["license"] == "CC BY-SA 4.0"
    assert data["resolution"] == "360p"


def test_force_regenerates_metadata(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "btc102", _PEERTUBE_EN)

    dl = _downloader(root, tmp_path)
    dl.run()
    meta = tmp_path / "archive" / f"{_UUID_A}.yml"
    meta.write_text("sentinel: true\n", encoding="utf-8")

    dl.run(force=True)
    assert "sentinel" not in meta.read_text(encoding="utf-8")


def test_skip_does_not_rewrite_metadata(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    _course(root, "btc102", _PEERTUBE_EN)

    dl = _downloader(root, tmp_path)
    dl.run()
    meta = tmp_path / "archive" / f"{_UUID_A}.yml"
    mtime = meta.stat().st_mtime_ns

    dl.run()  # idempotent skip
    assert meta.stat().st_mtime_ns == mtime
