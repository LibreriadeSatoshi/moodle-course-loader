"""Per-video metadata sidecar (`{uuid}.yml`) alongside the archived MP4."""

from __future__ import annotations

from pathlib import Path

import yaml

from moodle_loader.videos.peertube import PEERTUBE_HOST, PeerTubeVideo


def build_metadata(video: PeerTubeVideo, *, planb_uuid: str) -> dict:
    """Build the metadata dict written to ``{uuid}.yml`` for a downloaded video."""
    return {
        "planb_uuid": planb_uuid,
        "peertube_id": video.peertube_id,
        "source_url": f"{PEERTUBE_HOST}/w/{video.peertube_id}",
        "title": video.title,
        "description": video.description,
        "license": video.license,
        "language": video.language,
        "category": video.category,
        "tags": video.tags,
        "channel": video.channel,
        "duration": video.duration,
        "resolution": f"{video.height}p" if video.height else None,
        "published_at": video.published_at,
    }


def write_metadata(path: Path | str, data: dict) -> None:
    """Write *data* as YAML to *path* (atomically: temp file + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    tmp.replace(path)
