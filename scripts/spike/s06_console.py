"""Item 11: does a console window appear when a windowless program runs yt-dlp and FFmpeg?

Run with pythonw.exe (no console of its own), like the packaged app:
    pythonw scripts/spike/s06_console.py
Result: %TEMP%/media-downloader-spike/console.txt

While each command runs, a thread polls the visible top-level windows and records
any console window (classic conhost or Windows Terminal) that was not there before.
"""

import ctypes
import subprocess
import threading
import time
from ctypes import wintypes

from common import BASE, BIN, OUT, ZOO, fresh

user32 = ctypes.windll.user32
CONSOLE_CLASSES = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS"}
ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def consoles() -> set[int]:
    found: set[int] = set()

    def visit(hwnd: int, _: int) -> bool:
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, name, 64)
        if name.value in CONSOLE_CLASSES and user32.IsWindowVisible(hwnd):
            found.add(hwnd)
        return True

    user32.EnumWindows(ENUM(visit), 0)
    return found


def watch(label: str, command: list[str], flags: int) -> str:
    before = consoles()
    seen: set[int] = set()
    done = threading.Event()

    def poll() -> None:
        while not done.is_set():
            seen.update(consoles() - before)
            time.sleep(0.005)

    thread = threading.Thread(target=poll)
    thread.start()
    result = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL, creationflags=flags)
    done.set()
    thread.join()
    return f"{label}: exit={result.returncode} new console windows seen={len(seen)}"


if __name__ == "__main__":
    folder = fresh("console")
    download = [*BASE, "-f", "ba/b", "-x", "--audio-format", "mp3", "--embed-thumbnail",
                "--no-playlist", "-P", str(folder), ZOO]  # fmt: skip
    ffmpeg = [str(BIN / "ffmpeg.exe"), "-version"]
    lines = [f"own console attached: {bool(ctypes.windll.kernel32.GetConsoleWindow())}"]
    for name, flags in (("CREATE_NO_WINDOW", subprocess.CREATE_NO_WINDOW), ("no flag (control)", 0)):
        lines.append(watch(f"yt-dlp + deno + ffmpeg (MP3 download), {name}", download, flags))
        lines.append(watch(f"ffmpeg -version, {name}", ffmpeg, flags))
    (OUT / "console.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
