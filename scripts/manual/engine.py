"""Drives the real yt-dlp engine against real URLs and prints every event it reports.
Not part of CI: it needs the network and the programs in bin/ (python scripts/fetch_binaries.py).

Run from the repository root:

  uv run --project backend python scripts/manual/engine.py info <url>
  uv run --project backend python scripts/manual/engine.py mp3 <url> [--quality 320]
  uv run --project backend python scripts/manual/engine.py mp4 <url> [--quality 1080]
  uv run --project backend python scripts/manual/engine.py cancel-download [<url>]
  uv run --project backend python scripts/manual/engine.py cancel-convert [<url>]
  uv run --project backend python scripts/manual/engine.py version
  uv run --project backend python scripts/manual/engine.py update

Options for mp3 / mp4 / cancel-*:
  --dest <folder>          where to save (default: a media-downloader-manual folder in %TEMP%)
  --on-duplicate skip|overwrite|rename      (default: rename)

cancel-download cancels 3 s after the first progress event; cancel-convert cancels 1 s after
conversion starts. Without a URL they use a long 4K video and a one-hour audio track.
After every run the script lists what is left in the folder and which of our processes
are still alive (both should show nothing unexpected).
"""

import argparse
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.domain.engine import (  # noqa: E402
    DownloadCancelled,
    DownloadRequest,
    EngineError,
    EngineEvent,
    FileProgress,
    OnDuplicate,
    PostProcessing,
)
from app.domain.media import Format, PlaylistInfo  # noqa: E402
from app.infrastructure import binaries  # noqa: E402
from app.infrastructure.engines.ytdlp.engine import YtDlpEngine  # noqa: E402

LONG_VIDEO = "https://www.youtube.com/watch?v=LXb3EKWsInQ"
LONG_AUDIO = "https://www.youtube.com/watch?v=lzmSKX5TF3g"
START = time.perf_counter()


def say(text: str) -> None:
    print(f"{time.perf_counter() - START:6.1f}s  {text}", flush=True)


def leftovers(dest: Path) -> None:
    print("\nin the folder now:")
    for path in sorted(dest.rglob("*")):
        print(f"  {path.stat().st_size:>12,}  {path.relative_to(dest)}")
    script = (
        "(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '"
        + str(binaries.bin_dir())
        + "\\*' } | ForEach-Object { $_.Name }) -join ', '"
    )
    alive = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True,
                           text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()  # fmt: skip
    print("our processes still alive:", alive or "none")


def lookup(engine: YtDlpEngine, url: str) -> None:
    info = engine.fetch_info(url)
    say(f"looked up: {type(info).__name__}")
    if isinstance(info, PlaylistInfo):
        print(f"  title={info.title!r} channel={info.channel!r} entries={len(info.entries)} "
              f"unavailable={sum(not e.available for e in info.entries)}")  # fmt: skip
        for entry in info.entries[:5]:
            print("  ", entry)
        return
    print(f"  title={info.title!r} channel={info.channel!r} duration={info.duration_sec}s "
          f"platform={info.platform}\n  thumb={info.thumb}")  # fmt: skip
    for option in info.options:
        size = "unknown" if option.size_bytes is None else f"{option.size_bytes / 1e6:.1f} MB"
        print(f"  {option.format} {option.quality}: {size}")


def download(engine: YtDlpEngine, options: argparse.Namespace, format: Format, url: str,
             cancel_on: type | None = None, cancel_after: float = 0) -> None:  # fmt: skip
    dest = Path(options.dest)
    dest.mkdir(parents=True, exist_ok=True)
    quality = options.quality or (320 if format is Format.MP3 else 1080)
    request = DownloadRequest("manual1", url, format, quality, str(dest),
                              OnDuplicate(options.on_duplicate))  # fmt: skip
    state = {"progress": 0, "armed": False}

    def on_event(event: EngineEvent) -> None:
        if isinstance(event, FileProgress):
            state["progress"] += 1
            if state["progress"] % 25 != 1:  # every 25th line is plenty to read
                return
        say(str(event))
        if cancel_on and isinstance(event, cancel_on) and not state["armed"]:
            state["armed"] = True
            say(f"-- will cancel in {cancel_after} s")
            threading.Timer(cancel_after, lambda: (say("-- cancel()"), engine.cancel("manual1"))).start()

    try:
        result = engine.download(request, on_event)
        say(f"{state['progress']} progress events in total")
        say(f"RESULT {result}")
    except DownloadCancelled:
        say("CANCELLED (DownloadCancelled raised)")
    leftovers(dest)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("action", choices=["info", "mp3", "mp4", "cancel-download", "cancel-convert",
                                           "version", "update"])  # fmt: skip
    parser.add_argument("url", nargs="?")
    parser.add_argument("--quality", type=int)
    parser.add_argument("--dest", default=str(Path(tempfile.gettempdir()) / "media-downloader-manual"))
    parser.add_argument("--on-duplicate", default="rename", choices=[d.value for d in OnDuplicate])
    options = parser.parse_args()
    engine = YtDlpEngine()
    try:
        if options.action == "version":
            say(f"version {engine.version()}")
        elif options.action == "update":
            say(f"updated: {engine.update()}; version now {engine.version()}")
        elif options.action == "cancel-download":
            download(engine, options, Format.MP4, options.url or LONG_VIDEO, FileProgress, 3)
        elif options.action == "cancel-convert":
            download(engine, options, Format.MP3, options.url or LONG_AUDIO, PostProcessing, 1)
        elif not options.url:
            parser.error("this action needs a URL")
        elif options.action == "info":
            lookup(engine, options.url)
        else:
            download(engine, options, Format(options.action), options.url)
    except EngineError as error:
        say(f"ENGINE ERROR code={error.code}")
        print("detail:", error.detail[-1500:])


if __name__ == "__main__":
    main()
