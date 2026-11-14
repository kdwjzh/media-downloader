"""Where the bundled external programs live. The only place that knows these paths."""

import sys
from pathlib import Path


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
