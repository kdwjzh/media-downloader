"""HistoryService: what was downloaded (sections 2.9 and 3.3 of the contract).

Nothing here ever deletes a downloaded file: an entry is only the record of it.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.history import HistoryEntry, HistoryRecord, data_url
from app.services.ports import FinishedDownload, HistoryStore, ThumbnailSource

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoryAdded:
    entry: HistoryEntry


class HistoryService:
    def __init__(
        self,
        store: HistoryStore,
        thumbnails: ThumbnailSource,
        emit: Callable[[HistoryAdded], None],
        requeue: Callable[[HistoryRecord], str | None],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """requeue adds a record's URL to the queue with its format and quality, without
        making them the "last used" ones, and returns the new task id."""
        self._store = store
        self._thumbnails = thumbnails
        self._emit = emit
        self._requeue = requeue
        self._now = now

    def record(self, download: FinishedDownload) -> None:
        """Called on a download's thread; several downloads can finish at the same time."""
        thumb = self._thumbnails.make(download.thumb) if download.thumb else None
        entry = HistoryEntry(
            uuid.uuid4().hex,  # its own id: the same video twice is two entries
            download.url,
            download.title,
            download.format,
            download.quality,
            download.size_bytes,
            self._now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            data_url(thumb) if thumb else None,
        )
        self._store.add(HistoryRecord(entry, download.file_path, download.thumb), thumb)
        try:
            self._emit(HistoryAdded(entry))
        except Exception:
            log.exception("the history listener failed")

    def list(self) -> list[HistoryEntry]:
        return self._store.list()

    def redownload(self, entry_id: str) -> str | None:
        """The new task id; None when there is no such entry."""
        record = self._store.get(entry_id)
        return self._requeue(record) if record else None

    def file_path(self, entry_id: str) -> str | None:
        record = self._store.get(entry_id)
        return record.file_path if record else None

    def delete(self, entry_id: str) -> None:
        self._store.delete(entry_id)

    def clear(self) -> None:
        self._store.clear()
