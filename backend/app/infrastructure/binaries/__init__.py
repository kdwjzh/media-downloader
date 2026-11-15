"""Where the bundled external programs live. The only place that knows these paths."""

import re
import sys
from pathlib import Path

from app.infrastructure.process import run

VERSION_TIMEOUT = 10


def bin_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Packaged: next to the app's own exe, in the per-user install folder (ADR 0005).
        return Path(sys.executable).resolve().parent / "bin"
    # Development: <repo>/bin, filled by scripts/fetch_binaries.py.
    return Path(__file__).resolve().parents[4] / "bin"


def yt_dlp() -> Path:
    return bin_dir() / "yt-dlp.exe"


def ffmpeg() -> Path:
    return bin_dir() / "ffmpeg.exe"


def deno() -> Path:
    return bin_dir() / "deno.exe"


def ffmpeg_version() -> str | None:
    return _version([str(ffmpeg()), "-version"], r"ffmpeg version (\S+)")


def deno_version() -> str | None:
    return _version([str(deno()), "--version"], r"deno (\S+)")


def _version(args: list[str], pattern: str) -> str | None:
    """None when the program is missing, hangs or prints something unexpected."""
    try:
        _, out, _ = run(args, VERSION_TIMEOUT)
    except (OSError, TimeoutError):
        return None
    found = re.match(pattern, out)
    return found.group(1) if found else None
