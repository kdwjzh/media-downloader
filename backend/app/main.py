"""Starts the app: the backend, the window, and the bridge between them.

Order: build every service, clean up what a previous run left, open the window; when the
window is gone, stop sending events and stop every download. See docs/decisions/0012.
"""

import ctypes
import logging
import sys
from pathlib import Path

import webview

from app.bridge.api import BridgeApi
from app.bridge.events import EventSender
from app.composition import build

DEV_URL = "http://localhost:5173"
DIST_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html"

log = logging.getLogger(__name__)


def fatal(error: Exception) -> None:
    """The window could not be built, so there is no page to show the problem in. The only
    text the backend shows itself; there is no language setting to follow yet."""
    message = (
        "Media Downloader 無法啟動。\nMedia Downloader could not start.\n\n"
        f"{type(error).__name__}: {error}"
    )
    mb_iconerror = 0x10
    ctypes.windll.user32.MessageBoxW(None, message, "Media Downloader", mb_iconerror)


def main() -> None:
    dev = "--dev" in sys.argv[1:]
    if not dev and not DIST_INDEX.is_file():
        sys.exit("frontend/dist not found: run `npm run build` in frontend/, or start with --dev")

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
