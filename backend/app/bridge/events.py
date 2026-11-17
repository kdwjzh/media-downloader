"""Hands the backend's events to the web page, one at a time and in order.

emit() is called on the queue's sender thread, on download threads and, for settings, while
the settings' write lock is held (hand-over 3.3). It only puts the event in a queue; one
daemon thread converts it and calls the page. Nothing here calls a service.
"""

import json
import logging
import queue
import threading
from collections.abc import Callable

from app.bridge import shapes
from app.services.queue import TasksChanged

log = logging.getLogger(__name__)

# The function frontend/src/api/ puts on window. Only this file and api/ know the name.
RECEIVER = "mediaDownloaderEvent"


def script(payload: str) -> str:
    """JavaScript that hands one event to the page; it evaluates to whether the page took it."""
    return (
        f"typeof window.{RECEIVER} === 'function'"
        f" ? (window.{RECEIVER}({payload}), true) : false"
    )


class EventSender:
    def __init__(
        self, run_js: Callable[[str], object], close_window: Callable[[], None]
    ) -> None:
        """run_js evaluates a script in the page and returns its value; it may block until
        the page is ready, and raise. close_window closes the window without asking: used
        when a request to close cannot reach the page, so the window never gets stuck."""
        self._run_js = run_js
        self._close_window = close_window
        self._events: queue.SimpleQueue[shapes.Event | None] = queue.SimpleQueue()
        self._held: list[shapes.Event | None] = []  # taken off the queue while merging; goes next
        self._closing = threading.Event()
        self._thread = threading.Thread(target=self._send_all, name="bridge-events", daemon=True)

    def emit(self, event: shapes.Event) -> None:
        self._events.put(event)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        """The window is closing: whatever is still waiting is dropped."""
        self._closing.set()
        self._events.put(None)

    def _next(self) -> shapes.Event | None:
        """The next event to send. tasksChanged events already waiting right behind one
        another go as one: each id once, where it first appeared, with its latest state, so the
        page ends where the separate events would have left it (contract section 4). One at a
        time, cancelling 5,339 tasks took 93 s to reach the page (stage 4c). Any other kind of
        event stops the merge, so the order between kinds stays as it was."""
        event = self._held.pop() if self._held else self._events.get()
        if not isinstance(event, TasksChanged):
            return event
        tasks = {task.id: task for task in event.tasks}
        while True:
            try:
                after = self._events.get_nowait()
            except queue.Empty:
                break
            if not isinstance(after, TasksChanged):
                self._held.append(after)
                break
            tasks.update((task.id, task) for task in after.tasks)  # a known id keeps its place
        return TasksChanged(tuple(tasks.values()))

    def _send_all(self) -> None:
        while (event := self._next()) is not None:
            if self._closing.is_set():
                continue
            try:
                taken = self._run_js(script(json.dumps(shapes.event(event), ensure_ascii=False)))
            except Exception:
                # Not ready in time, closing, or the page threw. The next event goes on.
                log.exception("could not send an event to the page")
                taken = False
            if not taken:
                # The page has no receiver yet (still loading, or reloading in development).
                # It asks for the whole state when it starts, so nothing is lost but this one.
                log.debug("the page took no %s", type(event).__name__)
                if isinstance(event, shapes.CloseRequested) and not self._closing.is_set():
                    log.warning("a request to close did not reach the page: closing")
                    self._close_window()
