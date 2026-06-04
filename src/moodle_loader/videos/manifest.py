"""Shared video manifest: one entry per Plan ₿ video UUID.

Created by `download-videos` (download fields) and extended by
`publish-videos` (publish fields). STUB — bodies not implemented yet.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class VideoEntry(BaseModel):
    """One manifest row, keyed externally by the Plan ₿ video UUID.

    ``extra='allow'`` so the publish step can add ``youtube_id`` /
    ``uploaded_at`` without this model needing to know about them.
    """

    model_config = ConfigDict(extra="allow")

    peertube_id: str
    lang: str = "en"
    title: str | None = None
    mp4: str | None = None  # path relative to the manifest file
    sha256: str | None = None
    bytes: int | None = None
    status: str = "pending"  # pending | downloaded | failed | uploaded
    source_url: str | None = None


class VideoManifest:
    """A YAML manifest of video entries keyed by Plan ₿ UUID."""

    def __init__(
        self, path: Path | str, entries: dict[str, VideoEntry] | None = None
    ) -> None:
        self.path = Path(path)
        self.entries: dict[str, VideoEntry] = entries if entries is not None else {}

    @classmethod
    def load(cls, path: Path | str) -> VideoManifest:
        """Load a manifest from *path*; a missing file yields empty entries."""
        raise NotImplementedError

    def save(self) -> None:
        """Persist the manifest atomically (temp file + rename)."""
        raise NotImplementedError
