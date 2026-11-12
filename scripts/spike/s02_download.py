"""Items 3, 4, 10, 12: MP3/MP4 progress, Chinese titles and paths, three downloads at once."""

import subprocess
import threading
import time

from common import BASE, NO_WINDOW, PROGRESS, UHD, ZH, ZOO, fresh, popen

MP3 = ["-f", "ba/b", "-x", "--audio-format", "mp3", "--embed-thumbnail"]
MP4 = ["--merge-output-format", "mp4"]
NAME = ["-o", "%(title)s [%(id)s].%(ext)s", "--windows-filenames", "--no-playlist",
        "--print", "after_move:FILE %(filepath)s"]  # fmt: skip


def stream(args: list[str]) -> tuple[int, list[str]]:
    """Run one download, return (exit code, output lines with elapsed seconds)."""
    start = time.perf_counter()
    process = popen(args)
    assert process.stdout
    lines = [f"{time.perf_counter() - start:6.2f} {line.rstrip()}" for line in process.stdout]
    return process.wait(), lines


def show(title: str, code: int, lines: list[str]) -> None:
    """Print the output, collapsing runs of "downloading" lines to first, last and count."""
    print(f"\n## {title}  exit={code}  lines={len(lines)}")
    run: list[str] = []

    def flush() -> None:
        if run:
            print(run[0])
            if len(run) > 1:
                print(f"       ... {len(run) - 2} more ...\n{run[-1]}")
            run.clear()

    for line in lines:
        if '"status": "downloading"' in line:
            if run and line.split("{")[1] != run[0].split("{")[1]:
                flush()
            run.append(line)
        else:
            flush()
            print(line)
    flush()


def files(folder) -> None:  # type: ignore[no-untyped-def]
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            print(f"  {path.stat().st_size:>12,}  {path.relative_to(folder)}")


def raw_keys() -> None:
    folder = fresh("raw")
    code, lines = stream(["-f", "ba", "--no-playlist", "-P", str(folder), "--newline", "--progress-template",
                          "download:RAW %(progress)j", "--progress-template",
                          "postprocess:RAWPP %(progress)j", "-x", "--audio-format", "mp3", ZOO])  # fmt: skip
    print("\n## raw progress dicts (first download line, last download line, postprocess lines)")
    raws = [line for line in lines if " RAW " in line]
    for line in [*raws[:1], *raws[-1:], *[x for x in lines if "RAWPP" in x]]:
        print(line[:1500])


def encoding() -> None:
    print("\n## stdout bytes for a Chinese title, with and without --encoding utf-8")
    for label, base in (("with", BASE), ("without", [a for a in BASE if a not in ("--encoding", "utf-8")])):
        result = subprocess.run([*base, "--no-playlist", "--print", "title", ZH],
                                capture_output=True, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)  # fmt: skip
        raw = result.stdout.strip()
        print(f"  {label:8} bytes={raw[:24]!r}...  as utf-8: {raw.decode('utf-8', 'replace')}")
        print(f"  {'':8} as cp950: {raw.decode('cp950', 'replace')}")


def concurrent() -> None:
    folder = fresh("concurrent")
    results: dict[str, tuple[int, list[str]]] = {}

    def work(url: str) -> None:
        results[url] = stream([*MP3, *NAME, *PROGRESS, "-P", str(folder), url])

    threads = [threading.Thread(target=work, args=(url,)) for url in (ZOO, ZH, UHD)]
    start = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(f"\n## three downloads at once: {time.perf_counter() - start:.1f}s")
    for url, (code, lines) in results.items():
        video_id = url.rsplit("=", 1)[1]
        progress = [line for line in lines if " DL " in line or " PP " in line]
        foreign = [line for line in progress if video_id not in line]
        print(f"  {video_id}: exit={code} progress lines={len(progress)} lines about another video={len(foreign)}")
    files(folder)


if __name__ == "__main__":
    raw_keys()
    encoding()

    folder = fresh("mp3") / "中文 資料夾"
    show("MP3 (Chinese title and folder)", *stream([*MP3, *NAME, *PROGRESS, "-P", str(folder), ZH]))
    files(folder)

    folder = fresh("mp4")
    show("MP4 1080p h264+m4a", *stream(
        ["-S", "res:1080,vcodec:h264,acodec:m4a", *MP4, *NAME, *PROGRESS, "-P", str(folder), ZH]))  # fmt: skip
    show("MP4 2160p (no h264 at this size)", *stream(
        ["-S", "res:2160,vcodec:h264,acodec:m4a", *MP4, *NAME, *PROGRESS, "-P", str(folder), UHD]))  # fmt: skip
    files(folder)

    concurrent()
