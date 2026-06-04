"""Orchestrates downloading Plan ₿ PeerTube videos into the manifest.

STUB — ``run`` not implemented yet.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from moodle_loader.videos.ffmpeg import remux_to_mp4
from moodle_loader.videos.manifest import VideoManifest
from moodle_loader.videos.peertube import PeerTubeClient


class DownloadResult(BaseModel):
    """Summary of a download run, by Plan ₿ UUID."""

    downloaded: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []


class VideoDownloader:
    """Scan course.yml files under *courses_root* and archive PeerTube videos.

    *peertube* and *remux* are injectable so the network/ffmpeg can be faked
    in tests.
    """

    def __init__(
        self,
        courses_root: Path | str,
        manifest: VideoManifest,
        archive_dir: Path | str,
        *,
        lang: str = "en",
        peertube: PeerTubeClient | None = None,
        remux: Callable[[str, Path], None] | None = None,
    ) -> None:
        self.courses_root = Path(courses_root)
        self.manifest = manifest
        self.archive_dir = Path(archive_dir)
        self.lang = lang
        self.peertube = peertube or PeerTubeClient()
        self.remux = remux or remux_to_mp4

    def run(
        self, *, force: bool = False, only: list[str] | None = None
    ) -> DownloadResult:
        """Download all pending PeerTube videos; idempotent unless *force*."""
        raise NotImplementedError
