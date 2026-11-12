"""Throwaway helpers for the stage 1 spikes. Not part of the app; do not import from backend/."""

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "bin"
OUT = Path(tempfile.gettempdir()) / "media-downloader-spike"
NO_WINDOW = subprocess.CREATE_NO_WINDOW

# Short public videos.
ZOO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 19 s, 4:3, max 240p
UHD = "https://www.youtube.com/watch?v=2PuFyjAs7JA"  # 11 s, up to 2160p
SHORT = "https://www.youtube.com/watch?v=g4rArHjS30k"  # vertical
ZH = "https://www.youtube.com/watch?v=FtSUD4KDscE"  # 43 s, Chinese title, 16:9
LONG = "https://www.youtube.com/watch?v=LXb3EKWsInQ"  # 5 min 4K, big enough to cancel
PLAYLIST = "https://www.youtube.com/playlist?list=PL4fGSI1pDJn6puJdseH2Rt9sMvt9E2M4i"

BASE = [
    str(BIN / "yt-dlp.exe"),
    "--ignore-config",
    "--js-runtimes",
    f"deno:{BIN / 'deno.exe'}",  # must be absolute: a relative path is not found
    "--ffmpeg-location",
    str(BIN),
    "--color",
    "never",
    "--encoding",
    "utf-8",
]

PROGRESS = [
    "--progress",  # --print implies --quiet, which hides download progress without this
    "--newline",
    "--progress-template",
    "download:DL %(info.{id,format_id})j %(progress.{status,downloaded_bytes,total_bytes,"
    "total_bytes_estimate,fragment_index,fragment_count,speed,eta,elapsed})j",
    "--progress-template",
    "postprocess:PP %(info.{id})j %(progress.{status,postprocessor})j",
]


def run(args: list[str], base: list[str] = BASE, **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*base, *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
        **kwargs,
    )


def popen(args: list[str], **kwargs) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [*BASE, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
        **kwargs,
    )


def fresh(name: str) -> Path:
    """Empty output folder for one spike."""
    import shutil

    path = OUT / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True)
    return path


if sys.stdout:  # None under pythonw.exe started without redirection
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
