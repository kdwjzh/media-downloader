from collections.abc import Sequence
from dataclasses import replace
from enum import StrEnum

from app.domain.errors import RETRYABLE, ErrorCode, InvalidTransition
from app.domain.media import QUALITIES, Format
from app.domain.progress import Progress, ProgressTracker


class TaskStatus(StrEnum):
    FETCHING = "fetching"
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    RETRYING = "retrying"
    CONVERTING = "converting"
    MERGING = "merging"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


_S = TaskStatus

# Every legal status change. Documented in docs/介面與後端的約定.md section 6.
TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    _S.FETCHING: frozenset({_S.QUEUED, _S.FAILED, _S.CANCELLED}),
    _S.QUEUED: frozenset({_S.DOWNLOADING, _S.CANCELLED}),
    _S.DOWNLOADING: frozenset(
        {_S.RETRYING, _S.CONVERTING, _S.MERGING, _S.DONE, _S.FAILED, _S.CANCELLED}
    ),
    _S.RETRYING: frozenset({_S.DOWNLOADING, _S.FAILED, _S.CANCELLED}),
    _S.CONVERTING: frozenset({_S.DONE, _S.FAILED, _S.CANCELLED}),
    _S.MERGING: frozenset({_S.DONE, _S.FAILED, _S.CANCELLED}),
    _S.DONE: frozenset(),
    _S.FAILED: frozenset({_S.QUEUED, _S.FETCHING}),
    _S.CANCELLED: frozenset({_S.QUEUED, _S.FETCHING}),
}

FINISHED = frozenset({_S.DONE, _S.FAILED, _S.CANCELLED})


class DownloadTask:
    """One queue item. Its status changes only through the methods below."""

    def __init__(
        self,
        id: str,
        url: str,
        format: Format,
        quality: int,
        title: str | None = None,
        thumb: str | None = None,
    ) -> None:
        if quality not in QUALITIES[format]:
            raise ValueError(f"{quality} is not a {format} quality")
        self.id = id
        self.url = url
        self.format = format
        self.quality = quality
        self.title = title
        self.thumb = thumb
        self.progress: Progress | None = None
        self.attempt: int | None = None
        self.size_bytes: int | None = None
        self.skipped = False
        self.error: ErrorCode | None = None
        self._tracker = ProgressTracker()
        # Without a title nothing is known about the media yet, so look it up first.
        self._status = self._waiting_status()

    @property
    def status(self) -> TaskStatus:
        return self._status

    @property
    def is_finished(self) -> bool:
        return self._status in FINISHED

    def info_resolved(self, title: str, thumb: str | None = None) -> None:
        self._move(_S.QUEUED, only_from={_S.FETCHING})
        self.title = title
        self.thumb = thumb

    def start(self) -> None:
        self._move(_S.DOWNLOADING, only_from={_S.QUEUED})
        self._tracker = ProgressTracker()
        self.progress = Progress()

    def expect_file_sizes(self, sizes: Sequence[int | None]) -> None:
        self._require(_S.DOWNLOADING, _S.RETRYING)
        self._tracker.expect(sizes)

    def report_progress(
        self,
        file_index: int,
        file_count: int,
        downloaded_bytes: int,
        total_bytes: int | None = None,
        speed_bps: float | None = None,
    ) -> None:
        # Bytes arriving again is how a retry shows that it worked.
        if self._status is _S.RETRYING:
            self._move(_S.DOWNLOADING)
        self._require(_S.DOWNLOADING)
        self.progress = self._tracker.update(
            file_index, file_count, downloaded_bytes, total_bytes, speed_bps
        )

    def connection_lost(self, attempt: int) -> None:
        """The engine is retrying by itself. Repeated calls only raise the attempt number."""
        if self._status is not _S.RETRYING:
            self._move(_S.RETRYING)
        self.attempt = attempt
        if self.progress:
            self.progress = replace(self.progress, speed_bps=None, eta_sec=None)

    def begin_post_processing(self) -> None:
        to = _S.CONVERTING if self.format is Format.MP3 else _S.MERGING
        self._move(to)

    def complete(self, size_bytes: int) -> None:
        self._move(_S.DONE)
        self.size_bytes = size_bytes

    def skip(self) -> None:
        """The file already exists and the user chose to skip duplicates. Usually noticed as
        the download starts; after converting or merging when the file appeared meanwhile
        (the same video queued twice)."""
        self._move(_S.DONE)
        self.skipped = True

    def fail(self, error: ErrorCode) -> None:
        self._move(_S.FAILED)
        self.error = error

    def cancel(self) -> None:
        self._move(_S.CANCELLED)

    def retry(self) -> None:
        self._require(_S.FAILED)
        if self.error not in RETRYABLE:
            raise InvalidTransition(f"task {self.id}: error {self.error} cannot be retried")
        self._move(self._waiting_status())
        self.error = None

    def readd(self) -> None:
        self._require(_S.CANCELLED)
        self._move(self._waiting_status())

    def _waiting_status(self) -> TaskStatus:
        return _S.FETCHING if self.title is None else _S.QUEUED

    def _require(self, *statuses: TaskStatus) -> None:
        if self._status not in statuses:
            raise InvalidTransition(f"task {self.id}: not allowed while {self._status}")

    def _move(self, to: TaskStatus, only_from: set[TaskStatus] | None = None) -> None:
        allowed = to in TRANSITIONS[self._status]
        if only_from is not None:
            allowed = allowed and self._status in only_from
        if not allowed:
            raise InvalidTransition(f"task {self.id}: {self._status} -> {to} is not allowed")
        self._status = to
        # Progress numbers only mean something while bytes are (or were just) moving.
        if to not in (_S.DOWNLOADING, _S.RETRYING):
            self.progress = None
        if to is not _S.RETRYING:
            self.attempt = None
