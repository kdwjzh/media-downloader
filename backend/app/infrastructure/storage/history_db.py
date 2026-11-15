"""The history, in one SQLite file. Thumbnails are stored in it, so deleting an entry
deletes its thumbnail and nothing is left behind."""

import logging
import sqlite3
import threading
from collections.abc import Callable, Sequence
from contextlib import closing
from pathlib import Path
from typing import Any

from app.domain.history import HistoryEntry, HistoryRecord, data_url
from app.domain.media import Format
from app.infrastructure.storage.json_file import set_aside

log = logging.getLogger(__name__)

_CREATE = """
CREATE TABLE IF NOT EXISTS history (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    format TEXT NOT NULL,
    quality INTEGER NOT NULL,
    size_bytes INTEGER NOT NULL,
    finished_at TEXT NOT NULL,
    file_path TEXT NOT NULL,
    thumb_url TEXT,
    thumb BLOB
)"""
_BROKEN = (sqlite3.SQLITE_CORRUPT, sqlite3.SQLITE_NOTADB)


class HistoryDb:
    """Every method may be called from any thread."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def add(self, record: HistoryRecord, thumb: bytes | None) -> None:
        entry = record.entry
        self._run(
            lambda db: db.execute(
                "INSERT INTO history (id, url, title, format, quality, size_bytes, finished_at,"
                " file_path, thumb_url, thumb) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.id,
                    entry.url,
                    entry.title,
                    entry.format.value,
                    entry.quality,
                    entry.size_bytes,
                    entry.finished_at,
                    record.file_path,
                    record.thumb_url,
                    thumb,
                ),
            )
        )

    def list(self) -> list[HistoryEntry]:
        """Newest first."""
        rows = self._run(
            lambda db: db.execute(
                "SELECT id, url, title, format, quality, size_bytes, finished_at, thumb"
                " FROM history ORDER BY seq DESC"
            ).fetchall()
        )
        entries = []
        for *fields, thumb in rows:
            entry = _entry(fields, data_url(thumb) if thumb else None)
            if entry:
                entries.append(entry)
        return entries

    def get(self, entry_id: str) -> HistoryRecord | None:
        """The entry without its thumbnail image."""
        row = self._run(
            lambda db: db.execute(
                "SELECT id, url, title, format, quality, size_bytes, finished_at, file_path,"
                " thumb_url FROM history WHERE id = ?",
                (entry_id,),
            ).fetchone()
        )
        entry = _entry(row[:7], None) if row else None
        return HistoryRecord(entry, row[7], row[8]) if entry else None

    def delete(self, entry_id: str) -> None:
        self._run(lambda db: db.execute("DELETE FROM history WHERE id = ?", (entry_id,)))

    def clear(self) -> None:
        self._run(lambda db: db.execute("DELETE FROM history"))

    def _run[T](self, action: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            try:
                return self._once(action)
            except sqlite3.DatabaseError as error:
                # Only a file that is not a usable database is replaced. Anything else (a
                # full disk, a locked file) may pass, and must not cost the user the history.
                if error.sqlite_errorcode not in _BROKEN:
                    raise
                log.error("the history database is unusable and was set aside: %s", error)
                set_aside(self._path)
                return self._once(action)

    def _once[T](self, action: Callable[[sqlite3.Connection], T]) -> T:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # A connection per call: sqlite3 connections do not like changing threads.
        with closing(sqlite3.connect(self._path)) as db, db:
            db.execute(_CREATE)
            return action(db)


def _entry(fields: Sequence[Any], thumb: str | None) -> HistoryEntry | None:
    """fields: id, url, title, format, quality, size_bytes, finished_at."""
    entry_id, url, title, format, quality, size_bytes, finished_at = fields
    try:
        return HistoryEntry(entry_id, url, title, Format(format), quality, size_bytes,
                            finished_at, thumb)  # fmt: skip
    except ValueError:
        log.warning("skipped history entry %s: unknown format %r", entry_id, format)
        return None
