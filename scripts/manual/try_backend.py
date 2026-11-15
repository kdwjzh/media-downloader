"""A small console for the real back end: type commands, see the events the UI would get.
Not part of CI: it needs the network and the programs in bin/ (python scripts/fetch_binaries.py).

Run from the repository root:

  uv run --project backend python scripts/manual/try_backend.py [--data <folder>]

Settings, history and the log file go to --data (default: media-downloader-manual-data in
%TEMP%), never to the app's real folders, and they stay there between runs. On the first
run the download folder is set to a "downloads" folder inside it.

Commands (n is a number from the last "queue" or "history" list):

  settings                    show the settings
  set <field> <value>         change one, e.g.  set max_concurrent 2 / set on_duplicate skip
                              / set format mp4 / set mp4_height 720 / set language en
  dir <folder>                change the download folder (it must exist)
  add <url> [mp3|mp4] [q]     add to the queue (default: mp3 320)
  queue                       list the queue
  history                     list the history, newest first
  redo <n>                    download history entry n again
  delete <n>                  delete history entry n (the file is not touched)
  clear                       empty the history (files are not touched)
  open <n>                    open the folder of history entry n, with the file selected
  opentask <n>                the same for queue item n
  log                         open the log file          logdir   open its folder
  link releasePage|sourceCode open one of the two fixed web pages
  about                       app version and the third-party components
  update                      update yt-dlp
  check                       is there a newer version of the app
  quit

What to check (the URLs are examples; any YouTube video works):

 1. Settings survive a restart:   set max_concurrent 2  ->  quit  ->  start again  ->  settings
    shows max_concurrent=2. "set max_concurrent 9" is refused and changes nothing.
 2. History:   add https://www.youtube.com/watch?v=jNQXAC9IVRw
               add https://www.youtube.com/watch?v=FtSUD4KDscE
    wait for two "historyAdded" lines, then  history  (2 entries, newest first, each with a
    thumbnail)  ->  delete 1  ->  history (1 left)  ->  redo 1  ->  a new task appears
    as "queued" with its title, and "settings" still shows the format you used last.
 3. Open folder:   open 1   -> File Explorer opens with the file selected.
    Move the file elsewhere,   open 1   -> the folder opens ("folder").
    Rename the download folder,   open 1   -> nothing opens ("none").
 4. Log file:   add https://www.youtube.com/watch?v=yZIXLfi8CZQ   (a private video)
    -> "failed error=private". Then   log   -> the file has a line "task ... failed: private:"
    followed by yt-dlp's own message, and your Windows user name is nowhere in it.
 5. update  -> "updated=False version=..." (or True);   check  -> current version, and no
    latest version while the repository is private.
"""

import argparse
import shlex
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.composition import Backend, Event, build  # noqa: E402
from app.domain.engine import EngineError  # noqa: E402
from app.domain.media import Format  # noqa: E402
from app.services.history import HistoryAdded  # noqa: E402
from app.services.queue import TaskProgress, TasksChanged, TasksRemoved  # noqa: E402
from app.services.settings import SettingsChanged  # noqa: E402

from engine import say  # noqa: E402  (scripts/manual/engine.py)


def on_event(event: Event) -> None:
    if isinstance(event, TasksChanged):
        for item in event.tasks:
            extra = f" error={item.error}" if item.error else ""
            say(f"tasksChanged  [{item.id[:6]}] {item.format} {item.status}{extra}"
                f"  {item.title or item.url}")  # fmt: skip
    elif isinstance(event, TaskProgress):
        if event.progress.percent is not None and event.progress.percent % 25 == 0:
            say(f"taskProgress  [{event.id[:6]}] {event.progress.percent}%")
    elif isinstance(event, TasksRemoved):
        say(f"tasksRemoved  {event.ids}")
    elif isinstance(event, HistoryAdded):
        say(f"historyAdded  {event.entry.format} {event.entry.quality}  {event.entry.title}")
    elif isinstance(event, SettingsChanged):
        say(f"settingsChanged  {event.settings}")


def run(backend: Backend, command: str, args: list[str]) -> None:
    queue_ids = [item.id for item in backend.queue.items()]
    history_ids = [entry.id for entry in backend.history.list()]

    def pick(ids: list[str]) -> str:
        return ids[int(args[0]) - 1]

    if command == "settings":
        print(backend.settings.get())
    elif command == "set":
        value: object = int(args[1]) if args[1].isdigit() else args[1]
        print(backend.settings.update({args[0]: value}))
    elif command == "dir":
        print(backend.settings.set_download_dir(" ".join(args)))
    elif command == "add":
        format = Format(args[1]) if len(args) > 1 else Format.MP3
        quality = int(args[2]) if len(args) > 2 else (320 if format is Format.MP3 else 1080)
        print("task", backend.queue.add([args[0]], format, quality))
    elif command == "queue":
        for n, item in enumerate(backend.queue.items(), 1):
            print(f"  {n}. [{item.id[:6]}] {item.format} {item.quality} {item.status}"
                  f" {item.error or ''}  {item.title or item.url}")  # fmt: skip
    elif command == "history":
        for n, entry in enumerate(backend.history.list(), 1):
            # A data URL is base64: 4 characters for 3 bytes.
            thumb = f"thumbnail {len(entry.thumb) * 3 // 4:,} B" if entry.thumb else "no thumbnail"
            print(f"  {n}. [{entry.id[:6]}] {entry.finished_at} {entry.format} {entry.quality}"
                  f" {entry.size_bytes:,} B  {thumb}  {entry.title}")  # fmt: skip
    elif command == "redo":
        print("new task:", backend.history.redownload(pick(history_ids)))
    elif command == "delete":
        backend.history.delete(pick(history_ids))
    elif command == "clear":
        backend.history.clear()
    elif command == "open":
        print("opened:", backend.external.open_history_folder(pick(history_ids)))
    elif command == "opentask":
        print("opened:", backend.external.open_task_folder(pick(queue_ids)))
    elif command == "log":
        backend.external.open_log_file()
    elif command == "logdir":
        backend.external.open_log_folder()
    elif command == "link":
        backend.external.open_link(args[0])
    elif command == "about":
        about = backend.updates.get_about()
        print("app", about.app_version)
        for component in about.components:
            print(f"  {component.name}  {component.license}  {component.version or '-'}")
    elif command == "update":
        print(backend.updates.update_engine())
    elif command == "check":
        print(backend.updates.check_app_update())
    else:
        print("unknown command; see the top of this file")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--data", default=str(Path(tempfile.gettempdir()) / "media-downloader-manual-data")
    )
    data = Path(parser.parse_args().data)
    first_run = not (data / "data" / "settings.json").exists()
    backend = build(on_event, data / "data", data / "local")
    if first_run:
        (data / "downloads").mkdir(parents=True, exist_ok=True)
        backend.settings.set_download_dir(str(data / "downloads"))
    backend.start()
    print(f"data folder: {data}\ndownload folder: {backend.settings.download_dir}")
    try:
        while True:
            try:
                # posix=False: backslashes in a Windows path stay as they are.
                words = shlex.split(input("> "), posix=False)
            except EOFError:
                break
            if not words:
                continue
            if words[0] in ("quit", "exit"):
                break
            try:
                run(backend, words[0], [word.strip('"') for word in words[1:]])
            except EngineError as error:
                print(f"refused: {error.code}")
            except (ValueError, IndexError, OSError) as error:
                print(f"refused: {error}")
    finally:
        backend.shutdown()


if __name__ == "__main__":
    main()
