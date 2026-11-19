"""Starts the app: the backend, the window, and the bridge between them.

Order: build every service, clean up what a previous run left, open the window; when the
window is gone, stop sending events and stop every download. See docs/decisions/0012.
"""

import ctypes
import logging
import sys
import threading
from pathlib import Path

import webview

from app.bridge.api import BridgeApi
from app.bridge.events import EventSender
from app.composition import build
from app.infrastructure import binaries

DEV_URL = "http://localhost:5173"
FROZEN = getattr(sys, "frozen", False)
# Packaged, the data files sit in PyInstaller's folder (_internal), not above this file.
_ROOT = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parents[2]
DIST_INDEX = _ROOT / "frontend" / "dist" / "index.html"
# The installer looks for this name and asks the user to close the app first (installer.iss).
APP_MUTEX = "MediaDownloaderAppMutex"

log = logging.getLogger(__name__)


def show_error(message: str) -> None:
    """There is no page to show the problem in. The only text the backend shows itself;
    there is no language setting to follow yet, so it is in both languages."""
    mb_iconerror = 0x10
    ctypes.windll.user32.MessageBoxW(None, message, "Media Downloader", mb_iconerror)


def fatal(error: Exception) -> None:
    show_error(
        "Media Downloader 無法啟動。\nMedia Downloader could not start.\n\n"
        f"{type(error).__name__}: {error}"
    )


def missing_message(names: list[str]) -> str:
    return (
        f"找不到 {'、'.join(names)}，可能被防毒軟體移除了。請重新安裝 Media Downloader。\n\n"
        f"{', '.join(names)} could not be found; antivirus software may have removed it. "
        "Install Media Downloader again."
    )


def main() -> None:
    dev = "--dev" in sys.argv[1:]
    if not dev and not DIST_INDEX.is_file():
        sys.exit("frontend/dist not found: run `npm run build` in frontend/, or start with --dev")
    if gone := binaries.missing():
        if not FROZEN:
            sys.exit(f"{', '.join(gone)} not in bin/: run python scripts/fetch_binaries.py")
        show_error(missing_message(gone))  # reinstalling puts a missing program back
        sys.exit(1)
    if FROZEN:
        # Held until the process ends; Windows closes it then.
        ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX)

    # The bridge needs the window and the window needs the bridge: these look it up late.
    window: webview.Window | None = None
    api: BridgeApi | None = None

    def run_js(script: str) -> object:
        assert window is not None
        return window.evaluate_js(script)

    def destroy() -> None:
        if window is not None:
            window.destroy()

    def close_now() -> None:
        if api is not None:
            api._close_now()  # main.py owns the window

    def choose_folder(start: str) -> str | None:
        assert window is not None
        chosen = window.create_file_dialog(webview.FileDialog.FOLDER, directory=start)
        return chosen[0] if chosen else None

    events = EventSender(run_js, close_now)
    try:
        backend = build(events.emit)
    except Exception as error:
        log.exception("could not start")  # reaches the log file if logging got that far
        fatal(error)
        sys.exit(1)
    backend.start()
    if FROZEN:
        # Only the installed app: development keeps the yt-dlp in bin/ that the recorded
        # test samples came from (ADR 0019).
        threading.Thread(target=backend.updates.auto_update_engine, daemon=True).start()

    api = BridgeApi(backend, events, choose_folder, destroy)
    created = webview.create_window(
        "Media Downloader",
        DEV_URL if dev else str(DIST_INDEX),
        js_api=api,
        # Sizes come from design-system/media-downloader/MASTER.md section 5.
        width=960,
        height=680,
        min_size=(720, 520),
    )
    assert created is not None  # never None here; the annotation allows it
    window = created
    created.events.closing += api._on_closing
    try:
        webview.start(events.start, debug=dev)
    finally:
        events.close()
        backend.shutdown()


if __name__ == "__main__":
    main()
