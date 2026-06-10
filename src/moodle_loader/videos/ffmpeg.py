"""ffmpeg wrapper: remux an HLS master playlist to a single MP4.

STUB — bodies not implemented yet.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FfmpegError(Exception):
    """Raised when ffmpeg is missing or a remux fails."""


def check_ffmpeg() -> None:
    """Raise FfmpegError if the ``ffmpeg`` binary is not on the PATH."""
    if shutil.which("ffmpeg") is None:
        raise FfmpegError("ffmpeg not found on PATH; install it to download videos")


def remux_to_mp4(master_url: str, out_path: Path | str) -> None:
    """Remux an HLS master playlist to ``out_path`` MP4 without re-encoding.

    Selects the best video/audio rendition and copies the streams into an MP4
    container (no transcode). Raises FfmpegError on a non-zero ffmpeg exit.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-fflags",
        "+bitexact",  # deterministic demux/mux
        "-i",
        master_url,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-c",
        "copy",
        "-bsf:a",
        "aac_adtstoasc",
        "-flags",
        "+bitexact",  # don't write encoder tag / version into the container
        "-map_metadata",
        "-1",  # drop source metadata (incl. timestamps) → byte-identical output
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"ffmpeg failed for {master_url}: {result.stderr}")
