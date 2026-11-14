from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.domain.errors import ErrorCode
from app.domain.media import Format, MediaInfo, PlaylistInfo


@dataclass(frozen=True)
class DownloadRequest:
    task_id: str
    url: str
    format: Format
    quality: int
    dest_dir: str


@dataclass(frozen=True)
class FileSizes:
    """Sizes of the files about to be downloaded, in order; None where unknown."""

    sizes: tuple[int | None, ...]


@dataclass(frozen=True)
class FileProgress:
    file_index: int  # 0-based; an MP4 is usually two files
    file_count: int
    downloaded_bytes: int  # of this file only
    total_bytes: int | None = None
    speed_bps: float | None = None


@dataclass(frozen=True)
class ConnectionLost:
    attempt: int  # 1-based


@dataclass(frozen=True)
class PostProcessing:
    """Downloading is over; converting or merging has started (no percentage exists)."""


EngineEvent = FileSizes | FileProgress | ConnectionLost | PostProcessing


@dataclass(frozen=True)
class DownloadResult:
    file_path: str
    size_bytes: int


class EngineError(Exception):
    def __init__(self, code: ErrorCode, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail  # raw text for the log file, never shown to the user


class DownloadCancelled(Exception):
    """Raised by download() when cancel() stopped it."""


class MediaEngine(Protocol):
    """What a download engine must offer. The engine never touches a DownloadTask:
    it reports events and the service layer applies them to the task's state machine."""

    def fetch_info(self, url: str) -> MediaInfo | PlaylistInfo:
        """Raises EngineError."""
        ...

    def download(
        self, request: DownloadRequest, on_event: Callable[[EngineEvent], None]
    ) -> DownloadResult:
        """Blocks until the file is in dest_dir. Raises EngineError or DownloadCancelled."""
        ...

    def cancel(self, task_id: str) -> None:
        """Stops that task's download and removes its temporary files. Unknown ids are ignored."""
        ...

    def version(self) -> str: ...

    def update(self) -> bool:
        """Updates the engine itself. True if a newer version was installed. Raises EngineError."""
        ...
