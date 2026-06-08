"""Minimal PeerTube API client (resolve a video's HLS master playlist).

STUB — bodies not implemented yet.
"""

from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from pydantic import BaseModel

PEERTUBE_HOST = "https://peertube.planb.network"

# RESOLUTION=<width>x<height> on an HLS master's #EXT-X-STREAM-INF line.
_RESOLUTION_RE = re.compile(r"RESOLUTION=(\d+)x(\d+)")


class PeerTubeError(Exception):
    """Raised when a PeerTube video can't be resolved."""


class PeerTubeVideo(BaseModel):
    """A PeerTube video: download URL plus preservation metadata."""

    peertube_id: str
    title: str
    playlist_url: str  # highest-resolution HLS media playlist (.m3u8)
    height: int | None = None  # vertical resolution of the selected variant
    # Metadata (for the per-video sidecar file).
    description: str | None = None
    license: str | None = None
    language: str | None = None
    category: str | None = None
    tags: list[str] = []
    channel: str | None = None
    duration: int | None = None
    published_at: str | None = None


def _select_best_variant(master_url: str, master_text: str) -> tuple[str, int | None]:
    """Return ``(url, height)`` of the highest-resolution variant in a master.

    PeerTube lists variants ascending (144p → 240p → 360p), so ffmpeg's default
    "first variant" would pick the *lowest*. We parse the master and pick the
    variant with the largest pixel area, resolving its (possibly relative) URI
    against *master_url*. Falls back to the master URL if it has no variants.
    """
    lines = master_text.splitlines()
    best: tuple[int, str, int] | None = None  # (pixels, uri, height)
    for i, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF"):
            continue
        m = _RESOLUTION_RE.search(line)
        width, height = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        pixels = width * height
        uri = next(
            (
                lines[j].strip()
                for j in range(i + 1, len(lines))
                if lines[j].strip() and not lines[j].strip().startswith("#")
            ),
            None,
        )
        if uri and (best is None or pixels > best[0]):
            best = (pixels, uri, height)

    if best is None:
        return master_url, None
    return urljoin(master_url, best[1]), (best[2] or None)


class PeerTubeClient:
    def __init__(self, host: str = PEERTUBE_HOST) -> None:
        self.host = host

    def get_video(self, peertube_id: str) -> PeerTubeVideo:
        """Resolve the highest-resolution HLS media playlist for a video.

        GET /api/v1/videos/<id> for the HLS master, then parse the master to
        pick the highest-resolution variant. Raises PeerTubeError if the video
        has no streaming playlist or the master can't be fetched.
        """
        url = f"{self.host}/api/v1/videos/{peertube_id}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise PeerTubeError(f"Failed to fetch {peertube_id}: {exc}") from exc

        playlists = data.get("streamingPlaylists") or []
        master_url = playlists[0].get("playlistUrl") if playlists else None
        if not master_url:
            raise PeerTubeError(
                f"Video {peertube_id} has no HLS streaming playlist"
            )

        try:
            master = requests.get(master_url, timeout=30)
            master.raise_for_status()
        except requests.RequestException as exc:
            raise PeerTubeError(
                f"Failed to fetch master playlist for {peertube_id}: {exc}"
            ) from exc

        playlist_url, height = _select_best_variant(master_url, master.text)

        def _label(field: str) -> str | None:
            value = data.get(field)
            return value.get("label") if isinstance(value, dict) else None

        channel = data.get("channel")
        return PeerTubeVideo(
            peertube_id=peertube_id,
            title=data.get("name") or "",
            playlist_url=playlist_url,
            height=height,
            description=data.get("description"),
            license=_label("licence"),
            language=_label("language"),
            category=_label("category"),
            tags=data.get("tags") or [],
            channel=channel.get("displayName") if isinstance(channel, dict) else None,
            duration=data.get("duration"),
            published_at=data.get("publishedAt"),
        )
