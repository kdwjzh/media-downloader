"""Items 8, 9, 13: Deno on/off, self-update, sizes.

Usage: python s05_misc.py [deno] [update] [ffprobe] [sizes]   (default: all)
"""

import getpass
import json
import lzma
import shutil
import subprocess
import sys
import time

from common import BASE, BIN, LONG, NO_WINDOW, SHORT, UHD, ZH, ZOO, fresh, run

OLDER = "2026.10.21"  # the release before the pinned one


def deno() -> None:
    print("\n## with and without Deno (-J)")
    for url in (ZOO, ZH, SHORT, UHD):
        for label, extra in (("deno", []), ("no JS runtime", ["--no-js-runtimes"])):
            start = time.perf_counter()
            result = run([*extra, "-J", "--no-playlist", url])
            took = time.perf_counter() - start
            formats = json.loads(result.stdout)["formats"] if result.stdout.strip() else []
            https = [f for f in formats if f.get("protocol") == "https"]
            top = max((f.get("height") or 0 for f in formats), default=0)
            ids = ",".join(sorted(f["format_id"] for f in formats if f.get("height") == top))
            print(f"  {url[-11:]} {label:14} exit={result.returncode} {took:4.1f}s formats={len(formats):2} "
                  f"https={len(https):2} max height={top} ({ids}) warnings={result.stderr.count('WARNING')}")  # fmt: skip
            if extra and result.stderr.strip():
                print("     " + result.stderr.strip().splitlines()[0][:300])


def call(exe, *args: str) -> None:  # type: ignore[no-untyped-def]
    start = time.perf_counter()
    result = subprocess.run([str(exe), "--ignore-config", "--color", "never", *args], capture_output=True,
                            encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)  # fmt: skip
    print(f"  $ yt-dlp {' '.join(args)}   -> exit={result.returncode}  {time.perf_counter() - start:.1f}s")
    for line in (result.stdout + result.stderr).strip().splitlines():
        print("      " + line[:300])


def listing(folder) -> None:  # type: ignore[no-untyped-def]
    print("    files: " + ", ".join(f"{p.name} ({p.stat().st_size:,})" for p in sorted(folder.iterdir())))


def update() -> None:
    folder = fresh("update")
    exe = folder / "yt-dlp.exe"
    shutil.copy2(BIN / "yt-dlp.exe", exe)

    print("\n## -U when already on the latest version")
    call(exe, "-U")
    listing(folder)

    print(f"\n## --update-to {OLDER} (downgrade, to have something to update from)")
    call(exe, "--update-to", OLDER)
    call(exe, "--version")
    listing(folder)

    locked = fresh("update-locked")
    shutil.copy2(exe, locked / "yt-dlp.exe")

    print("\n## -U while a download is running from the same yt-dlp.exe")
    download = subprocess.Popen([str(exe), "--ignore-config", "-q", "-P", str(fresh("update-dl")), *BASE[2:6], LONG],
                                stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)  # fmt: skip
    time.sleep(8)
    print(f"    download still running: {download.poll() is None}")
    call(exe, "-U")
    call(exe, "--version")
    listing(folder)
    print(f"    download still running after the update: {download.poll() is None}")
    subprocess.run(["taskkill", "/PID", str(download.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)

    print("\n## -U in a folder the user cannot write to (like C:\\Program Files)")
    user = getpass.getuser()
    acl = [str(locked), "/deny", f"{user}:(OI)(CI)(WD,AD,DC)"]
    try:
        subprocess.run(["icacls", *acl], capture_output=True, creationflags=NO_WINDOW, check=True)
        call(locked / "yt-dlp.exe", "-U")
        call(locked / "yt-dlp.exe", "--version")
    finally:
        subprocess.run(["icacls", str(locked), "/remove:d", user], capture_output=True, creationflags=NO_WINDOW)
    listing(locked)


def ffprobe() -> None:
    print("\n## is ffprobe.exe needed? (a folder with ffmpeg.exe only)")
    only = fresh("ffmpeg-only")
    shutil.copy2(BIN / "ffmpeg.exe", only / "ffmpeg.exe")
    out = fresh("ffmpeg-only-out")
    base = [*BASE[:4], "--ffmpeg-location", str(only), *BASE[6:]]
    jobs = {
        "MP3 + cover": ["-f", "ba/b", "-x", "--audio-format", "mp3", "--embed-thumbnail"],
        "MP4 merge": ["-S", "res:360,vcodec:h264,acodec:m4a", "--merge-output-format", "mp4"],
    }
    for label, args in jobs.items():
        result = run(["-v", *args, "-P", str(out), "-o", f"{label[:3]}.%(ext)s", "--no-playlist", ZOO], base=base)
        notes = [x for x in result.stderr.splitlines() if "exe versions" in x or "WARNING" in x or "ERROR" in x]
        print(f"  {label}: exit={result.returncode}")
        for note in notes:
            print("      " + note[:300])
    listing(out)


def sizes() -> None:
    print("\n## sizes")
    total = packed = 0
    for exe in sorted(BIN.glob("*.exe")):
        size = exe.stat().st_size
        compressor = lzma.LZMACompressor(preset=6)
        compressed = 0
        with exe.open("rb") as handle:
            while chunk := handle.read(1 << 22):
                compressed += len(compressor.compress(chunk))
        compressed += len(compressor.flush())
        total += size
        packed += compressed
        print(f"  {exe.name:12} {size:>12,} bytes  {size / 2**20:6.1f} MiB   lzma: {compressed / 2**20:6.1f} MiB", flush=True)
    print(f"  {'total':12} {total:>12,} bytes  {total / 2**20:6.1f} MiB   lzma: {packed / 2**20:6.1f} MiB")


if __name__ == "__main__":
    chosen = sys.argv[1:] or ["deno", "update", "ffprobe", "sizes"]
    for name in chosen:
        {"deno": deno, "update": update, "ffprobe": ffprobe, "sizes": sizes}[name]()
