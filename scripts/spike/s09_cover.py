"""Stage 3b, experiment C: crop the embedded MP3 cover to a centred square.

Needs ffprobe.exe in bin/ (development only) to inspect the result.
"""

import json
import subprocess

from common import BIN, NO_WINDOW, SHORT, ZH, ZOO, fresh, run

MP3 = ["-f", "ba/b", "-x", "--audio-format", "mp3", "--embed-thumbnail", "--no-playlist"]
# The thumbnail is converted before it is embedded; the crop rides on that conversion.
# yt-dlp splits the value like a shell: the double quotes keep the single quotes, which ffmpeg
# needs so the commas are not read as filter separators.
SQUARE = ["--convert-thumbnails", "jpg",
          "--ppa", "ThumbnailsConvertor+ffmpeg_o:-vf \"crop='min(iw,ih)':'min(iw,ih)'\""]  # fmt: skip


def tool(name: str, *args: str) -> str:
    return subprocess.run([str(BIN / name), *args], capture_output=True, encoding="utf-8",
                          errors="replace", creationflags=NO_WINDOW).stdout  # fmt: skip


def cover(label: str, url: str, extra: list[str]) -> None:
    folder = fresh("cover") / label
    result = run([*MP3, *extra, "-o", f"{label}.%(ext)s", "-P", str(folder), "-v", url])
    mp3 = folder / f"{label}.mp3"
    print(f"\n## {label} {'square' if extra else 'as is'}: exit={result.returncode}")
    for line in result.stderr.splitlines():
        if "ffmpeg command line" in line and ("crop" in line or "-map 1" in line):
            print("   ", line.replace(str(BIN), "<bin>").replace(str(folder), "<out>")[:400])
    if not mp3.exists():
        print(result.stderr[-600:])
        return
    streams = json.loads(tool("ffprobe.exe", "-v", "error", "-show_streams", "-of", "json", str(mp3)))["streams"]
    for s in streams:
        print(f"    stream: {s['codec_type']} {s['codec_name']} {s.get('width', '')}x{s.get('height', '')} "
              f"attached_pic={s['disposition']['attached_pic']}")  # fmt: skip
    print(f"    header: {mp3.read_bytes()[:5]!r}  size: {mp3.stat().st_size:,}  left in folder: "
          f"{[p.name for p in folder.iterdir()]}")  # fmt: skip
    keep = folder.parent.parent / f"cover-{label}-{'square' if extra else 'asis'}"
    tool("ffmpeg.exe", "-y", "-v", "error", "-i", str(mp3), "-an", "-c:v", "copy", f"{keep}.jpg")
    mp3.replace(f"{keep}.mp3")  # kept so a person can open it in a player
    print(f"    kept: {keep.name}.mp3 / .jpg")


if __name__ == "__main__":
    cover("wide", ZH, [])
    for label, url in (("wide", ZH), ("vertical", SHORT), ("old43", ZOO)):
        cover(label, url, SQUARE)
