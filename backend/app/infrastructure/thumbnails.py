"""Makes the small thumbnail a history entry keeps."""

import logging
import tempfile
from collections.abc import Sequence
from pathlib import Path

from app.infrastructure import binaries, http
from app.infrastructure.process import run

log = logging.getLogger(__name__)

MAX_BYTES = 5_000_000
FETCH_TIMEOUT = 10
FFMPEG_TIMEOUT = 20
WIDTH = 320  # a history row shows it at half of this or less


def _demuxer(image: bytes) -> str | None:
    """FFmpeg is told what the file is instead of guessing: what was fetched is outside data,
    and some of the formats FFmpeg would recognise can make it read other files."""
    if image.startswith(b"\xff\xd8\xff"):
        return "jpeg_pipe"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png_pipe"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "webp_pipe"
    return None


class ThumbnailMaker:
    def __init__(self, allowed_hosts: Sequence[str]) -> None:
        self._hosts = allowed_hosts

    def make(self, url: str) -> bytes | None:
        """A JPEG at most WIDTH wide, or None: a missing thumbnail is never an error."""
        try:
            image = http.get(url, self._hosts, MAX_BYTES, FETCH_TIMEOUT)
            demuxer = _demuxer(image)
            if demuxer is None:
                raise ValueError("not a JPEG, PNG or WebP image")
            with tempfile.TemporaryDirectory(prefix="md-thumb-") as folder:
                source, small = Path(folder, "in"), Path(folder, "out.jpg")
                source.write_bytes(image)
                code, _, err = run(
                    [
                        str(binaries.ffmpeg()), "-hide_banner", "-loglevel", "error", "-y",
                        "-f", demuxer, "-i", str(source),
                        "-vf", f"scale='min({WIDTH},iw)':-2", "-frames:v", "1", "-q:v", "5",
                        str(small),
                    ],  # fmt: skip
                    FFMPEG_TIMEOUT,
                )
                if code != 0:
                    raise ValueError(f"FFmpeg could not shrink it: {err.strip()}")
                return small.read_bytes()
        except (OSError, ValueError, TimeoutError) as error:
            log.warning("no thumbnail for the history: %s", error)
            return None
