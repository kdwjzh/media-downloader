"""Stage 3b, smaller checks: sizes before download, the retry line, lookup arguments,
live streams, playlists with unavailable entries, playlists over 200 entries.

  python s10_misc.py [sizes] [retry] [lookup] [playlists]     (no argument: all)
"""

import json
import subprocess
import sys
import time

from common import BASE, LONG, NO_WINDOW, PLAYLIST, PROGRESS, SHORT, ZH, ZOO, fresh, run
from s04_errors import Proxy

MP3 = ["-f", "ba/b", "-x", "--audio-format", "mp3"]
MP4 = ["-S", "res:1080,vcodec:h264,acodec:m4a", "--merge-output-format", "mp4"]
SIZES = "before_dl:SIZES %(requested_formats.:.{format_id,filesize,filesize_approx})j %(.{format_id,filesize,filesize_approx})j"


def sizes() -> None:
    for label, fmt in (("MP3", MP3), ("MP4", MP4)):
        out = run([*fmt, "--print", SIZES, "--no-playlist", "-P", str(fresh("sizes")), ZH])
        print(f"\n## sizes before download, {label}: exit={out.returncode}\n  {out.stdout.strip()}")


def retry(label: str, extra: list[str], restore: bool) -> None:
    """Cuts every open connection once (restore=True) or for good, and shows what yt-dlp prints."""
    proxy = Proxy()
    folder = fresh(f"retry-{restore}")
    errors = (folder / "stderr.txt").open("w+", encoding="utf-8")
    process = subprocess.Popen([*BASE, "--proxy", f"http://127.0.0.1:{proxy.port}", "-S", "res:2160", *extra,
                                *PROGRESS, "-P", str(folder / "out"), "--no-playlist", LONG],
                               stdout=subprocess.PIPE, stderr=errors, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace", creationflags=NO_WINDOW)  # fmt: skip
    assert process.stdout
    print(f"\n## retry line ({label})")
    cut_at, after, previous = None, 0, ""
    for line in process.stdout:
        if cut_at is None and '"downloaded_bytes": 2' in line:
            cut_at = time.perf_counter()
            print("  last line before the cut:", line.strip()[:150])
            if restore:
                for sock in proxy.sockets:
                    sock.close()
            else:
                proxy.cut()
        elif cut_at is not None:
            after += 1
            if after <= 2 or not line.startswith("DL "):
                print(f"  stdout +{time.perf_counter() - cut_at:5.1f}s: {line.strip()[:260]}")
            if restore and after > 40:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, creationflags=NO_WINDOW)  # fmt: skip
                break
        previous = line
    code = process.wait()
    print(f"  exit={code}, ended {time.perf_counter() - (cut_at or 0):.1f}s after the cut; last stdout: {previous.strip()[:120]}")
    errors.seek(0)
    for line in errors.read().splitlines():
        print("  stderr:", line[:420])
    errors.close()


LOOKUP = ["-J", "--flat-playlist", "--no-playlist"]
URLS = [
    ("video inside a playlist", f"{ZOO}&list=PL4fGSI1pDJn6puJdseH2Rt9sMvt9E2M4i"),
    ("playlist page", PLAYLIST),
    ("short link with list", "https://youtu.be/jNQXAC9IVRw?list=PL4fGSI1pDJn6puJdseH2Rt9sMvt9E2M4i"),
    ("Shorts", SHORT.replace("watch?v=", "shorts/")),
    ("music.youtube.com video", "https://music.youtube.com/watch?v=jNQXAC9IVRw"),
    ("music.youtube.com playlist", "https://music.youtube.com/playlist?list=PL4fGSI1pDJn6puJdseH2Rt9sMvt9E2M4i"),
    ("m.youtube.com", "https://m.youtube.com/watch?v=jNQXAC9IVRw"),
    ("watch without id", "https://www.youtube.com/watch?v="),
    ("channel videos tab", "https://www.youtube.com/@YouTube/videos"),
    ("live stream", "https://www.youtube.com/@LofiGirl/live"),
    ("ended live stream without a recording", "https://www.youtube.com/watch?v=jfKfPfyJRdk"),
]


def lookup() -> None:
    print(f"\n## one set of lookup arguments for every URL: {LOOKUP}")
    for label, url in URLS:
        start = time.perf_counter()
        out = run([*LOOKUP, url])
        took = time.perf_counter() - start
        try:
            data = json.loads(out.stdout)
        except ValueError:
            data = None
        if not isinstance(data, dict):  # a failure prints "null"
            print(f"  {label}: exit={out.returncode} {took:.1f}s {out.stderr.strip()[-200:]}")
            continue
        entries = data.get("entries")
        print(f"  {label}: exit={out.returncode} {took:.1f}s _type={data.get('_type')} id={data.get('id')} "
              f"extractor={data.get('extractor_key')} entries={None if entries is None else len(entries)} "
              f"live_status={data.get('live_status')} is_live={data.get('is_live')} "
              f"duration={data.get('duration')} title={str(data.get('title'))[:40]!r}")  # fmt: skip
        if out.stderr.strip():
            print("      stderr:", out.stderr.strip()[-200:])


def playlists() -> None:
    # A playlist-only search gives us candidates without hard-coding somebody's list.
    found: dict[str, str] = {}
    for query in ("old+songs+playlist+2010", "classic+rock+500+songs", "80s+hits+playlist"):
        search = f"https://www.youtube.com/results?search_query={query}&sp=EgIQAw%3D%3D"
        data = json.loads(run(["-J", "--flat-playlist", "--playlist-end", "12", search]).stdout or "{}")
        for entry in data.get("entries", []):
            if "list=" in entry.get("url", ""):
                found[entry["url"]] = entry.get("title", "")
    print(f"\n## playlists: {len(found)} candidates")
    shown_bad = shown_big = 0
    for url in found:
        start = time.perf_counter()
        out = run(["-J", "--flat-playlist", "--no-playlist", url])
        took = time.perf_counter() - start
        try:
            data = json.loads(out.stdout)
        except ValueError:
            print(f"  {url}: exit={out.returncode} {out.stderr.strip()[-160:]}")
            continue
        entries = data.get("entries", [])
        bad = [e for e in entries if e.get("duration") is None or str(e.get("title", "")).startswith("[")]
        print(f"  {url}: {took:.1f}s entries={len(entries)} playlist_count={data.get('playlist_count')} odd={len(bad)}")
        if bad and shown_bad < 3:
            shown_bad += 1
            kinds: dict[str, dict] = {}  # type: ignore[type-arg]
            for entry in bad:
                kinds.setdefault(str(entry.get("title")), entry)
            for entry in list(kinds.values())[:4]:
                entry = {k: v for k, v in entry.items() if k not in ("thumbnails", "__x_forwarded_for_ip")}
                print("      odd entry:", json.dumps(entry, ensure_ascii=False)[:600])
        if len(entries) > 200 and shown_big < 3:
            shown_big += 1
            print(f"      >200: output is {len(out.stdout) / 1e6:.1f} MB of JSON")
        if shown_bad >= 3 and shown_big >= 2:
            break


if __name__ == "__main__":
    wanted = sys.argv[1:] or ["sizes", "retry", "lookup", "playlists"]
    if "sizes" in wanted:
        sizes()
    if "retry" in wanted:
        if "nodrop" not in sys.argv:
            retry("connections dropped once, defaults", [], restore=True)
        retry("connection gone for good, --retries 3 --socket-timeout 10", ["--retries", "3", "--socket-timeout", "10"], restore=False)
    if "lookup" in wanted:
        lookup()
    if "playlists" in wanted:
        playlists()
