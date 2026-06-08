"""Orchestrates downloading Plan ₿ PeerTube videos into the manifest.

STUB — ``run`` not implemented yet.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel

from moodle_loader.sources.planb_source import _read_videos
from moodle_loader.videos.ffmpeg import remux_to_mp4
from moodle_loader.videos.manifest import VideoEntry, VideoManifest
from moodle_loader.videos.metadata import build_metadata, write_metadata
from moodle_loader.videos.peertube import PEERTUBE_HOST, PeerTubeClient

log = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


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

    def _course_ymls(self) -> list[Path]:
        """The ``course.yml`` files to scan.

        If *courses_root* is itself a course directory (contains a
        ``course.yml``), only that one is scanned; otherwise every child
        ``<slug>/course.yml`` under the root is scanned.
        """
        if (self.courses_root / "course.yml").is_file():
            return [self.courses_root / "course.yml"]
        return sorted(self.courses_root.glob("*/course.yml"))

    def _enumerate(self) -> dict[str, str]:
        """Map ``{planb_uuid → peertube_id}`` for videos with a track in *lang*.

        Scans the relevant ``course.yml`` file(s); the first occurrence of a
        UUID wins (dedup across courses). YouTube-only videos are skipped.
        """
        videos: dict[str, str] = {}
        for course_yml in self._course_ymls():
            for uuid, video in _read_videos(course_yml).items():
                if uuid in videos:
                    continue
                peertube_id = video.peertube.get(self.lang)
                if peertube_id:
                    videos[uuid] = peertube_id
        return videos

    def _is_current(self, uuid: str) -> bool:
        """True if the manifest entry is downloaded and matches the file on disk."""
        entry = self.manifest.entries.get(uuid)
        if entry is None or entry.status != "downloaded" or not entry.mp4:
            return False
        mp4 = self.manifest.path.parent / entry.mp4
        if not mp4.is_file():
            return False
        return not entry.sha256 or _sha256(mp4) == entry.sha256

    def run(
        self, *, force: bool = False, only: list[str] | None = None
    ) -> DownloadResult:
        """Download all pending PeerTube videos; idempotent unless *force*."""
        result = DownloadResult()
        videos = self._enumerate()
        if only is not None:
            wanted = set(only)
            videos = {u: pid for u, pid in videos.items() if u in wanted}

        for uuid, peertube_id in videos.items():
            if not force and self._is_current(uuid):
                log.info("Skipping %s (already downloaded)", uuid)
                result.skipped.append(uuid)
                continue

            try:
                video = self.peertube.get_video(peertube_id)
                out_path = self.archive_dir / f"{uuid}.{self.lang}.mp4"
                self.remux(video.playlist_url, out_path)
                write_metadata(
                    self.archive_dir / f"{uuid}.yml",
                    build_metadata(video, planb_uuid=uuid),
                )
                rel = os.path.relpath(out_path, self.manifest.path.parent)
                self.manifest.entries[uuid] = VideoEntry(
                    peertube_id=peertube_id,
                    lang=self.lang,
                    title=video.title,
                    resolution=f"{video.height}p" if video.height else None,
                    mp4=rel,
                    sha256=_sha256(out_path),
                    bytes=out_path.stat().st_size,
                    status="downloaded",
                    source_url=f"{PEERTUBE_HOST}/w/{peertube_id}",
                )
                self.manifest.save()
                result.downloaded.append(uuid)
            except Exception as exc:  # noqa: BLE001 — record and continue the batch
                log.warning("Failed to download %s (%s): %s", uuid, peertube_id, exc)
                self.manifest.entries[uuid] = VideoEntry(
                    peertube_id=peertube_id,
                    lang=self.lang,
                    status="failed",
                    source_url=f"{PEERTUBE_HOST}/w/{peertube_id}",
                )
                self.manifest.save()
                result.failed.append(uuid)

        return result
