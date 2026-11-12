"""Items 1, 2, 5: single-video info, flat playlist, quality selection (no downloads)."""

import json
import time

from common import PLAYLIST, SHORT, UHD, ZH, ZOO, run


def info(url: str) -> None:
    start = time.perf_counter()
    result = run(["-J", "--no-playlist", url])
    took = time.perf_counter() - start
    data = json.loads(result.stdout)
    print(f"\n## {url}  exit={result.returncode}  {took:.1f}s  stderr={result.stderr.strip()[:200]!r}")
    for key in ("id", "title", "channel", "uploader", "duration", "thumbnail", "extractor_key",
                "webpage_url_domain", "live_status", "availability", "age_limit",
                "width", "height", "filesize", "filesize_approx", "format_id"):  # fmt: skip
        print(f"  {key} = {str(data.get(key))[:90]}")
    print(f"  thumbnails: {len(data['thumbnails'])}, top-level keys: {len(data)}")
    stats = {"exact": 0, "approx_only": 0, "neither": 0}
    heights: dict[int, list[str]] = {}
    for fmt in data["formats"]:
        if fmt.get("filesize"):
            stats["exact"] += 1
        elif fmt.get("filesize_approx"):
            stats["approx_only"] += 1
        else:
            stats["neither"] += 1
        if fmt.get("height"):
            size = fmt.get("filesize") or fmt.get("filesize_approx")
            heights.setdefault(fmt["height"], []).append(
                f"{fmt['format_id']}:{fmt.get('width')}x{fmt['height']}:"
                f"{(fmt.get('vcodec') or '')[:4]}:{fmt.get('protocol')}:{size}"
            )
    print(f"  formats: {len(data['formats'])}  filesize {stats}")
    for height in sorted(heights):
        print(f"  {height}: {' '.join(heights[height])}")
    audio = [f for f in data["formats"] if f.get("vcodec") == "none" and f.get("acodec") != "none"]
    print("  audio:", " ".join(f"{f['format_id']}:{f['ext']}:{f.get('abr')}:{f.get('filesize')}" for f in audio))


def playlist() -> None:
    start = time.perf_counter()
    result = run(["-J", "--flat-playlist", PLAYLIST])
    took = time.perf_counter() - start
    data = json.loads(result.stdout)
    entries = data["entries"]
    print(f"\n## playlist  exit={result.returncode}  {took:.1f}s  entries={len(entries)}")
    print("  playlist keys:", sorted(k for k in data if k != "entries"))
    print("  title:", data.get("title"), "| playlist_count:", data.get("playlist_count"))
    print("  entry keys:", sorted(entries[0]))
    print("  entry[0]:", json.dumps({k: v for k, v in entries[0].items() if k != "thumbnails"}, ensure_ascii=False)[:700])
    print("  entry[0] thumbnails:", entries[0].get("thumbnails"))
    for key in ("title", "duration", "channel", "thumbnails", "url"):
        print(f"  entries missing {key}: {sum(1 for e in entries if not e.get(key))}")


def quality() -> None:
    print("\n## quality selection (simulated)")
    template = "%(format_id)s %(width)sx%(height)s %(vcodec).4s+%(acodec).4s %(ext)s"
    for name, url in (("16:9", ZH), ("4:3", ZOO), ("vertical", SHORT), ("4K", UHD)):
        for limit in (360, 720, 1080, 2160):
            selectors = {
                "height<=": ["-f", f"bv*[height<={limit}]+ba/b[height<={limit}]"],
                "-S res:": ["-S", f"res:{limit}"],
                "-S res,h264": ["-S", f"res:{limit},vcodec:h264,acodec:m4a"],
            }
            row = []
            for label, args in selectors.items():
                result = run([*args, "--no-playlist", "--print", template, url])
                row.append(f"{label} {result.stdout.strip() or result.stderr.strip()[:80]}")
            print(f"  {name:8} N={limit:<5} | " + " | ".join(row))


if __name__ == "__main__":
    for video in (ZOO, ZH, SHORT, UHD):
        info(video)
    playlist()
    quality()
