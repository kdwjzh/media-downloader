"""Builds yt-dlp command lines. Every argument here is backed by docs/技術驗證.md."""

from pathlib import Path

from app.domain.engine import DownloadRequest
from app.domain.media import Format
from app.infrastructure import binaries

# Prefixes of the lines we ask yt-dlp to print; parse.py reads them back.
NAME, SIZES, FILE, DL, PP = "MD-NAME ", "MD-SIZES ", "MD-FILE ", "MD-DL ", "MD-PP "

# Titles longer than a path component can hold make the download fail (item 15).
TRIM = 100

# Measured in docs/技術驗證.md item 23.
# Lookup: an unresponsive network is reported after about 12 s (two requests of 5 s each).
LOOKUP_NETWORK = ["--socket-timeout", "5", "--extractor-retries", "0"]
# Download: yt-dlp goes through the retries twice, so this is 6 attempts. A drop that heals
# within about 35 s resumes by itself; with Wi-Fi really off it fails after about 40 s, and
# in the worst simulated case (connected, but nothing ever answers) after 110 s.
DOWNLOAD_NETWORK = [
    "--socket-timeout", "10", "--retries", "3", "--fragment-retries", "3",
    "--retry-sleep", "5", "--retry-sleep", "fragment:5",
]  # fmt: skip

_SQUARE_COVER = [
    "--embed-thumbnail",
    "--convert-thumbnails",
    "jpg",
    # yt-dlp splits this value like a shell: the double quotes keep the single quotes, which
    # ffmpeg needs so the commas are not read as filter separators (item 17).
    "--ppa",
    "ThumbnailsConvertor+ffmpeg_o:-vf \"crop='min(iw,ih)':'min(iw,ih)'\"",
]


def base() -> list[str]:
    return [
        str(binaries.yt_dlp()),
        "--ignore-config",
        "--encoding",  # without it the output is the system code page (cp950)
        "utf-8",
        "--color",
        "never",
        "--ffmpeg-location",
        str(binaries.ffmpeg().parent),
        "--js-runtimes",
        f"deno:{binaries.deno()}",  # must be absolute; a relative path is silently not found
    ]


def info(url: str) -> list[str]:
    # --no-playlist: a video inside a playlist is a single video. --flat-playlist: a pure
    # playlist URL lists its entries without looking each one up.
    return [*base(), *LOOKUP_NETWORK, "-J", "--flat-playlist", "--no-playlist", "--", url]


def format_selection(format: Format, quality: int) -> list[str]:
    if format is Format.MP3:
        return ["-f", "ba/b", "-x", "--audio-format", "mp3", "--audio-quality", f"{quality}K",
                *_SQUARE_COVER]  # fmt: skip
    # res: is the short side, so vertical videos pick correctly (height<=N does not).
    return ["-S", f"res:{quality},vcodec:h264,acodec:m4a", "--merge-output-format", "mp4"]


def download(request: DownloadRequest, task_dir: Path) -> list[str]:
    return [
        *base(),
        *DOWNLOAD_NETWORK,
        *format_selection(request.format, request.quality),
        "--no-playlist",
        "-P",
        str(task_dir),  # everything happens in the task's own folder; files.place() moves it out
        "-o",
        "%(title)s.%(ext)s",
        "--windows-filenames",
        "--trim-filenames",
        str(TRIM),
        "--print",
        f"before_dl:{NAME}%(filename)s",
        "--print",
        f"before_dl:{SIZES}%(requested_formats.:.{{format_id,filesize,filesize_approx}})j"
        " %(.{format_id,filesize,filesize_approx})j",
        "--print",
        f"after_move:{FILE}%(filepath)s",
        "--no-quiet",
        "--progress",
        "--newline",
        "--progress-template",
        f"download:{DL}%(info.{{format_id}})j"
        " %(progress.{status,downloaded_bytes,total_bytes,total_bytes_estimate,speed})j",
        "--progress-template",
        f"postprocess:{PP}%(progress.{{status,postprocessor}})j",
        "--",  # so a URL starting with - can never be read as an option
        request.url,
    ]


def version() -> list[str]:
    return [str(binaries.yt_dlp()), "--ignore-config", "--version"]


def update() -> list[str]:
    return [str(binaries.yt_dlp()), "--ignore-config", "--encoding", "utf-8", "--color", "never",
            "-U"]  # fmt: skip
