"""Stage 3b, experiment A: duplicate file names, and file names from odd titles.

Questions: is the final name known before data moves? Does yt-dlp's own skip work for MP3?
Can everything finish in a per-task folder and be moved by us afterwards?
"""

import json
import subprocess
import time

from common import NO_WINDOW, PROGRESS, ZH, ZOO, fresh, popen, run

NAME = ["-o", "%(title)s.%(ext)s", "--windows-filenames", "--no-playlist"]
MP3 = ["-f", "ba/b", "-x", "--audio-format", "mp3", "--embed-thumbnail"]
MP4 = ["-S", "res:1080,vcodec:h264,acodec:m4a", "--merge-output-format", "mp4"]


def listing(folder) -> None:  # type: ignore[no-untyped-def]
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            print(f"    {path.stat().st_size:>11,}  {path.relative_to(folder)}")


def json_has_filename() -> None:
    data = json.loads(run(["-J", *NAME, *MP3, ZOO]).stdout)
    print("\n## -J keys with 'file' in them:", [k for k in data if "file" in k])


def own_skip(label: str, fmt: list[str], flag: list[str]) -> None:
    folder = fresh("skip")
    paths = ["-P", f"home:{folder}", "-P", f"temp:{folder / '.tmp'}"]
    run([*fmt, *NAME, *paths, ZOO])
    before = {p.name: p.stat().st_mtime_ns for p in folder.iterdir() if p.is_file()}
    start = time.perf_counter()
    second = run([*fmt, *NAME, *paths, *flag, ZOO])
    after = {p.name: p.stat().st_mtime_ns for p in folder.iterdir() if p.is_file()}
    print(f"\n## yt-dlp's own skip, {label} {flag}: second run exit={second.returncode} "
          f"{time.perf_counter() - start:.1f}s rewritten={before != after}")  # fmt: skip
    for line in (second.stdout + second.stderr).splitlines():
        if not line.startswith("[youtube]"):
            print("   ", line[:200])
    listing(folder)


def name_before_download(label: str, fmt: list[str], kill: bool) -> None:
    folder = fresh("before")
    start = time.perf_counter()
    process = popen([*fmt, *NAME, "-P", str(folder), "--print", "before_dl:NAME %(filename)s",
                     "--print", "after_move:FILE %(filepath)s", *PROGRESS, ZH])  # fmt: skip
    assert process.stdout
    print(f"\n## name before download, {label}, kill at NAME={kill}")
    shown = 0
    for line in process.stdout:
        if line.startswith(("NAME", "FILE")) or shown < 3:
            print(f"  {time.perf_counter() - start:5.2f} {line.strip()[:160]}")
            shown += not line.startswith("NAME")
        if kill and line.startswith("NAME"):
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, creationflags=NO_WINDOW)  # fmt: skip
            break
    print("  exit:", process.wait())
    listing(folder)


TITLES = [
    'a\\b/c:d*e?f"g<h>i|j',
    'AC/DC - Back: "Live" <1080p>?',
    "trailing dot.",
    "trailing space ",
    "...",
    "CON",
    "🎵 歌名 🎵",
    "長" * 300,
]


def odd_titles() -> None:
    print("\n## file names from odd titles (title replaced with --replace-in-metadata)")
    for title in TITLES:
        fake = ["--replace-in-metadata", "title", "^.*$", title.replace("\\", "\\\\")]
        out = run([*fake, *NAME, "--print", "filename", ZOO])
        print(f"  {title[:40]!r:45} -> {out.stdout.strip()[:60]!r} (len {len(out.stdout.strip())})")
        if out.returncode:
            print("     ", out.stderr.strip()[-200:])
    for title in (TITLES[0], TITLES[-1]):
        folder = fresh("odd")
        fake = ["--replace-in-metadata", "title", "^.*$", title.replace("\\", "\\\\")]
        out = run([*fake, *MP3, *NAME, "-P", str(folder), "--print", "after_move:FILE %(filepath)s", ZOO])
        print(f"  real MP3 download with {title[:20]!r}: exit={out.returncode}")
        print("     ", (out.stdout.strip() or out.stderr.strip())[-260:])
        listing(folder)


if __name__ == "__main__":
    json_has_filename()
    own_skip("MP3", MP3, [])
    own_skip("MP3", MP3, ["--no-overwrites"])
    own_skip("MP4", MP4, [])
    name_before_download("MP3", MP3, kill=False)
    name_before_download("MP4", MP4, kill=False)
    name_before_download("MP4", MP4, kill=True)
    odd_titles()
