"""QueueService: the download queue.

Threads:
- every running download has its own thread, started when a slot is free;
- MAX_LOOKUPS threads look up the tasks that were added with nothing but a URL;
- one thread hands the events to the listener, in the order they were produced.
A task is only touched while holding self._lock, whoever the caller is. Events are put in
the outbox under that same lock, so their order is the order of the changes.
"""

import logging
import queue
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.domain.engine import (
    ConnectionLost,
    DownloadCancelled,
    DownloadRequest,
    DownloadResult,
    EngineError,
    EngineEvent,
    FileProgress,
    FileSizes,
    MediaEngine,
    PostProcessing,
)
from app.domain.errors import ErrorCode, InvalidTransition
from app.domain.media import Format, MediaInfo, PlaylistInfo
from app.domain.progress import Progress
from app.domain.task import DownloadTask, TaskStatus
from app.services.media_info import MediaInfoService, normalize
from app.services.ports import FinishedDownload, HistoryRecorder, QueueSettings

log = logging.getLogger(__name__)

# A lookup is a yt-dlp and a Deno process for 3-4 s. With 3 downloads running, 2 keeps it to
# five process trees; ten pasted URLs still all have their titles after about 20 s.
MAX_LOOKUPS = 2
PROGRESS_INTERVAL = 0.5  # seconds between two progress events of one task
SHUTDOWN_WAIT = 5.0  # seconds given to the downloads to delete their temporary folders


@dataclass(frozen=True)
class QueueItem:
    """A task as it was at one moment (section 2.7 of the contract). No file path."""

    id: str
    url: str
    format: Format
    quality: int
    status: TaskStatus
    title: str | None = None
    thumb: str | None = None
    progress: Progress | None = None  # only while downloading or retrying
    attempt: int | None = None
    size_bytes: int | None = None
    skipped: bool = False
    error: ErrorCode | None = None


@dataclass(frozen=True)
class TasksChanged:
    tasks: tuple[QueueItem, ...]


@dataclass(frozen=True)
class TasksRemoved:
    ids: tuple[str, ...]


@dataclass(frozen=True)
class TaskProgress:
    id: str
    progress: Progress


QueueEvent = TasksChanged | TasksRemoved | TaskProgress


@dataclass
class _Entry:
    task: DownloadTask
    dest_dir: str  # decided when the task was added; a later change of folder does not move it
    # Changes whenever a lookup or download of this task starts or is given up on. Whatever
    # arrives from an earlier run is ignored.
    run: int = 0
    file_path: str | None = None
    sent: Progress | None = None
    sent_at: float | None = None


class QueueService:
    def __init__(
        self,
        engine: MediaEngine,
        media_info: MediaInfoService,
        settings: QueueSettings,
        history: HistoryRecorder,
        emit: Callable[[QueueEvent], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._engine = engine
        self._media_info = media_info
        self._settings = settings
        self._history = history
        self._emit = emit
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, _Entry] = {}  # in queue order
        # Tasks whose download thread is alive. A cancelled task stays here until the engine
        # has cleaned up, and holds its slot until then.
        self._workers: dict[str, threading.Thread] = {}
        self._closing = False
        self._outbox: queue.SimpleQueue[QueueEvent | None] = queue.SimpleQueue()
        self._lookup_jobs: queue.SimpleQueue[tuple[str, int, str] | None] = queue.SimpleQueue()
        # Daemon threads: a lookup that is still running must not keep the app from exiting.
        self._sender = threading.Thread(target=self._send_events, daemon=True)
        self._sender.start()
        for _ in range(MAX_LOOKUPS):
            threading.Thread(target=self._run_lookups, daemon=True).start()

    # ---- commands (section 3.2 of the contract)

    def start(self) -> None:
        """Call once when the app starts, before anything is added."""
        for folder in self._settings.dirs_to_clean():
            try:
                self._engine.remove_stale_temp(folder)
            except Exception:
                log.exception("could not clean temporary folders")

    def add(
        self, urls: Sequence[str], format: Format, quality: int, remember: bool = True
    ) -> list[str]:
        """Returns the new task ids. Raises EngineError(INVALID_URL) when any URL is not
        http(s), ValueError for a quality the format does not have; nothing is added then.
        remember=False is for "download again" from the history."""
        urls = [normalize(url) for url in urls]
        if not urls:
            raise ValueError("no URLs")
        for url in urls:
            _require_http(url)
        tasks = []
        for url in urls:
            title, thumb = self._media_info.known(url) or (None, None)
            # The id becomes a folder name: letters and digits only.
            tasks.append(DownloadTask(uuid.uuid4().hex, url, format, quality, title, thumb))
        with self._lock:
            if self._closing:
                return []
            dest_dir = self._settings.download_dir
            entries = [_Entry(task, dest_dir) for task in tasks]
            for entry in entries:
                self._entries[entry.task.id] = entry
                if entry.task.status is TaskStatus.FETCHING:
                    self._start_lookup(entry)
            self._changed(*entries)
            self._fill_slots()
        for task in tasks:
            log.info("task %s added: %s %s %s", task.id, format, quality, task.url)
        if remember:
            self._settings.remember_format(format, quality)
        return [task.id for task in tasks]

    def items(self) -> list[QueueItem]:
        with self._lock:
            return [_snapshot(entry.task) for entry in self._entries.values()]

    def cancel(self, task_id: str) -> None:
        with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or entry.task.is_finished:
                return
            entry.task.cancel()
            entry.run += 1  # whatever its lookup or download still reports is ignored
            self._changed(entry)
            if task_id in self._workers:
                # Inside the lock, so it cannot hit a download that a re-add started meanwhile.
                # The engine ignores it while its process does not exist yet;
                # _on_engine_event repeats it as soon as that process says anything.
                self._engine.cancel(task_id)

    def retry(self, task_id: str) -> None:
        self._again(task_id, DownloadTask.retry)

    def readd(self, task_id: str) -> None:
        self._again(task_id, DownloadTask.readd)

    def remove(self, task_id: str) -> None:
        with self._lock:
            entry = self._entries.get(task_id)
            if entry is not None and entry.task.is_finished:
                self._remove([task_id])

    def clear_finished(self) -> None:
        with self._lock:
            self._remove([i for i, entry in self._entries.items() if entry.task.is_finished])

    def file_path(self, task_id: str) -> str | None:
        """Where a done task's file is (for a skipped one: the file that was already there)."""
        with self._lock:
            entry = self._entries.get(task_id)
            return entry.file_path if entry else None

    def settings_changed(self) -> None:
        """Call after the number of simultaneous downloads was changed. Raising it starts
        waiting tasks now; lowering it stops nothing."""
        with self._lock:
            self._fill_slots()

    def shutdown(self) -> None:
        """For closing the app: stops everything. The queue is not kept."""
        with self._lock:
            if self._closing:
                return
            self._closing = True  # nothing starts, and nothing that arrives is applied
            workers = list(self._workers.values())
        for _ in range(MAX_LOOKUPS):
            self._lookup_jobs.put(None)
        self._engine.stop_all()
        # The engine deletes a task's temporary folder as its download() returns. Whatever is
        # not gone in time is removed by start() on the next launch.
        deadline = time.monotonic() + SHUTDOWN_WAIT
        for worker in workers:
            worker.join(max(0.0, deadline - time.monotonic()))
        self._outbox.put(None)
        self._sender.join(1)

    # ---- everything below "(lock held)" is only called while holding self._lock

    def _again(self, task_id: str, action: Callable[[DownloadTask], None]) -> None:
        with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or self._closing:
                return
            try:
                action(entry.task)  # same id, same place in the queue
            except InvalidTransition:
                return  # not failed / not cancelled / an error that cannot be retried
            entry.file_path = None
            if entry.task.status is TaskStatus.FETCHING:
                self._start_lookup(entry)
            self._changed(entry)
            self._fill_slots()

    def _fill_slots(self) -> None:
        """(lock held) Starts waiting tasks, first in the queue first."""
        if self._closing:
            return
        for entry in self._entries.values():
            if len(self._workers) >= self._settings.max_concurrent:
                return
            task = entry.task
            # A cancelled and re-added task waits for its old download to finish cleaning up:
            # the engine keeps one temporary folder per task id.
            if task.status is not TaskStatus.QUEUED or task.id in self._workers:
                continue
            task.start()
            entry.run += 1
            entry.sent_at = None
            request = DownloadRequest(
                task.id,
                task.url,
                task.format,
                task.quality,
                entry.dest_dir,
                self._settings.on_duplicate,  # read now, so a changed rule applies to waiting tasks
            )
            worker = threading.Thread(
                target=self._download, args=(request, entry.run), daemon=True
            )
            self._workers[task.id] = worker
            self._changed(entry)
            log.info("task %s started", task.id)
            worker.start()

    def _start_lookup(self, entry: _Entry) -> None:
        """(lock held)"""
        entry.run += 1
        self._lookup_jobs.put((entry.task.id, entry.run, entry.task.url))

    def _current(self, task_id: str, run: int) -> _Entry | None:
        """(lock held) The entry, unless this run was cancelled, removed or the app is closing."""
        entry = self._entries.get(task_id)
        return entry if entry and entry.run == run and not self._closing else None

    def _changed(self, *entries: _Entry) -> None:
        """(lock held)"""
        for entry in entries:
            entry.sent = entry.task.progress
        self._outbox.put(TasksChanged(tuple(_snapshot(entry.task) for entry in entries)))

    def _remove(self, task_ids: list[str]) -> None:
        """(lock held)"""
        for task_id in task_ids:
            del self._entries[task_id]
        if task_ids:
            self._outbox.put(TasksRemoved(tuple(task_ids)))

    # ---- lookup threads

    def _run_lookups(self) -> None:
        while (job := self._lookup_jobs.get()) is not None:
            try:
                self._lookup(*job)
            except Exception:
                log.exception("lookup thread failed")

    def _lookup(self, task_id: str, run: int, url: str) -> None:
        with self._lock:
            if self._current(task_id, run) is None:
                return  # cancelled while it waited for its turn
        info: MediaInfo | PlaylistInfo | None = None
        code = ErrorCode.UNKNOWN
        try:
            info = self._media_info.lookup(url)
        except EngineError as error:
            code = error.code
            log.warning("lookup for task %s failed: %s: %s", task_id, error.code, error.detail)
        except Exception:
            log.exception("lookup for task %s failed unexpectedly", task_id)
        with self._lock:
            entry = self._current(task_id, run)
            if entry is None:
                return
            if isinstance(info, MediaInfo):
                entry.task.info_resolved(info.title, info.thumb)
            elif isinstance(info, PlaylistInfo):
                entry.task.fail(ErrorCode.PLAYLIST_URL)  # never expanded behind the user's back
            else:
                entry.task.fail(code)
            self._changed(entry)
            self._fill_slots()

    # ---- download threads

    def _download(self, request: DownloadRequest, run: int) -> None:
        task_id = request.task_id
        outcome: DownloadResult | Exception
        try:
            outcome = self._engine.download(
                request, lambda event: self._on_engine_event(task_id, run, event)
            )
        except Exception as error:
            outcome = error
        finished: FinishedDownload | None = None
        with self._lock:
            del self._workers[task_id]
            try:
                entry = self._current(task_id, run)
                if entry is not None:
                    finished = self._finish(entry, outcome)
                    self._changed(entry)
                self._fill_slots()
            except Exception:
                log.exception("could not finish task %s", task_id)
        if finished:
            try:
                self._history.record(finished)
            except Exception:
                log.exception("could not record task %s in the history", task_id)

    def _finish(
        self, entry: _Entry, outcome: DownloadResult | Exception
    ) -> FinishedDownload | None:
        """(lock held) Whatever the engine did, the task ends up finished."""
        task = entry.task
        try:
            if isinstance(outcome, DownloadResult):
                if outcome.skipped:
                    task.skip()
                    entry.file_path = outcome.file_path
                    return None
                task.complete(outcome.size_bytes)
                entry.file_path = outcome.file_path
                log.info("task %s done: %s bytes", task.id, outcome.size_bytes)
                return FinishedDownload(
                    task.url,
                    task.title or "",
                    task.format,
                    task.quality,
                    outcome.size_bytes,
                    outcome.file_path,
                    task.thumb,
                )
            if isinstance(outcome, DownloadCancelled):
                task.cancel()  # stopped by something other than cancel()
            elif isinstance(outcome, EngineError):
                # detail can hold a personal path: the log file must mask it (stage 3d).
                log.warning("task %s failed: %s: %s", task.id, outcome.code, outcome.detail)
                task.fail(outcome.code)
            else:
                log.error("task %s failed unexpectedly", task.id, exc_info=outcome)
                task.fail(ErrorCode.UNKNOWN)
        except InvalidTransition:
            log.exception("task %s could not take the engine's outcome", task.id)
            # Not expected: every status a running task can have takes done, failed and cancelled.
            task.fail(ErrorCode.UNKNOWN)
        return None

    def _on_engine_event(self, task_id: str, run: int, event: EngineEvent) -> None:
        """Runs on the download's thread, for every line yt-dlp prints. An exception here would
        abort the download, and anything slow would stall it: change the task, queue an event,
        nothing else."""
        try:
            with self._lock:
                entry = self._current(task_id, run)
                if entry is not None:
                    self._apply(entry, event)
            if entry is None:
                # This download was cancelled, perhaps before the engine had a process to stop.
                self._engine.cancel(task_id)
        except InvalidTransition as error:
            log.debug("ignored an engine event: %s", error)
        except Exception:
            log.exception("could not handle an engine event for task %s", task_id)

    def _apply(self, entry: _Entry, event: EngineEvent) -> None:
        """(lock held)"""
        task = entry.task
        before = (task.status, task.attempt)
        match event:
            case FileSizes():
                task.expect_file_sizes(event.sizes)
            case FileProgress():
                task.report_progress(
                    event.file_index,
                    event.file_count,
                    event.downloaded_bytes,
                    event.total_bytes,
                    event.speed_bps,
                )
            case ConnectionLost():
                task.connection_lost(event.attempt)
            case PostProcessing():
                task.begin_post_processing()
        if (task.status, task.attempt) != before:
            self._changed(entry)  # never throttled
            return
        # Progress that is too soon is dropped, not kept for later, so there is never an old
        # percentage waiting to be sent after the status has changed.
        progress, now = task.progress, self._clock()
        if progress is None or progress == entry.sent:
            return
        if entry.sent_at is not None and now - entry.sent_at < PROGRESS_INTERVAL:
            return
        entry.sent, entry.sent_at = progress, now
        self._outbox.put(TaskProgress(task.id, progress))

    # ---- the thread that hands events to the listener

    def _send_events(self) -> None:
        while (event := self._outbox.get()) is not None:
            try:
                self._emit(event)
            except Exception:
                log.exception("the event listener failed")


def _snapshot(task: DownloadTask) -> QueueItem:
    return QueueItem(
        task.id,
        task.url,
        task.format,
        task.quality,
        task.status,
        task.title,
        task.thumb,
        task.progress,
        task.attempt,
        task.size_bytes,
        task.skipped,
        task.error,
    )


def _require_http(url: str) -> None:
    try:
        parts = urlsplit(url)
        ok = parts.scheme in ("http", "https") and bool(parts.hostname)
    except ValueError:
        ok = False
    if not ok or any(c.isspace() for c in url):
        raise EngineError(ErrorCode.INVALID_URL, url)
