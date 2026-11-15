"""Stage 3e checks that need the real back end (app/composition.py's build()), the network
and the programs in bin/. Not part of CI. Everything goes to a media-downloader-3e folder in
%TEMP% (settings, history, log file, downloads), never to the app's real folders.

Run from the repository root:

  uv run --project backend python scripts/manual/stage3e.py concurrency [--rounds 2]
          [--counts 3 4 5] [--format mp4] [--quality 480]
      the same five videos with N downloads at a time; prints one table.
  uv run --project backend python scripts/manual/stage3e.py watch <url> [--format mp4]
      one download with every event printed; waits for Enter before a failed task is
      retried. For the tests where the author switches Wi-Fi off and on.
  uv run --project backend python scripts/manual/stage3e.py duplicates
      the same video three times, once per duplicate rule, then again from the history.
  uv run --project backend python scripts/manual/stage3e.py shutdown
      calls shutdown() in the middle of a download.
  uv run --project backend python scripts/manual/stage3e.py crash
      starts a child that downloads, kills the child, then starts the back end again.
  uv run --project backend python scripts/manual/stage3e.py open
      downloads one file, selects it in Explorer, moves it away and opens again.
  uv run --project backend python scripts/manual/stage3e.py lookup <url>...
      what lookup() returns or raises for each URL.
  uv run --project backend python scripts/manual/stage3e.py update
      update_engine() and the versions before and after.
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.composition import Backend, Event, build  # noqa: E402
from app.domain.engine import EngineError  # noqa: E402
from app.domain.media import Format, PlaylistInfo  # noqa: E402
from app.domain.task import TaskStatus  # noqa: E402
from app.services.history import HistoryAdded  # noqa: E402
from app.services.queue import QueueItem, TaskProgress, TasksChanged  # noqa: E402

from engine import leftovers, say  # noqa: E402  (scripts/manual/engine.py)

ROOT = Path(tempfile.gettempdir()) / "media-downloader-3e"
ENDED = (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)
VIDEOS = [  # 5 to 15 minutes each
    "https://www.youtube.com/watch?v=eRsGyueVLvQ",
    "https://www.youtube.com/watch?v=R6MlUcmOul8",
    "https://www.youtube.com/watch?v=LXb3EKWsInQ",
    "https://www.youtube.com/watch?v=YE7VzlLtp-4",
    "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
]
SHORT = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # 19 s
LONG_AUDIO = "https://www.youtube.com/watch?v=lzmSKX5TF3g"  # one hour


def describe(item: QueueItem) -> str:
    extra = "".join(
        f" {name}={value}"
        for name, value in (
            ("error", item.error),
            ("attempt", item.attempt),
            ("percent", item.progress and item.progress.percent),
            ("size", item.size_bytes),
            ("skipped", item.skipped or None),
        )
        if value is not None
    )
    return f"[{item.id[:6]}] {item.format} {item.status:<11}{extra}  {item.title or item.url}"


def printer(event: Event) -> None:
    if isinstance(event, TasksChanged):
        for item in event.tasks:
            say(f"tasksChanged  {describe(item)}")
    elif isinstance(event, TaskProgress):
        p = event.progress
        say(f"taskProgress  [{event.id[:6]}] {p.percent}%  {p.done_bytes:,} / {p.total_bytes}")
    elif isinstance(event, HistoryAdded):
        say(f"historyAdded  {event.entry.format} {event.entry.quality} {event.entry.title}")
    else:
        say(f"{type(event).__name__}  {event}")


def start(emit: Callable[[Event], None], name: str, fresh: bool = True) -> tuple[Backend, Path]:
    """A back end of its own under ROOT/name, saving to ROOT/name/downloads."""
    base = ROOT / name
    if fresh:
        shutil.rmtree(base, ignore_errors=True)
    dest = base / "downloads"
    dest.mkdir(parents=True, exist_ok=True)
    backend = build(emit, base / "data", base / "local")
    backend.settings.set_download_dir(str(dest))
    backend.start()
    return backend, dest


def wait_ended(backend: Backend, limit: float = 30 * 60) -> None:
    started = time.monotonic()
    while time.monotonic() - started < limit:
        time.sleep(0.5)
        if all(item.status in ENDED for item in backend.queue.items()):
            time.sleep(1)  # let the last events arrive
            return
    say("-- TIME LIMIT reached")


def concurrency(rounds: int, counts: list[int], format: Format, quality: int) -> None:
    began: dict[str, float] = {}
    ended: dict[str, float] = {}
    size: dict[str, int] = {}
    retries: dict[str, int] = {}

    def on_event(event: Event) -> None:
        now = time.monotonic()
        if isinstance(event, TaskProgress) and event.progress.done_bytes:
            size[event.id] = event.progress.done_bytes
        elif isinstance(event, TasksChanged):
            for item in event.tasks:
                if item.status == TaskStatus.DOWNLOADING:
                    began.setdefault(item.id, now)
                elif item.status == TaskStatus.RETRYING:
                    retries[item.id] = max(retries.get(item.id, 0), item.attempt or 1)
                elif item.id in began:
                    ended.setdefault(item.id, now)

    backend, dest = start(on_event, "concurrency")
    rows = []
    try:
        say("-- looking the videos up first, so every task starts as queued")
        threads = [threading.Thread(target=backend.media_info.lookup, args=(u,)) for u in VIDEOS]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        for round_no in range(1, rounds + 1):
            for count in counts:
                backend.settings.update({"max_concurrent": count})
                ids = backend.queue.add(VIDEOS, format, quality, remember=False)
                wait_ended(backend)
                items = {item.id: item for item in backend.queue.items()}
                ok = [i for i in ids if items[i].status == TaskStatus.DONE and i in size]
                speeds = [size[i] / (ended[i] - began[i]) / 1e6 for i in ok]
                done_mb = sum(size[i] for i in ok) / 1e6
                span = max(ended[i] for i in ids) - min(began[i] for i in ids)
                failed = [f"{items[i].error}" for i in ids if items[i].status != TaskStatus.DONE]
                row = (round_no, count, done_mb, span, done_mb / span,
                       sum(speeds) / len(speeds) if speeds else 0.0,
                       min(speeds, default=0.0), sum(retries.get(i, 0) for i in ids), failed)  # fmt: skip
                rows.append(row)
                say(f"-- round {round_no}, {count} at once: {row}")
                backend.queue.clear_finished()
                for path in dest.iterdir():
                    path.unlink()
    finally:
        backend.shutdown()
    print("\nround | at once | MB | seconds | total MB/s | average MB/s each | slowest MB/s | retries | failed")
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]:.0f} | {r[3]:.0f} | {r[4]:.2f} | {r[5]:.2f} | {r[6]:.2f} | {r[7]} | {r[8] or 'none'}")
    log_text = (ROOT / "concurrency" / "local" / "logs" / "app.log").read_text(encoding="utf-8")
    for needle in ("403", "429", "Too Many", "rate"):
        print(f"log lines mentioning {needle!r}: {sum(needle in line for line in log_text.splitlines())}")
    leftovers(dest)


def watch(url: str, format: Format) -> None:
    backend, dest = start(printer, "watch")
    try:
        (task_id,) = backend.queue.add([url], format, 320 if format == Format.MP3 else 1080)
        while True:
            wait_ended(backend)
            item = backend.queue.items()[0]
            if item.status != TaskStatus.FAILED:
                break
            input(f"\nfailed with {item.error}. Press Enter to retry it...\n")
            backend.queue.retry(task_id)
        print("\nfinal:", describe(backend.queue.items()[0]))
        print("history entries:", len(backend.history.list()))
    finally:
        backend.shutdown()
    leftovers(dest)


def duplicates() -> None:
    backend, dest = start(printer, "duplicates")
    try:
        say("-- first download, MP3 192 (the last used format becomes mp3 192)")
        backend.queue.add([SHORT], Format.MP3, 192)
        wait_ended(backend)
        for rule in ("skip", "overwrite", "rename"):
            say(f"-- again with on_duplicate={rule}")
            backend.settings.update({"on_duplicate": rule})
            backend.queue.add([SHORT], Format.MP3, 192)
            wait_ended(backend)
            print("   files:", sorted(p.name for p in dest.iterdir()),
                  "| history entries:", len(backend.history.list()))  # fmt: skip
        say("-- change the last used format to mp4 720, then download again from the oldest history entry")
        backend.settings.update({"format": "mp4", "mp4_height": 720})
        oldest = backend.history.list()[-1]
        before = len(backend.history.list())
        new_id = backend.history.redownload(oldest.id)
        new = next(item for item in backend.queue.items() if item.id == new_id)
        print(f"   new task: {describe(new)} quality={new.quality}")
        wait_ended(backend)
        entries = backend.history.list()
        print(f"   history entries: {before} -> {len(entries)}; newest: {entries[0].format} {entries[0].quality}")
        print("   settings now:", backend.settings.get())
        print("\nfinal queue:")
        for item in backend.queue.items():
            print("  " + describe(item))
    finally:
        backend.shutdown()
    leftovers(dest)


def shutdown() -> None:
    seen = threading.Event()

    def on_event(event: Event) -> None:
        printer(event)
        if isinstance(event, TaskProgress) and (event.progress.percent or 0) >= 5:
            seen.set()

    backend, dest = start(on_event, "shutdown")
    backend.queue.add([*VIDEOS[:2], LONG_AUDIO], Format.MP4, 1080)
    backend.queue.add([LONG_AUDIO], Format.MP3, 320)  # waits its turn: 3 at a time
    seen.wait(120)
    say("-- shutdown() now, with downloads running")
    began = time.monotonic()
    backend.shutdown()
    say(f"-- shutdown() returned after {time.monotonic() - began:.2f} s")
    leftovers(dest)


def crash(child: bool) -> None:
    if child:  # downloads until it is killed
        backend, _ = start(printer, "crash")
        backend.queue.add(VIDEOS[:2], Format.MP4, 1080)
        time.sleep(600)
        return
    dest = ROOT / "crash" / "downloads"
    process = subprocess.Popen([sys.executable, __file__, "crash", "--child"], stdout=subprocess.PIPE,
                               text=True, encoding="utf-8")  # fmt: skip
    assert process.stdout
    for line in process.stdout:
        print("   child:", line.rstrip())
        found = re.search(r"taskProgress .* (\d+)%", line)
        if found and int(found[1]) >= 3:
            break
    say("-- killing the child (TerminateProcess, no cleanup runs)")
    process.kill()
    process.wait()
    time.sleep(2)
    leftovers(dest)
    say("-- starting the back end again on the same folders")
    backend, _ = start(printer, "crash", fresh=False)
    print("   queue after restart:", backend.queue.items())
    leftovers(dest)
    backend.shutdown()
    leftovers(dest)


def open_folder() -> None:
    backend, dest = start(printer, "open")
    try:
        (task_id,) = backend.queue.add([SHORT], Format.MP3, 192)
        wait_ended(backend)
        entry = backend.history.list()[0]
        print("open_task_folder ->", backend.external.open_task_folder(task_id))
        input("Is the MP3 selected in the Explorer window? Close it, then press Enter...")
        print("open_history_folder ->", backend.external.open_history_folder(entry.id))
        input("Selected again? Close it, then press Enter (the file will be moved away)...")
        for path in dest.glob("*.mp3"):
            path.rename(ROOT / "open" / path.name)
        print("file moved; open_task_folder ->", backend.external.open_task_folder(task_id))
        input("Did the downloads folder open, with nothing selected? Close it, then press Enter...")
        moved = ROOT / "open" / "downloads-moved"
        backend.shutdown()
        dest.rename(moved)
        print("folder gone; open_history_folder ->", backend.external.open_history_folder(entry.id))
        print("(nothing should have opened)")
    finally:
        backend.shutdown()


def lookup(urls: list[str]) -> None:
    backend, _ = start(printer, "lookup")
    try:
        for url in urls:
            try:
                result = backend.media_info.lookup(url)
            except EngineError as error:
                print(f"{url}\n  -> EngineError {error.code}")
                continue
            if isinstance(result, PlaylistInfo):
                print(f"{url}\n  -> playlist {result.title!r}, {len(result.entries)} entries")
                for entry in result.entries:
                    if not entry.available or entry.duration_sec is None:
                        print("    ", entry)
            else:
                print(f"{url}\n  -> video {result.title!r} {result.duration_sec}s")
    finally:
        backend.shutdown()
    print("log file:", ROOT / "lookup" / "local" / "logs" / "app.log")


def update() -> None:
    backend, _ = start(printer, "update")
    try:
        print("about before:", backend.updates.get_about().components[0])
        try:
            print("update_engine ->", backend.updates.update_engine())
        except EngineError as error:
            print("update_engine raised EngineError", error.code)
        print("about after: ", backend.updates.get_about().components[0])
    finally:
        backend.shutdown()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("what", choices=["concurrency", "watch", "duplicates", "shutdown", "crash",
                                         "open", "lookup", "update"])  # fmt: skip
    parser.add_argument("urls", nargs="*")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--counts", type=int, nargs="+", default=[3, 4, 5])
    parser.add_argument("--quality", type=int, default=480)
    parser.add_argument("--format", default="mp4", choices=["mp3", "mp4"])
    parser.add_argument("--child", action="store_true")
    args = parser.parse_args()
    if args.what == "concurrency":
        concurrency(args.rounds, args.counts, Format(args.format), args.quality)
    elif args.what == "watch":
        watch(args.urls[0], Format(args.format))
    elif args.what == "duplicates":
        duplicates()
    elif args.what == "shutdown":
        shutdown()
    elif args.what == "crash":
        crash(args.child)
    elif args.what == "open":
        open_folder()
    elif args.what == "lookup":
        lookup(args.urls)
    else:
        update()


if __name__ == "__main__":
    main()
