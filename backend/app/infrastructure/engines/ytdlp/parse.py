"""Reads what yt-dlp prints: the lines of a download, and the JSON of a lookup."""

import json
from typing import Any

from app.domain.engine import (
    ConnectionLost,
    EngineError,
    EngineEvent,
    FileProgress,
    FileSizes,
    PostProcessing,
)
from app.domain.errors import ErrorCode
from app.domain.media import (
    QUALITIES,
    Format,
    FormatOption,
    MediaInfo,
    PlaylistEntry,
    PlaylistInfo,
)
from app.infrastructure.engines.ytdlp import args
from app.infrastructure.engines.ytdlp.errors import classify
from app.infrastructure.engines.ytdlp.urls import PLATFORM

Json = dict[str, Any]


def _size(fmt: Json) -> int | None:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    return int(size) if size else None


class DownloadOutput:
    """Feed it the output lines of one download (stdout and stderr together), in order."""

    def __init__(self) -> None:
        self.name: str | None = None  # printed before any data moves
        self.file: str | None = None  # the finished file, printed at the very end
        self._format_ids: list[str] = []
        self._attempt = 0
        self.downloaded = False  # a progress line was seen: bytes of the file have moved
        self._post_processing = False
        self.other_text = ""  # everything that is not ours: warnings and the final error

    def feed(self, line: str) -> EngineEvent | None:
        line = line.rstrip("\r\n")
        if line.startswith(args.DL):
            return self._progress(line[len(args.DL) :])
        if line.startswith(args.PP):
            status = json.loads(line[len(args.PP) :])
            # The cover is converted before the download starts, so only what follows the
            # download counts. MoveFiles is not a stage the user waits for.
            if (
                self.downloaded
                and not self._post_processing
                and status.get("status") == "started"
                and status.get("postprocessor") != "MoveFiles"
            ):
                self._post_processing = True
                return PostProcessing()
        elif line.startswith(args.NAME):
            self.name = line[len(args.NAME) :]
        elif line.startswith(args.FILE):
            self.file = line[len(args.FILE) :]
        elif line.startswith(args.SIZES):
            return self._sizes(line[len(args.SIZES) :])
        elif line.startswith("[download] Got error:") and "Retrying (" in line:
            # yt-dlp's own (N/M) starts over after a full round, so the count is kept here.
            self._attempt += 1
            return ConnectionLost(self._attempt)
        else:
            self.other_text += line + "\n"
        return None

    def _sizes(self, text: str) -> FileSizes:
        # Two JSON values: the list of files of a merged download, then the single file.
        decoder = json.JSONDecoder()
        several, end = decoder.raw_decode(text)
        single, _ = decoder.raw_decode(text[end:].lstrip())
        files: list[Json] = several or [single]
        self._format_ids = [str(f.get("format_id")) for f in files]
        return FileSizes(tuple(_size(f) for f in files))

    def _progress(self, text: str) -> FileProgress | None:
        decoder = json.JSONDecoder()
        info, end = decoder.raw_decode(text)
        progress, _ = decoder.raw_decode(text[end:].lstrip())
        if progress.get("status") not in ("downloading", "finished"):
            return None
        self._attempt = 0  # bytes are moving again
        self.downloaded = True
        format_id = str(info.get("format_id"))
        if format_id not in self._format_ids:
            self._format_ids.append(format_id)
        total = progress.get("total_bytes") or progress.get("total_bytes_estimate")
        return FileProgress(
            file_index=self._format_ids.index(format_id),
            file_count=len(self._format_ids),
            downloaded_bytes=int(progress.get("downloaded_bytes") or 0),
            total_bytes=int(total) if total else None,
            speed_bps=progress.get("speed") or None,
        )


def _short_side(fmt: Json) -> int | None:
    sides = [s for s in (fmt.get("width"), fmt.get("height")) if s]
    return min(sides) if sides else None


def _has(fmt: Json, codec: str) -> bool:
    return (fmt.get(codec) or "none") != "none"


def pick_formats(formats: list[Json], quality: int) -> tuple[Json, Json | None] | None:
    """The video and audio formats yt-dlp downloads for an MP4 of this quality.

    Imitates `-S res:N,vcodec:h264,acodec:m4a` closely enough to add up their sizes;
    tests compare it with what yt-dlp really chose (fixtures/ytdlp/selected.json).
    """
    fitting = [f for f in formats if _has(f, "vcodec") and 0 < (_short_side(f) or 0) <= quality]
    if not fitting:
        return None

    def video_rank(f: Json) -> tuple[Any, ...]:
        return (
            _short_side(f),
            str(f.get("vcodec")).startswith("avc1"),
            f.get("fps") or 0,
            f.get("protocol") == "https",
            f.get("tbr") or 0,
        )

    video = max(fitting, key=video_rank)
    if _has(video, "acodec"):
        return video, None
    audios = [f for f in formats if _has(f, "acodec") and not _has(f, "vcodec")]
    if not audios:
        return video, None

    def audio_rank(f: Json) -> tuple[Any, ...]:
        return (
            f.get("language_preference") or -1,
            f.get("quality") or -1,
            str(f.get("acodec")).startswith("mp4a"),
            f.get("protocol") == "https",
            f.get("abr") or 0,
        )

    return video, max(audios, key=audio_rank)


def options(data: Json) -> tuple[FormatOption, ...]:
    duration = data.get("duration") or 0
    # MP3 is re-encoded at a constant bitrate, so its size follows from the length alone.
    result = [
        FormatOption(Format.MP3, kbps, int(kbps * 1000 / 8 * duration) if duration else None)
        for kbps in QUALITIES[Format.MP3]
    ]
    formats: list[Json] = data.get("formats") or []
    below = 0
    for quality in QUALITIES[Format.MP4]:
        # A quality is offered when the video has something between the previous step and it.
        if any(below < (_short_side(f) or 0) <= quality for f in formats if _has(f, "vcodec")):
            picked = pick_formats(formats, quality)
            sizes = [_size(f) for f in picked or () if f]
            total = sum(s for s in sizes if s) if sizes and all(sizes) else None
            result.append(FormatOption(Format.MP4, quality, total))
        below = quality
    return tuple(result)


def _entry(entry: Json) -> PlaylistEntry:
    title = entry.get("title")
    if not title:
        # Private (and presumably deleted) videos are listed with nothing but an id.
        return PlaylistEntry(url=entry["url"], available=False)
    thumbs = entry.get("thumbnails") or []
    duration = entry.get("duration")
    return PlaylistEntry(
        url=entry["url"],
        title=title,
        channel=entry.get("channel") or entry.get("uploader"),
        duration_sec=int(duration) if duration else None,
        thumb=thumbs[-1].get("url") if thumbs else None,  # listed smallest first
    )


def info(url: str, stdout: str) -> MediaInfo | PlaylistInfo:
    """Turns the JSON of a lookup into a MediaInfo or PlaylistInfo. Raises EngineError."""
    try:
        data = json.loads(stdout)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise EngineError(ErrorCode.UNKNOWN, f"unexpected lookup output: {stdout[:200]!r}")
    channel = data.get("channel") or data.get("uploader")
    if data.get("_type") == "playlist":
        return PlaylistInfo(
            url=url,
            title=data.get("title") or "",
            platform=PLATFORM,
            entries=tuple(_entry(e) for e in data.get("entries") or [] if e and e.get("url")),
            channel=channel,
        )
    if data.get("is_live") or data.get("live_status") in ("is_live", "is_upcoming"):
        raise EngineError(ErrorCode.LIVE_NOT_SUPPORTED, str(data.get("live_status")))
    return MediaInfo(
        url=url,
        title=data.get("title") or "",
        duration_sec=int(data.get("duration") or 0),
        platform=PLATFORM,
        options=options(data),
        channel=channel,
        thumb=data.get("thumbnail"),
    )


def update_result(code: int, stdout: str, stderr: str) -> bool:
    """True when yt-dlp replaced itself, False when it was already the newest."""
    if code != 0:
        raise classify(stderr or stdout)
    return "Updated yt-dlp to" in stdout
