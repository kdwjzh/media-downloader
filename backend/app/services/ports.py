"""What the queue needs from settings and history.

Stage 3d's SettingsService and HistoryService will satisfy these two protocols. Until then
the in-memory classes below stand in for them (tests and scripts/manual/download_queue.py).

The queue reads settings while it holds its own lock, so an implementation must never call
back into the queue from inside these members (or while holding a lock they need).
"""

from dataclasses import dataclass, field
from typing import Protocol

from app.domain.engine import OnDuplicate
from app.domain.media import Format


@dataclass(frozen=True)
class FinishedDownload:
    """A download that really produced a file (skipped ones are not reported)."""

    url: str
    title: str
    format: Format
    quality: int
    size_bytes: int
    file_path: str
    thumb: str | None = None


class QueueSettings(Protocol):
    @property
    def download_dir(self) -> str: ...

    @property
    def max_concurrent(self) -> int: ...

    @property
    def on_duplicate(self) -> OnDuplicate: ...

    def remember_format(self, format: Format, quality: int) -> None:
        """Called by add(): this is now the "last used" format and quality."""
        ...

    def dirs_to_clean(self) -> list[str]:
        """Folders that may hold temporary folders of an earlier run: the download folder and
        every folder it was changed away from since the last call."""
        ...


class HistoryRecorder(Protocol):
    def record(self, download: FinishedDownload) -> None:
        """Called on the download's thread after its slot was freed; may be slow."""
        ...


@dataclass
class InMemorySettings:
    download_dir: str
    max_concurrent: int = 3
    on_duplicate: OnDuplicate = OnDuplicate.RENAME
    last_format: tuple[Format, int] | None = None

    def remember_format(self, format: Format, quality: int) -> None:
        self.last_format = (format, quality)

    def dirs_to_clean(self) -> list[str]:
        return [self.download_dir]


@dataclass
class InMemoryHistory:
    records: list[FinishedDownload] = field(default_factory=list)

    def record(self, download: FinishedDownload) -> None:
        self.records.append(download)
