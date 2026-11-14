"""A MediaEngine that the tests drive step by step: nothing happens until a test says so,
and every step waits until the code under test has dealt with it. No sleeping."""

import queue
import threading
from collections.abc import Callable

from app.domain.engine import DownloadCancelled, DownloadRequest, DownloadResult, EngineEvent
from app.domain.media import Format, FormatOption, MediaInfo, PlaylistInfo

WAIT = 5  # seconds before a test that is stuck fails; never reached when things work

Answer = MediaInfo | PlaylistInfo | Exception
THUMB = "https://example.com/thumb.jpg"


def info(url: str, title: str = "Song") -> MediaInfo:
    return MediaInfo(url, title, 60, "fake", (FormatOption(Format.MP3, 320, 1),), thumb=THUMB)


class Download:
    """One call of download() that is still running."""

    def __init__(self, request: DownloadRequest, on_event: Callable[[EngineEvent], None]) -> None:
        self.request = request
        self.thread = threading.current_thread()
        self._on_event = on_event
        self.steps: queue.Queue[EngineEvent | DownloadResult | Exception] = queue.Queue()
        self._handled: queue.Queue[None] = queue.Queue()

    def send(self, event: EngineEvent) -> None:
        """Reports an event; returns once the handler has returned."""
        self.steps.put(event)
        self._handled.get(timeout=WAIT)

    def end(self, outcome: DownloadResult | Exception) -> None:
        """Makes download() return or raise; returns once its thread is completely done."""
        self.steps.put(outcome)
        self.wait_ended()

    def wait_ended(self) -> None:
        self.thread.join(WAIT)
        assert not self.thread.is_alive()

    def run(self) -> DownloadResult:
        while True:
            step = self.steps.get(timeout=WAIT * 4)
            if isinstance(step, DownloadResult):
                return step
            if isinstance(step, Exception):
                raise step
            self._on_event(step)
            self._handled.put(None)


class FakeEngine:
    def __init__(self) -> None:
        self.started: queue.Queue[Download] = queue.Queue()
        # A lookup of a URL without a prepared answer waits here for the test to answer it.
        self.lookups: queue.Queue[tuple[str, queue.Queue[Answer]]] = queue.Queue()
        self.answers: dict[str, Answer] = {}
        self.fetched: list[str] = []
        self.cancels: list[str] = []
        self.ignore_cancel = False  # the gap: cancel() arrives before the process exists
        self.cleaned: list[str] = []
        self.stopped = False
        self._lock = threading.Lock()
        self._running: dict[str, Download] = {}

    def fetch_info(self, url: str) -> MediaInfo | PlaylistInfo:
        self.fetched.append(url)
        answer = self.answers.get(url)
        if answer is None:
            pending: queue.Queue[Answer] = queue.Queue()
            self.lookups.put((url, pending))
            answer = pending.get(timeout=WAIT * 4)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def answer_lookup(self, answer: Answer | None = None) -> str:
        """Ends the oldest waiting lookup (by default: with a video titled "Song")."""
        url, pending = self.lookups.get(timeout=WAIT)
        pending.put(answer or info(url))
        return url

    def download(
        self, request: DownloadRequest, on_event: Callable[[EngineEvent], None]
    ) -> DownloadResult:
        download = Download(request, on_event)
        with self._lock:
            assert request.task_id not in self._running, "two downloads share a task folder"
            self._running[request.task_id] = download
        self.started.put(download)
        try:
            return download.run()
        finally:
            with self._lock:
                del self._running[request.task_id]

    def cancel(self, task_id: str) -> None:
        self.cancels.append(task_id)
        with self._lock:
            download = self._running.get(task_id)
        if download and not self.ignore_cancel:
            download.steps.put(DownloadCancelled(task_id))

    def stop_all(self) -> None:
        self.stopped = True
        with self._lock:
            task_ids = list(self._running)
        for task_id in task_ids:
            self.cancel(task_id)

    def remove_stale_temp(self, dest_dir: str) -> None:
        self.cleaned.append(dest_dir)

    def version(self) -> str:
        return "fake"

    def update(self) -> bool:
        return False
