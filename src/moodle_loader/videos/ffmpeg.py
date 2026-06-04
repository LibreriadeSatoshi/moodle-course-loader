"""ffmpeg wrapper: remux an HLS master playlist to a single MP4.

STUB — bodies not implemented yet.
"""

from __future__ import annotations

from pathlib import Path


class FfmpegError(Exception):
    """Raised when ffmpeg is missing or a remux fails."""


def check_ffmpeg() -> None:
    """Raise FfmpegError if the ``ffmpeg`` binary is not on the PATH."""
    raise NotImplementedError


def remux_to_mp4(master_url: str, out_path: Path | str) -> None:
    """Remux an HLS master playlist to ``out_path`` MP4 without re-encoding.

    Raises FfmpegError on a non-zero ffmpeg exit.
    """
    raise NotImplementedError
