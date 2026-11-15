"""What the services need from each other and from the outside world (files, the network,
Windows). The infrastructure layer has the real ones; tests/fakes.py the ones for tests.

The queue reads settings while it holds its own lock, so a QueueSettings must never call
back into the queue from inside its members (or while holding a lock they need).
"""

from dataclasses import dataclass
from typing import Protocol

from app.domain.engine import OnDuplicate
from app.domain.history import HistoryEntry, HistoryRecord
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


class KeyValueFile(Protocol):
    def load(self) -> dict[str, object] | None:
        """None when there is nothing to read. A file that cannot be read is set aside and
        counts as nothing."""
        ...

    def save(self, data: dict[str, object]) -> None:
        """All of it or nothing. Raises OSError."""
        ...


class HistoryStore(Protocol):
    """Callable from any thread. A store that turns out to be unusable sets itself aside and
    starts empty."""

    def add(self, record: HistoryRecord, thumb: bytes | None) -> None: ...

    def list(self) -> list[HistoryEntry]:
        """Newest first, thumbnails as data URLs."""
        ...

    def get(self, entry_id: str) -> HistoryRecord | None: ...

    def delete(self, entry_id: str) -> None: ...

    def clear(self) -> None: ...


class ThumbnailSource(Protocol):
    def make(self, url: str) -> bytes | None:
        """A small JPEG of the image at url; None when it cannot be had. Never raises."""
        ...


class Shell(Protocol):
    """Opens things with the operating system. Every method raises OSError on failure."""

    def select_file(self, path: str) -> None: ...

    def open_path(self, path: str) -> None: ...

    def open_url(self, url: str) -> None: ...
