"""Events on their way to the page: the JSON of each of the six kinds (contract section 4),
and the sender's thread. No window: run_js is a stand-in that records what the page got."""

import json
import queue
import re
import threading

import pytest

from app.bridge import shapes
from app.bridge.events import RECEIVER, EventSender, script
from app.domain.history import HistoryEntry
from app.domain.media import Format
from app.domain.progress import Progress
from app.domain.settings import Settings
from app.domain.task import TaskStatus
from app.services.history import HistoryAdded
from app.services.queue import QueueItem, TaskProgress, TasksChanged, TasksRemoved
from app.services.settings import SettingsChanged

WAIT = 5  # seconds; only reached when something is broken

EVENTS: list[tuple[shapes.Event, dict[str, object]]] = [
    (TasksChanged((QueueItem("a", "u", Format.MP3, 320, TaskStatus.QUEUED, title="t"),)),
     {"type": "tasksChanged", "tasks": [
         {"id": "a", "url": "u", "format": "mp3", "quality": 320, "status": "queued",
          "title": "t"}]}),
    (TasksRemoved(("a", "b")), {"type": "tasksRemoved", "ids": ["a", "b"]}),
    (TaskProgress("a", Progress(10, 1, 1000, 99.4, 10)),
     {"type": "taskProgress", "progress": {"id": "a", "percent": 1, "doneBytes": 10,
                                           "totalBytes": 1000, "speedBps": 99, "etaSec": 10}}),
    # Fields this time without a value are absent: the page replaces all five (2.8).
    (TaskProgress("a", Progress(10, None)),
     {"type": "taskProgress", "progress": {"id": "a", "doneBytes": 10}}),
    (HistoryAdded(HistoryEntry("h", "u", "t", Format.MP4, 720, 5, "2026-11-16T00:00:00Z")),
     {"type": "historyAdded", "entry": {"id": "h", "url": "u", "title": "t", "format": "mp4",
                                        "quality": 720, "sizeBytes": 5,
                                        "finishedAt": "2026-11-16T00:00:00Z"}}),
    (SettingsChanged(Settings("D:\\dl")),
     {"type": "settingsChanged", "settings": {
         "downloadDir": "D:\\dl", "maxConcurrent": 3, "onDuplicate": "rename", "format": "mp3",
         "mp3Bitrate": 320, "mp4Height": 1080, "language": "system"}}),
    (shapes.CloseRequested(), {"type": "closeRequested"}),
]  # fmt: skip


@pytest.mark.parametrize(("event", "expected"), EVENTS)
def test_event_json(event: shapes.Event, expected: dict[str, object]) -> None:
    assert shapes.event(event) == expected


def test_every_kind_of_event_is_covered() -> None:
    kinds = {e["type"] for _, e in EVENTS}
    assert kinds == {"tasksChanged", "tasksRemoved", "taskProgress", "historyAdded",
                     "settingsChanged", "closeRequested"}  # fmt: skip


def payload_of(js: str) -> object:
    """The event a script hands to the page."""
    found = re.search(rf"window\.{RECEIVER}\((.*)\), true\) : false$", js, re.S)
    assert found, js
    return json.loads(found.group(1))


def test_the_script_checks_for_the_receiver_first() -> None:
    js = script('{"type": "tasksRemoved", "ids": []}')
    assert js.startswith(f"typeof window.{RECEIVER} === 'function'")
    assert payload_of(js) == {"type": "tasksRemoved", "ids": []}


class Page:
    """Stands in for evaluate_js. Each call can be held until the test lets it go."""

    def __init__(self) -> None:
        self.got: queue.Queue[object] = queue.Queue()
        self.answers: queue.Queue[object] = queue.Queue()  # what the next calls return
        self.hold = threading.Event()
        self.hold.set()
        self.closed = threading.Event()
        self.entered = threading.Event()  # a call has started

    def run_js(self, js: str) -> object:
        self.entered.set()
        assert self.hold.wait(WAIT)
        self.got.put(payload_of(js))
        answer = self.answers.get_nowait() if not self.answers.empty() else True
        if isinstance(answer, Exception):
            raise answer
        return answer

    def close_window(self) -> None:
        self.closed.set()

    def next(self) -> object:
        return self.got.get(timeout=WAIT)


@pytest.fixture
def page() -> Page:
    return Page()


@pytest.fixture
def sender(page: Page) -> EventSender:
    sender = EventSender(page.run_js, page.close_window)
    sender.start()
    return sender


def removed(*ids: str) -> TasksRemoved:
    return TasksRemoved(ids)


def test_emit_returns_at_once_while_the_page_is_slow(page: Page, sender: EventSender) -> None:
    page.hold.clear()  # the page does not answer
    done = threading.Event()

    def producer() -> None:
        for i in range(200):
            sender.emit(removed(str(i)))
        done.set()

    threading.Thread(target=producer, daemon=True).start()
    assert done.wait(WAIT), "emit waited for the page"
    page.hold.set()
    assert [page.next() for _ in range(200)] == [
        {"type": "tasksRemoved", "ids": [str(i)]} for i in range(200)
    ]


def changed(*tasks: tuple[str, TaskStatus]) -> TasksChanged:
    return TasksChanged(tuple(QueueItem(i, "u", Format.MP3, 320, status) for i, status in tasks))


def test_task_changes_waiting_behind_one_another_go_as_one(page: Page, sender: EventSender) -> None:
    # Cancel all on 5,339 tasks sent 5,339 events, one at a time: 93 s before the page
    # showed them all (stage 4c). Whatever piles up while the page is busy goes together.
    page.hold.clear()
    sender.emit(removed("first"))
    assert page.entered.wait(WAIT)  # the page is busy with it; the rest wait in line
    sender.emit(changed(("a", TaskStatus.QUEUED)))
    sender.emit(changed(("b", TaskStatus.QUEUED)))
    sender.emit(changed(("a", TaskStatus.CANCELLED)))
    sender.emit(removed("x"))  # another kind keeps its place: no merging across it
    sender.emit(changed(("c", TaskStatus.QUEUED)))
    sender.emit(changed(("b", TaskStatus.CANCELLED)))
    page.hold.set()

    def statuses(got: object) -> list[tuple[str, str]]:
        assert isinstance(got, dict) and got["type"] == "tasksChanged", got
        return [(t["id"], t["status"]) for t in got["tasks"]]

    assert page.next() == {"type": "tasksRemoved", "ids": ["first"]}
    # Each id once, where it first appeared, with its latest state: the page ends up
    # exactly where the separate events would have left it.
    assert statuses(page.next()) == [("a", "cancelled"), ("b", "queued")]
    assert page.next() == {"type": "tasksRemoved", "ids": ["x"]}
    assert statuses(page.next()) == [("c", "queued"), ("b", "cancelled")]
    assert page.got.empty()


def test_events_from_several_threads_reach_the_page_one_at_a_time(
    page: Page, sender: EventSender
) -> None:
    def produce(n: int) -> None:
        for i in range(50):
            sender.emit(removed(f"{n}-{i}"))

    threads = [threading.Thread(target=produce, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT)
    got = [page.next() for _ in range(200)]
    for n in range(4):  # each thread's own events keep their order
        mine = [g["ids"][0] for g in got if g["ids"][0].startswith(f"{n}-")]  # type: ignore[index]
        assert mine == [f"{n}-{i}" for i in range(50)]


def test_an_event_the_page_cannot_take_yet_is_dropped_and_the_next_goes_on(
    page: Page, sender: EventSender
) -> None:
    # No receiver yet (the page is still loading): the page asks for everything when it starts.
    page.answers.put(False)
    sender.emit(removed("lost"))
    sender.emit(removed("next"))
    assert page.next() == {"type": "tasksRemoved", "ids": ["lost"]}
    assert page.next() == {"type": "tasksRemoved", "ids": ["next"]}
    assert not page.closed.is_set()


def test_a_page_that_fails_is_logged_and_the_next_event_goes_on(
    page: Page, sender: EventSender, caplog: pytest.LogCaptureFixture
) -> None:
    page.answers.put(RuntimeError("Main window failed to start"))
    sender.emit(removed("a"))
    sender.emit(removed("b"))
    page.next()
    assert page.next() == {"type": "tasksRemoved", "ids": ["b"]}
    assert "could not send an event to the page" in caplog.text


def test_after_close_nothing_more_is_sent(page: Page, sender: EventSender) -> None:
    page.hold.clear()
    sender.emit(removed("in flight"))
    assert page.entered.wait(WAIT)  # the sender is inside the page now
    sender.close()
    sender.emit(removed("late"))
    sender.emit(shapes.CloseRequested())
    page.hold.set()
    assert page.next() == {"type": "tasksRemoved", "ids": ["in flight"]}
    sender._thread.join(WAIT)
    assert not sender._thread.is_alive() and page.got.empty()
    assert not page.closed.is_set()


def test_a_request_to_close_the_page_took_does_not_close(page: Page, sender: EventSender) -> None:
    sender.emit(shapes.CloseRequested())
    sender.emit(removed("after"))
    assert page.next() == {"type": "closeRequested"}
    page.next()
    assert not page.closed.is_set()


@pytest.mark.parametrize("answer", [False, RuntimeError("the page threw")])
def test_a_request_to_close_that_cannot_reach_the_page_closes_the_window(
    page: Page, sender: EventSender, answer: object
) -> None:
    # Otherwise a broken page would leave a window that cannot be closed.
    page.answers.put(answer)
    sender.emit(shapes.CloseRequested())
    assert page.closed.wait(WAIT)
