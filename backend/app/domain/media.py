from dataclasses import dataclass
from enum import StrEnum


class Format(StrEnum):
    MP3 = "mp3"
    MP4 = "mp4"


# MP3: bitrate in kbps. MP4: ceiling on the short side in pixels.
# Mirrored in frontend/src/types.ts; change both together.
QUALITIES: dict[Format, tuple[int, ...]] = {
    Format.MP3: (128, 192, 320),
    Format.MP4: (144, 240, 360, 480, 720, 1080, 1440, 2160),
}


@dataclass(frozen=True)
class FormatOption:
    format: Format
    quality: int
    size_bytes: int | None = None  # an estimate; None when the source gives no size


@dataclass(frozen=True)
class MediaInfo:
    url: str
    title: str
    duration_sec: int
    platform: str
    options: tuple[FormatOption, ...]
    channel: str | None = None
    thumb: str | None = None


@dataclass(frozen=True)
class PlaylistEntry:
    url: str
    available: bool = True
    title: str | None = None
    channel: str | None = None
    duration_sec: int | None = None
    thumb: str | None = None


@dataclass(frozen=True)
class PlaylistInfo:
    url: str
    title: str
    platform: str
    entries: tuple[PlaylistEntry, ...]
    channel: str | None = None
