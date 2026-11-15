import base64
from dataclasses import dataclass

from app.domain.media import Format


@dataclass(frozen=True)
class HistoryEntry:
    """Section 2.9 of the contract. No file path: the UI opens the folder by id."""

    id: str
    url: str
    title: str
    format: Format
    quality: int
    size_bytes: int
    finished_at: str  # ISO 8601, UTC: "2026-11-13T06:20:00Z"
    thumb: str | None = None  # the small local thumbnail, as a data URL


@dataclass(frozen=True)
class HistoryRecord:
    """An entry with what the back end keeps to itself."""

    entry: HistoryEntry
    file_path: str
    thumb_url: str | None = None  # where the thumbnail came from, for "download again"


def data_url(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode("ascii")
