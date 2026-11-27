"""Starts the app: the backend, the window, and the bridge between them.

Order: build every service, clean up what a previous run left, open the window; when the
window is gone, stop sending events and stop every download. See docs/decisions/0012.
"""

import ctypes
import logging
import platform
import sys
import threading
from pathlib import Path

import webview

from app.bridge.api import BridgeApi
from app.bridge.events import EventSender
from app.composition import build
from app.infrastructure import binaries, webview2
from app.infrastructure.shell import WindowsShell

DEV_URL = "http://localhost:5173"
FROZEN = getattr(sys, "frozen", False)
# Packaged, the data files sit in PyInstaller's folder (_internal), not above this file.
_ROOT = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parents[2]
DIST_INDEX = _ROOT / "frontend" / "dist" / "index.html"
# The installer looks for this name and asks the user to close the app first (installer.iss).
APP_MUTEX = "MediaDownloaderAppMutex"
# The same page installer.iss names when WebView2 is missing.
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
_ARCH = "win-arm64" if platform.machine() == "ARM64" else "win-x64"
_LOADER = Path(webview.__file__).parent / "lib/runtimes" / _ARCH / "native/WebView2Loader.dll"

log = logging.getLogger(__name__)


def show_error(message: str) -> None:
    """There is no page to show the problem in. The only text the backend shows itself;
    there is no language setting to follow yet, so it is in both languages."""
    mb_iconerror = 0x10
    ctypes.windll.user32.MessageBoxW(None, message, "Media Downloader", mb_iconerror)


def ask(message: str) -> bool:
    """Like show_error, with Yes and No; True for Yes."""
    mb_yesno, mb_iconerror, idyes = 0x4, 0x10, 6
    flags = mb_yesno | mb_iconerror
    return bool(ctypes.windll.user32.MessageBoxW(None, message, "Media Downloader", flags) == idyes)


def webview2_message(code: int) -> str:
    return (
        "Media Downloader 無法開啟視窗：這台電腦上的 Microsoft Edge WebView2 Runtime "
        "找不到或無法使用。\n請到微軟網站下載「Evergreen Standalone Installer」，"
        f"安裝後再開啟 Media Downloader：\n{WEBVIEW2_URL}\n要現在開啟下載頁嗎？\n\n"
        "Media Downloader could not open its window: the Microsoft Edge WebView2 Runtime on "
        'this computer is missing or cannot be used.\nDownload the "Evergreen Standalone '
        'Installer" from Microsoft, install it, then open Media Downloader again:\n'
        f"{WEBVIEW2_URL}\nOpen the download page now?\n\n(0x{code:08X})"
    )


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
    # Without this check a broken runtime gives a white, empty window and no word why: pywebview
    # only logs the failure (ADR 0023).
    if (code := webview2.problem(_LOADER)) is not None:
        # FormatError takes a signed 32-bit number; HRESULTs come unsigned.
        text = ctypes.FormatError(code - (1 << 32) if code >= 1 << 31 else code)
        log.error("WebView2 Runtime cannot be used: 0x%08X %s", code, text)
        if ask(webview2_message(code)):
            WindowsShell().open_url(WEBVIEW2_URL)
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
