"""Minimal PeerTube API client (resolve a video's HLS master playlist).

STUB — bodies not implemented yet.
"""

from __future__ import annotations

from pydantic import BaseModel

PEERTUBE_HOST = "https://peertube.planb.network"


class PeerTubeError(Exception):
    """Raised when a PeerTube video can't be resolved."""


class PeerTubeVideo(BaseModel):
    """The bits of a PeerTube video we need to download it."""

    peertube_id: str
    title: str
    playlist_url: str  # master HLS .m3u8


class PeerTubeClient:
    def __init__(self, host: str = PEERTUBE_HOST) -> None:
        self.host = host

    def get_video(self, peertube_id: str) -> PeerTubeVideo:
        """GET /api/v1/videos/<id> → title + master HLS playlist URL.

        Raises PeerTubeError if the video has no streaming playlist.
        """
        raise NotImplementedError
