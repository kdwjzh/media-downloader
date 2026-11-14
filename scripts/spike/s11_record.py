"""Records real yt-dlp output as test fixtures in backend/tests/fixtures/ytdlp/.

Uses the engine's own argument builder, so the samples are exactly what the engine reads.
Personal paths are masked; lookup JSON is cut down to the fields listed below (values untouched).

  python scripts/spike/s11_record.py [info] [selected] [errors] [downloads] [retry]
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from common import LONG, PLAYLIST, SHORT, UHD, ZH, ZOO, fresh  # noqa: E402
from s04_errors import CASES, Proxy  # noqa: E402

from app.domain.engine import DownloadRequest  # noqa: E402
from app.domain.media import QUALITIES, Format  # noqa: E402
from app.infrastructure.engines.ytdlp import args  # noqa: E402

FIXTURES = ROOT / "backend" / "tests" / "fixtures" / "ytdlp"
VIDEOS = {"wide": ZH, "vertical": SHORT, "uhd": UHD, "old43": ZOO}
TOP = ["_type", "id", "title", "channel", "uploader", "duration", "thumbnail", "extractor_key",
       "webpage_url_domain", "live_status", "is_live", "availability", "age_limit", "width",
       "height", "playlist_count"]  # fmt: skip
FORMAT = ["format_id", "width", "height", "vcodec", "acodec", "fps", "filesize", "filesize_approx",
          "protocol", "ext", "tbr", "abr", "quality", "language", "language_preference",
          "format_note"]  # fmt: skip
ENTRY = ["_type", "id", "url", "title", "duration", "channel", "uploader", "thumbnails",
         "availability", "live_status", "ie_key"]  # fmt: skip


def mask(text: str) -> str:
    for path, label in ((tempfile.gettempdir(), "<TEMP>"), (str(ROOT), "<REPO>"), (str(Path.home()), "<HOME>")):
        text = text.replace(path, label).replace(path.replace("\\", "\\\\"), label)
    return text


def call(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, capture_output=True, encoding="utf-8", errors="replace",
                          stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)  # fmt: skip


def save(name: str, text: str) -> None:
    path = FIXTURES / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mask(text), encoding="utf-8", newline="\n")
    print(f"  wrote {name} ({path.stat().st_size:,} bytes)")


def info() -> None:
    urls = {**VIDEOS, "playlist": PLAYLIST,
            "playlist_unavailable": "https://www.youtube.com/playlist?list=PLCGH0VYM-IpK8QG40jXx79q_KmReC66ZC",
            "live": "https://www.youtube.com/@LofiGirl/live"}  # fmt: skip
    for name, url in urls.items():
        data = json.loads(call(args.info(url)).stdout)
        slim = {k: data[k] for k in TOP if k in data}
        if "formats" in data:  # the format URLs are signed for this machine's address: dropped
            slim["formats"] = [{k: f[k] for k in FORMAT if k in f} for f in data["formats"]]
        if "entries" in data:
            slim["entries"] = [{k: e[k] for k in ENTRY if k in e} for e in data["entries"]]
        save(f"info/{name}.json", json.dumps(slim, ensure_ascii=False, indent=1))


def selected() -> None:
    """What yt-dlp itself picks for every MP4 quality: the truth pick_formats is tested against."""
    truth: dict[str, dict[str, str]] = {}
    for name, url in VIDEOS.items():
        truth[name] = {}
        for quality in QUALITIES[Format.MP4]:
            out = call([*args.base(), *args.format_selection(Format.MP4, quality), "--no-playlist",
                        "--print", "%(format_id)s", "--", url])  # fmt: skip
            truth[name][str(quality)] = out.stdout.strip()
            print(f"  {name} {quality}: {out.stdout.strip()}")
    save("selected.json", json.dumps(truth, indent=1))


def errors() -> None:
    names = ["not_a_url", "no_host", "unsupported_site", "watch_without_id", "not_found", "private",
             "age_restricted", "age_restricted_but_ok", "removed", "geo_blocked", "playlist_not_found"]  # fmt: skip
    for name, (_, url) in zip(names, CASES, strict=True):
        out = call([*args.base(), *args.LOOKUP_NETWORK, "-J", "--flat-playlist", "--no-playlist", "--", url])
        if out.returncode:
            save(f"errors/{name}.txt", out.stderr)
    out = call(args.info("https://www.youtube.com/watch?v=jfKfPfyJRdk"))
    save("errors/live_recording_gone.txt", out.stderr)
    start = time.perf_counter()
    out = call([*args.base(), "--proxy", "http://127.0.0.1:9", *args.info(ZH)[len(args.base()):]])
    print(f"  offline lookup failed after {time.perf_counter() - start:.1f}s")
    save("errors/offline_lookup_proxy.txt", out.stderr)
    out = call([*args.update(), "--proxy", "http://127.0.0.1:9"])
    print("  offline update exit:", out.returncode)
    save("errors/offline_update_proxy.txt", out.stderr)
    save("update_up_to_date.txt", call(args.update()).stdout)


def download(name: str, format: Format, quality: int, url: str) -> None:
    folder = fresh("record")
    # stdout and stderr together, as the engine reads them: post-processing progress is on stderr.
    out = subprocess.run(args.download(DownloadRequest("rec", url, format, quality, str(folder)), folder / "task"),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)  # fmt: skip
    print(f"  {name}: exit={out.returncode}")
    save(f"download/{name}.txt", out.stdout)


def retry(name: str, restore: bool) -> None:
    proxy = Proxy()
    folder = fresh(f"record-{name}")
    command = args.download(DownloadRequest("rec", LONG, Format.MP4, 2160, str(folder)), folder / "task")
    command[len(args.base()):len(args.base())] = ["--proxy", f"http://127.0.0.1:{proxy.port}"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace",
                               creationflags=subprocess.CREATE_NO_WINDOW)  # fmt: skip
    assert process.stdout
    lines: list[str] = []
    cut_at: float | None = None
    after = 0
    for line in process.stdout:
        lines.append(line)
        if cut_at is None and '"downloaded_bytes": 2' in line:
            cut_at = time.perf_counter()
            if restore:
                for sock in proxy.sockets:
                    sock.close()
            else:
                proxy.cut()
        elif cut_at is not None:
            after += 1
            if restore and after > 12:  # enough to show the download carrying on
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)  # fmt: skip
                break
    process.wait()
    print(f"  {name}: exit={process.returncode}, ended {time.perf_counter() - (cut_at or 0):.1f}s after the cut")
    save(f"download/{name}.txt", "".join(lines))


if __name__ == "__main__":
    wanted = sys.argv[1:] or ["info", "selected", "errors", "downloads", "retry"]
    if "info" in wanted:
        info()
    if "selected" in wanted:
        selected()
    if "errors" in wanted:
        errors()
    if "downloads" in wanted:
        download("mp3", Format.MP3, 320, ZH)
        download("mp4", Format.MP4, 1080, ZH)
        download("mp4_single_file", Format.MP4, 240, ZOO)
    if "retry" in wanted:
        retry("retry_then_resume", restore=True)
        retry("retry_then_give_up", restore=False)
