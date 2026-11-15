"""Runs the real back end (everything app/composition.py builds: the queue, the yt-dlp engine,
settings and history on real files) through one fixed scenario and prints every event the UI
would receive.
Not part of CI: it needs the network and the programs in bin/ (python scripts/fetch_binaries.py).
Settings, history and the log file go to a media-downloader-manual-queue-data folder in
%TEMP%, never to the app's real folders; the history there is emptied at the start.

Run from the repository root (takes a few minutes, downloads about 150 MB):

  uv run --project backend python scripts/manual/download_queue.py [--dest <folder>]

  --dest   where to save (default: a media-downloader-manual-queue folder in %TEMP%)

What it does, and what to look for:

 1. Adds 5 URLs by URL alone (2 as MP4 1080, 3 as MP3 320) with 3 downloads at a time.
    -> each appears as "fetching", gets its title ("queued"), and at most 3 are
       "downloading" at once. Progress lines of one task are at least 0.5 s apart.
 2. Adds a watch URL without a video id, and a private video.
    -> the first ends "failed error=invalidUrl", the second "failed error=private".
    Also tries to add text that is no URL at all -> add() itself refuses with invalidUrl.
 3. 3 s after the long video (the first URL) reports progress: cancels it, and lowers the
    number of simultaneous downloads to 1.
    -> it is "cancelled" at once; the downloads already running continue; from then on a
       new one only starts when nothing else is downloading ("downloading now" stays <= 1
       once the running ones have ended).
 4. 5 s later: adds the cancelled one again.
    -> same id, same place, "queued", later "downloading" from 0 %, and "done" in the end.
 5. When everything has ended: prints the final queue, the history as it is read back from
    the database (5 entries, each with a small thumbnail of a few KB), what is left in the
    folder (only finished files, no .md-tmp-* folders) and which of our processes are still
    alive (none).

Every percentage of one download only grows; an MP4 runs from 0 to 100 once.
"""

import argparse
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.composition import Event, build  # noqa: E402
from app.domain.engine import EngineError  # noqa: E402
from app.domain.media import Format  # noqa: E402
from app.domain.task import TaskStatus  # noqa: E402
from app.services.history import HistoryAdded  # noqa: E402
from app.services.queue import QueueItem, TaskProgress, TasksChanged, TasksRemoved  # noqa: E402

from engine import leftovers, say  # noqa: E402  (scripts/manual/engine.py)

LONG = "https://www.youtube.com/watch?v=LXb3EKWsInQ"  # 5 min, 4K: long enough to cancel
MP4_URLS = [LONG, "https://www.youtube.com/watch?v=2PuFyjAs7JA"]  # + 11 s, up to 2160p
MP3_URLS = [
    "https://www.youtube.com/watch?v=FtSUD4KDscE",  # 43 s, Chinese title
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",  # 19 s
    "https://www.youtube.com/watch?v=g4rArHjS30k",  # vertical
]
NO_VIDEO_ID = "https://www.youtube.com/watch"
PRIVATE = "https://www.youtube.com/watch?v=yZIXLfi8CZQ"
TIME_LIMIT = 20 * 60


def describe(item: QueueItem) -> str:
    extra = "".join(
        f" {name}={value}"
        for name, value in (
            ("error", item.error),
            ("attempt", item.attempt),
            ("size", item.size_bytes),
            ("skipped", item.skipped or None),
        )
        if value is not None
    )
    return f"[{item.id[:6]}] {item.format} {item.status:<11}{extra}  {item.title or item.url}"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--dest", default=str(Path(tempfile.gettempdir()) / "media-downloader-manual-queue"))
    dest = Path(parser.parse_args().dest)
    dest.mkdir(parents=True, exist_ok=True)

    step = {"cancel": False, "readded": False}
    long_id: list[str] = []

    def downloading_now() -> int:
        active = (TaskStatus.DOWNLOADING, TaskStatus.RETRYING, TaskStatus.CONVERTING, TaskStatus.MERGING)
        return sum(item.status in active for item in service.items())

    def cancel_and_lower() -> None:
        say("-- cancel the long video")
        service.cancel(long_id[0])
        say("-- from now on: 1 download at a time (running ones are not stopped)")
        backend.settings.update({"max_concurrent": 1})  # the settings tell the queue
        threading.Timer(5, readd).start()

    def readd() -> None:
        say("-- add the cancelled one again")
        service.readd(long_id[0])
        step["readded"] = True

    def on_event(event: Event) -> None:
        if isinstance(event, TasksChanged):
            for item in event.tasks:
                say(f"tasksChanged  {describe(item)}   (downloading now: {downloading_now()})")
        elif isinstance(event, TaskProgress):
            p = event.progress
            speed = None if p.speed_bps is None else f"{round(p.speed_bps):,}"
            say(f"taskProgress  [{event.id[:6]}] {p.percent}%  {p.done_bytes:,} / {p.total_bytes}"
                f"  speed={speed}  eta={p.eta_sec}")  # fmt: skip
            if long_id and event.id == long_id[0] and not step["cancel"]:
                step["cancel"] = True
                say("-- will cancel the long video in 3 s")
                threading.Timer(3, cancel_and_lower).start()
        elif isinstance(event, TasksRemoved):
            say(f"tasksRemoved  {event.ids}")
        elif isinstance(event, HistoryAdded):
            say(f"historyAdded  {event.entry.format} {event.entry.title}")
        else:
            say(f"settingsChanged  {event.settings}")

    data = Path(tempfile.gettempdir()) / "media-downloader-manual-queue-data"
    backend = build(on_event, data / "data", data / "local")
    service = backend.queue
    backend.history.clear()
    backend.settings.set_download_dir(str(dest))
    backend.settings.update({"max_concurrent": 3})
    backend.start()
    try:
        long_id += service.add(MP4_URLS, Format.MP4, 1080)[:1]
        service.add(MP3_URLS, Format.MP3, 320)
        service.add([NO_VIDEO_ID, PRIVATE], Format.MP3, 320)
        try:
            service.add(["this is not a url"], Format.MP3, 320)
        except EngineError as error:
            say(f"-- add() refused text that is no URL: {error.code}")
        say(f"-- last used format, as remembered: {backend.settings.get()}")

        started = time.monotonic()
        while time.monotonic() - started < TIME_LIMIT:
            time.sleep(1)
            waiting_for_readd = step["cancel"] and not step["readded"]
            if not waiting_for_readd and all(
                item.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)
                for item in service.items()
            ):
                break
        else:
            say("-- TIME LIMIT reached; stopping")
        time.sleep(1)  # let the last events print
        print("\nfinal queue:")
        for item in service.items():
            print("  " + describe(item), "->", service.file_path(item.id))
        entries = backend.history.list()
        print(f"\nhistory, newest first ({len(entries)} entries):")
        for entry in entries:
            # A data URL is base64: 4 characters for 3 bytes.
            thumb = f"thumbnail {len(entry.thumb) * 3 // 4:,} bytes" if entry.thumb else "NO THUMBNAIL"
            print(f"  {entry.finished_at} {entry.format} {entry.quality} {entry.size_bytes:>12,}"
                  f"  {thumb}  {entry.title}")  # fmt: skip
    finally:
        backend.shutdown()
    leftovers(dest)
    print(f"\nsettings, history and log file: {data}")


if __name__ == "__main__":
    main()
