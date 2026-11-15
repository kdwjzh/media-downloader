"""QueueService with a fake engine and a fake clock. No network, no yt-dlp, no sleeping:
every step of a download happens when the test says so."""

import queue
import threading
from collections.abc import Callable, Iterator
from dataclasses import fields, replace

import pytest
from fake_engine import THUMB, WAIT, Download, FakeEngine, info

from app.domain.engine import (
    ConnectionLost,
    DownloadCancelled,
    DownloadResult,
    EngineError,
    FileProgress,
    FileSizes,
    OnDuplicate,
    PostProcessing,
)
from app.domain.errors import ErrorCode
from app.domain.media import Format, PlaylistInfo
from app.domain.progress import Progress
from app.domain.task import TaskStatus
from app.services.media_info import MediaInfoService
from app.services.ports import FinishedDownload, InMemoryHistory, InMemorySettings
from app.services.queue import (
    MAX_LOOKUPS,
    QueueEvent,
    QueueItem,
    QueueService,
    TaskProgress,
    TasksChanged,
    TasksRemoved,
)

S = TaskStatus
FILE = "C:\\dl\\Song.mp3"
RESULT = DownloadResult(FILE, 1234)
NEW_URL = "https://example.com/not-looked-up-yet"


class Harness:
    def __init__(
        self, max_concurrent: int = 3, emit: Callable[[QueueEvent], None] | None = None
    ) -> None:
        self.engine = FakeEngine()
        self.media = MediaInfoService(self.engine)
        self.settings = InMemorySettings("C:\\dl", max_concurrent)
        self.history = InMemoryHistory()
        self.now = 0.0
        self.events: queue.Queue[QueueEvent] = queue.Queue()
        self.log: list[QueueEvent] = []  # every event a test has taken, in order
        self._count = 0
        self.service = QueueService(
            self.engine,
            self.media,
            self.settings,
            self.history,
            emit or self.events.put,
            lambda: self.now,
        )

    def add(self, count: int = 1, format: Format = Format.MP3, quality: int = 320) -> list[str]:
        """Adds tasks whose titles are already known, so they need no lookup."""
        urls = []
        for _ in range(count):
            self._count += 1
            urls.append(f"https://example.com/v/{self._count}")
            self.media.remember(urls[-1], f"Title {self._count}", THUMB)
        return self.service.add(urls, format, quality)

    def downloading(self, format: Format = Format.MP3) -> tuple[str, Download]:
        [task_id] = self.add(format=format, quality=320 if format is Format.MP3 else 1080)
        return task_id, self.started()

    def started(self) -> Download:
        return self.engine.started.get(timeout=WAIT)

    def flush(self) -> list[QueueEvent]:
        """Every event sent since the last call. Only use when no thread is still working."""
        marker = TasksRemoved(("-marker-",))
        self.service._outbox.put(marker)
        new: list[QueueEvent] = []
        while (event := self.events.get(timeout=WAIT)) != marker:
            new.append(event)
        self.log += new
        return new

    def wait(self, task_id: str, status: TaskStatus) -> QueueItem:
        """Takes events until that task is reported with that status."""
        while True:
            event = self.events.get(timeout=WAIT)
            self.log.append(event)
            if isinstance(event, TasksChanged):
                for item in event.tasks:
                    if item.id == task_id and item.status is status:
                        return item

    def item(self, task_id: str) -> QueueItem:
        return next(item for item in self.service.items() if item.id == task_id)

    def statuses(self) -> list[TaskStatus]:
        return [item.status for item in self.service.items()]

    def finished(self, how: str) -> str:
        """A task that ended as "done", "failed" (network), "private" or "cancelled"."""
        task_id, download = self.downloading()
        if how == "cancelled":
            self.service.cancel(task_id)
            download.wait_ended()
        else:
            ends: dict[str, DownloadResult | Exception] = {
                "done": RESULT,
                "failed": EngineError(ErrorCode.NETWORK),
                "private": EngineError(ErrorCode.PRIVATE),
            }
            download.end(ends[how])
        self.flush()
        return task_id


Make = Callable[..., Harness]


@pytest.fixture
def make() -> Iterator[Make]:
    made: list[Harness] = []

    def factory(*args: object, **kwargs: object) -> Harness:
        made.append(Harness(*args, **kwargs))  # type: ignore[arg-type]
        return made[-1]

    yield factory
    for harness in made:
        harness.engine.ignore_cancel = False
        harness.service.shutdown()


@pytest.fixture
def q(make: Make) -> Harness:
    return make()


def trail(events: list[QueueEvent], task_id: str) -> list[str]:
    """What the UI was told about one task: statuses and percentages, in order."""
    out: list[str] = []
    for event in events:
        if isinstance(event, TasksChanged):
            out += [item.status.value for item in event.tasks if item.id == task_id]
        elif isinstance(event, TaskProgress) and event.id == task_id:
            out.append(f"{event.progress.percent}%")
    return out


def progress(done: int, total: int = 1000) -> FileProgress:
    return FileProgress(0, 1, done, total, 100.0)


# ---- add


def test_added_tasks_start_in_order_and_are_reported(q: Harness) -> None:
    ids = q.add(2)
    first, second = q.started(), q.started()
    assert {first.request.task_id, second.request.task_id} == set(ids)
    assert all(task_id.isalnum() for task_id in ids)  # the id becomes a folder name
    assert [item.id for item in q.service.items()] == ids
    events = q.flush()
    added = events[0]
    assert isinstance(added, TasksChanged)  # both new tasks in one event, in order
    assert [(item.id, item.status, item.title) for item in added.tasks] == [
        (ids[0], S.QUEUED, "Title 1"),
        (ids[1], S.QUEUED, "Title 2"),
    ]
    assert trail(events, ids[0]) == ["queued", "downloading"]
    assert first.request.dest_dir == "C:\\dl" and first.request.format is Format.MP3
    assert first.request.quality == 320


def test_the_same_url_twice_is_two_tasks(q: Harness) -> None:
    q.media.remember("https://example.com/same", "Same")
    first = q.service.add(["https://example.com/same"], Format.MP3, 128)
    second = q.service.add(["https://example.com/same"], Format.MP3, 128)
    assert first != second and len(q.service.items()) == 2


def test_pasted_text_is_tidied_like_a_lookup(q: Harness) -> None:
    q.media.remember("https://example.com/v", "Known")
    [task_id] = q.service.add(["  example.com/v \n"], Format.MP3, 128)
    assert (q.item(task_id).url, q.item(task_id).title) == ("https://example.com/v", "Known")


@pytest.mark.parametrize("bad", ["", "hello", "ftp://example.com/v", "https://", "a b.com/x", "-U"])
def test_one_bad_url_adds_nothing(q: Harness, bad: str) -> None:
    q.media.remember("https://example.com/ok", "Ok")
    with pytest.raises(EngineError) as error:
        q.service.add(["https://example.com/ok", bad], Format.MP3, 320)
    assert error.value.code is ErrorCode.INVALID_URL
    assert q.service.items() == [] and q.flush() == []
    assert q.settings.last_format is None


def test_a_quality_of_the_other_format_or_no_url_adds_nothing(q: Harness) -> None:
    with pytest.raises(ValueError):
        q.service.add(["https://example.com/ok"], Format.MP3, 1080)
    with pytest.raises(ValueError):
        q.service.add([], Format.MP3, 320)
    assert q.service.items() == [] and q.flush() == []


def test_adding_remembers_the_format_unless_told_not_to(q: Harness) -> None:
    q.add(format=Format.MP4, quality=720)
    assert q.settings.last_format == (Format.MP4, 720)
    q.service.add(["https://example.com/again"], Format.MP3, 128, remember=False)
    assert q.settings.last_format == (Format.MP4, 720)


def test_the_folder_is_fixed_when_added_and_the_duplicate_rule_when_started(make: Make) -> None:
    q = make(max_concurrent=1)
    q.add(2)
    first = q.started()
    q.settings.download_dir = "D:\\elsewhere"
    q.settings.on_duplicate = OnDuplicate.SKIP
    first.end(RESULT)
    second = q.started()
    assert first.request.on_duplicate is OnDuplicate.RENAME
    assert (second.request.dest_dir, second.request.on_duplicate) == ("C:\\dl", OnDuplicate.SKIP)


# ---- tasks added with nothing but a URL


def test_a_url_alone_is_looked_up_then_downloaded(q: Harness) -> None:
    [task_id] = q.service.add([NEW_URL], Format.MP3, 192)
    assert q.item(task_id).status is S.FETCHING
    assert q.engine.answer_lookup() == NEW_URL
    item = q.wait(task_id, S.QUEUED)
    assert (item.title, item.thumb) == ("Song", THUMB)
    assert q.started().request.url == NEW_URL


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (EngineError(ErrorCode.PRIVATE, "raw"), ErrorCode.PRIVATE),
        (EngineError(ErrorCode.NETWORK, "raw"), ErrorCode.NETWORK),
        (RuntimeError("boom"), ErrorCode.UNKNOWN),
        (PlaylistInfo(NEW_URL, "List", "fake", ()), ErrorCode.PLAYLIST_URL),
    ],
)
def test_a_lookup_that_fails_fails_the_task(q: Harness, answer: object, code: ErrorCode) -> None:
    [task_id] = q.service.add([NEW_URL], Format.MP3, 192)
    q.engine.answer_lookup(answer)  # type: ignore[arg-type]
    assert q.wait(task_id, S.FAILED).error is code
    assert q.engine.started.empty()


def test_lookups_need_no_download_slot_but_have_their_own_limit(make: Make) -> None:
    q = make(max_concurrent=1)
    q.downloading()  # the only slot is taken
    urls = [f"https://example.com/new/{n}" for n in range(MAX_LOOKUPS + 2)]
    ids = q.service.add(urls, Format.MP3, 320)
    waiting = dict(q.engine.lookups.get(timeout=WAIT) for _ in range(MAX_LOOKUPS))
    # Every lookup thread is now inside the engine, so nothing else can have been asked.
    # (Which of the threads got there first is not fixed.)
    assert sorted(q.engine.fetched) == urls[:MAX_LOOKUPS]
    waiting[urls[0]].put(info(urls[0]))
    assert q.engine.lookups.get(timeout=WAIT)[0] == urls[MAX_LOOKUPS]
    assert q.wait(ids[0], S.QUEUED).title == "Song"
    assert q.statuses().count(S.DOWNLOADING) == 1


def test_a_task_cancelled_while_waiting_for_a_lookup_is_never_looked_up(q: Harness) -> None:
    urls = [f"https://example.com/new/{n}" for n in range(MAX_LOOKUPS + 1)]
    ids = q.service.add(urls, Format.MP3, 320)
    waiting = dict(q.engine.lookups.get(timeout=WAIT) for _ in range(MAX_LOOKUPS))
    q.service.cancel(ids[-1])
    q.service.cancel(ids[0])
    for url, pending in waiting.items():
        pending.put(info(url))
    q.wait(ids[1], S.QUEUED)
    assert q.item(ids[0]).status is S.CANCELLED  # its late answer changed nothing
    assert q.item(ids[0]).title is None
    assert urls[-1] not in q.engine.fetched


# ---- cancel


def test_cancel_stops_a_download_and_frees_its_slot(make: Make) -> None:
    q = make(max_concurrent=1)
    ids = q.add(2)
    download = q.started()
    q.service.cancel(ids[0])
    assert q.item(ids[0]).status is S.CANCELLED  # at once, not when the engine is done
    download.wait_ended()
    assert q.engine.cancels == [ids[0]]
    assert q.started().request.task_id == ids[1]
    assert trail(q.flush(), ids[0]) == ["queued", "downloading", "cancelled"]


def test_cancel_while_converting(q: Harness) -> None:
    task_id, download = q.downloading()
    download.send(progress(1000))
    download.send(PostProcessing())
    q.service.cancel(task_id)
    download.wait_ended()
    assert trail(q.flush(), task_id)[-2:] == ["converting", "cancelled"]


def test_cancel_a_waiting_task_and_a_task_being_looked_up(make: Make) -> None:
    q = make(max_concurrent=1)
    ids = q.add(2)
    [fetching] = q.service.add([NEW_URL], Format.MP3, 320)
    q.service.cancel(ids[1])
    q.service.cancel(fetching)
    assert q.statuses() == [S.DOWNLOADING, S.CANCELLED, S.CANCELLED]
    assert q.engine.cancels == []  # the engine never had them
    q.started().end(RESULT)
    assert q.engine.started.empty()  # the cancelled one did not start


@pytest.mark.parametrize("how", ["done", "failed", "cancelled"])
def test_cancel_does_nothing_to_a_finished_task(q: Harness, how: str) -> None:
    task_id = q.finished(how)
    before = q.item(task_id)
    q.service.cancel(task_id)
    q.service.cancel("no-such-task")
    assert q.item(task_id) == before and q.flush() == []


def test_cancel_before_the_engine_has_a_process_still_ends_cancelled(q: Harness) -> None:
    task_id, download = q.downloading()
    q.engine.ignore_cancel = True  # the engine's process does not exist yet
    q.service.cancel(task_id)
    assert q.item(task_id).status is S.CANCELLED
    q.engine.ignore_cancel = False
    download.send(FileSizes((1000,)))  # the process exists now, and says something
    download.wait_ended()
    assert q.engine.cancels == [task_id, task_id]  # the queue asked again
    assert q.item(task_id).status is S.CANCELLED
    assert trail(q.flush(), task_id) == ["queued", "downloading", "cancelled"]


def test_a_download_that_completes_after_its_cancel_stays_cancelled(q: Harness) -> None:
    task_id, download = q.downloading()
    q.engine.ignore_cancel = True
    q.service.cancel(task_id)
    download.end(RESULT)
    assert q.item(task_id).status is S.CANCELLED
    assert q.history.records == [] and q.service.file_path(task_id) is None
    assert trail(q.flush(), task_id) == ["queued", "downloading", "cancelled"]


# ---- retry and re-add


def test_retry_keeps_id_and_place_and_starts_from_zero(q: Harness) -> None:
    ids = q.add(3)
    downloads = {d.request.task_id: d for d in (q.started(), q.started(), q.started())}
    downloads[ids[1]].send(progress(500))
    downloads[ids[1]].end(EngineError(ErrorCode.NETWORK, "raw"))
    assert (q.item(ids[1]).status, q.item(ids[1]).error) == (S.FAILED, ErrorCode.NETWORK)
    q.flush()
    q.service.retry(ids[1])
    again = q.started()
    assert again.request.task_id == ids[1]
    assert [item.id for item in q.service.items()] == ids
    item = q.item(ids[1])
    assert (item.status, item.error, item.progress) == (S.DOWNLOADING, None, Progress())
    again.send(progress(100))
    assert trail(q.flush(), ids[1]) == ["queued", "downloading", "10%"]


@pytest.mark.parametrize("how", ["done", "private", "cancelled"])
def test_retry_does_nothing_unless_failed_with_a_retryable_error(q: Harness, how: str) -> None:
    task_id = q.finished(how)
    before = q.item(task_id)
    q.service.retry(task_id)
    q.service.retry("no-such-task")
    assert q.item(task_id) == before and q.flush() == []


def test_retry_does_nothing_to_a_running_task(q: Harness) -> None:
    task_id, _ = q.downloading()
    q.flush()
    q.service.retry(task_id)
    q.service.readd(task_id)
    assert q.item(task_id).status is S.DOWNLOADING and q.flush() == []


def test_retry_of_a_failed_lookup_looks_up_again(q: Harness) -> None:
    [task_id] = q.service.add([NEW_URL], Format.MP3, 192)
    q.engine.answer_lookup(EngineError(ErrorCode.NETWORK, "raw"))
    q.wait(task_id, S.FAILED)
    q.service.retry(task_id)
    assert q.wait(task_id, S.FETCHING).error is None
    q.engine.answer_lookup()
    assert q.wait(task_id, S.QUEUED).title == "Song"


def test_readd_runs_a_cancelled_task_again(q: Harness) -> None:
    task_id = q.finished("cancelled")
    q.service.readd(task_id)
    again = q.started()
    assert again.request.task_id == task_id
    again.end(RESULT)
    assert trail(q.flush(), task_id) == ["queued", "downloading", "done"]


@pytest.mark.parametrize("how", ["done", "failed"])
def test_readd_does_nothing_unless_cancelled(q: Harness, how: str) -> None:
    task_id = q.finished(how)
    before = q.item(task_id)
    q.service.readd(task_id)
    q.service.readd("no-such-task")
    assert q.item(task_id) == before and q.flush() == []


def test_a_readded_task_waits_until_its_old_download_has_cleaned_up(q: Harness) -> None:
    task_id, old = q.downloading()
    q.engine.ignore_cancel = True  # the old download takes its time to stop
    q.service.cancel(task_id)
    q.service.readd(task_id)
    assert q.item(task_id).status is S.QUEUED  # a free slot, but its folder is still in use
    q.engine.ignore_cancel = False
    old.end(DownloadCancelled(task_id))
    new = q.started()  # FakeEngine asserts that the two never overlap
    new.end(RESULT)
    assert trail(q.flush(), task_id) == [
        "queued", "downloading", "cancelled", "queued", "downloading", "done",
    ]  # fmt: skip


# ---- remove


def test_remove_and_clear_only_take_finished_tasks(make: Make) -> None:
    q = make(max_concurrent=1)
    done, failed, cancelled = q.finished("done"), q.finished("failed"), q.finished("cancelled")
    running, _ = q.downloading()
    [waiting] = q.add()
    [fetching] = q.service.add([NEW_URL], Format.MP3, 320)
    q.flush()
    for task_id in (running, waiting, fetching, "no-such-task"):
        q.service.remove(task_id)
    assert q.flush() == [] and len(q.service.items()) == 6
    q.service.remove(failed)
    assert q.flush() == [TasksRemoved((failed,))]
    q.service.clear_finished()
    assert q.flush() == [TasksRemoved((done, cancelled))]
    assert [item.id for item in q.service.items()] == [running, waiting, fetching]
    q.service.clear_finished()
    assert q.flush() == []  # nothing finished: no event


# ---- how many at once


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_no_more_than_the_limit_download_at_once(make: Make, limit: int) -> None:
    q = make(max_concurrent=limit)
    ids = q.add(5)
    running = [q.started() for _ in range(limit)]
    assert {d.request.task_id for d in running} == set(ids[:limit])
    assert q.statuses() == [S.DOWNLOADING] * limit + [S.QUEUED] * (5 - limit)
    running[0].end(RESULT)
    assert q.started().request.task_id == ids[limit]  # the next in line takes the free slot
    assert q.statuses().count(S.DOWNLOADING) == limit


def test_raising_the_limit_starts_waiting_tasks_at_once(make: Make) -> None:
    q = make(max_concurrent=1)
    ids = q.add(4)
    q.started()
    q.settings.max_concurrent = 3
    q.service.settings_changed()
    assert {q.started().request.task_id, q.started().request.task_id} == set(ids[1:3])
    assert q.statuses() == [S.DOWNLOADING] * 3 + [S.QUEUED]


def test_lowering_the_limit_stops_nothing_and_takes_effect_as_downloads_end(make: Make) -> None:
    q = make(max_concurrent=3)
    q.add(5)
    running = [q.started() for _ in range(3)]
    q.settings.max_concurrent = 1
    q.service.settings_changed()
    assert q.statuses().count(S.DOWNLOADING) == 3 and q.engine.cancels == []
    running[0].end(RESULT)
    running[1].end(RESULT)
    assert q.statuses().count(S.DOWNLOADING) == 1  # two ended, none started
    running[2].end(RESULT)
    q.started()
    assert q.statuses().count(S.DOWNLOADING) == 1


# ---- how a download ends


def test_done_records_history_and_keeps_the_path_to_itself(q: Harness) -> None:
    task_id, download = q.downloading()
    download.end(RESULT)
    item = q.item(task_id)
    assert (item.status, item.size_bytes, item.skipped) == (S.DONE, 1234, False)
    assert q.history.records == [
        FinishedDownload(item.url, "Title 1", Format.MP3, 320, 1234, FILE, THUMB)
    ]
    assert q.service.file_path(task_id) == FILE
    assert "file_path" not in {field.name for field in fields(QueueItem)}


@pytest.mark.parametrize("converted", [False, True])
def test_skipped_is_done_with_a_flag_and_no_history(q: Harness, converted: bool) -> None:
    task_id, download = q.downloading()
    if converted:  # the same video was queued twice; the other one placed its file first
        download.send(PostProcessing())
    download.end(DownloadResult(FILE, 999, skipped=True))
    item = q.item(task_id)
    assert (item.status, item.skipped, item.size_bytes) == (S.DONE, True, None)
    assert q.history.records == []
    assert q.service.file_path(task_id) == FILE  # the file that was already there


def test_an_engine_error_fails_the_task_with_its_code(
    q: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    task_id, download = q.downloading()
    download.end(EngineError(ErrorCode.GEO_BLOCKED, "ERROR: the raw yt-dlp text"))
    assert (q.item(task_id).status, q.item(task_id).error) == (S.FAILED, ErrorCode.GEO_BLOCKED)
    assert "the raw yt-dlp text" in caplog.text  # kept for the log file


def test_any_other_exception_fails_the_task_as_unknown_and_frees_the_slot(
    make: Make, caplog: pytest.LogCaptureFixture
) -> None:
    q = make(max_concurrent=1)
    ids = q.add(2)
    q.started().end(ZeroDivisionError("something nobody expected"))
    assert (q.item(ids[0]).status, q.item(ids[0]).error) == (S.FAILED, ErrorCode.UNKNOWN)
    assert "something nobody expected" in caplog.text and "ZeroDivisionError" in caplog.text
    assert q.started().request.task_id == ids[1]


def test_a_download_cancelled_by_the_engine_itself_ends_cancelled(q: Harness) -> None:
    task_id, download = q.downloading()
    download.end(DownloadCancelled(task_id))
    assert q.item(task_id).status is S.CANCELLED


def test_a_download_that_succeeds_while_retrying_is_done(q: Harness) -> None:
    # The file is in the folder: whatever the task's status was, it must not show as failed.
    task_id, download = q.downloading()
    download.send(progress(100))
    download.send(ConnectionLost(1))
    download.end(RESULT)
    assert (q.item(task_id).status, q.item(task_id).error) == (S.DONE, None)


def test_a_failing_history_does_not_touch_the_task(q: Harness) -> None:
    def broken(download: FinishedDownload) -> None:
        raise OSError("disk full")

    q.history.record = broken  # type: ignore[method-assign]
    task_id, download = q.downloading()
    download.end(RESULT)
    assert q.item(task_id).status is S.DONE


# ---- events


def test_events_alone_are_enough_to_draw_a_task_from_url_to_done(q: Harness) -> None:
    [task_id] = q.service.add([NEW_URL], Format.MP3, 192)
    fetching = QueueItem(task_id, NEW_URL, Format.MP3, 192, S.FETCHING)  # no title, no numbers
    assert q.wait(task_id, S.FETCHING) == fetching
    q.engine.answer_lookup()
    queued = replace(fetching, status=S.QUEUED, title="Song", thumb=THUMB)
    assert q.wait(task_id, S.QUEUED) == queued
    download = q.started()
    # Downloading starts at 0 % with nothing known yet.
    assert q.wait(task_id, S.DOWNLOADING) == replace(
        queued, status=S.DOWNLOADING, progress=Progress(0, 0, None, None, None)
    )
    download.send(FileSizes((1000,)))
    download.send(FileProgress(0, 1, 250, 1000, 100.0))
    assert q.flush() == [TaskProgress(task_id, Progress(250, 25, 1000, 100.0, 8))]
    download.send(PostProcessing())
    assert q.flush() == [TasksChanged((replace(queued, status=S.CONVERTING),))]
    download.end(RESULT)
    assert q.flush() == [TasksChanged((replace(queued, status=S.DONE, size_bytes=1234),))]
    assert trail(q.log, task_id) == [
        "fetching", "queued", "downloading", "25%", "converting", "done",
    ]  # fmt: skip


def test_a_failed_task_is_reported_with_its_error_and_no_numbers(q: Harness) -> None:
    task_id, download = q.downloading()
    download.send(progress(500))
    q.flush()
    download.end(EngineError(ErrorCode.NETWORK))
    [event] = q.flush()
    assert isinstance(event, TasksChanged)
    [item] = event.tasks
    assert (item.status, item.error, item.progress, item.attempt) == (
        S.FAILED,
        ErrorCode.NETWORK,
        None,
        None,
    )


def test_progress_is_sent_at_most_every_half_second_and_only_when_it_changed(q: Harness) -> None:
    task_id, download = q.downloading()
    q.flush()
    for at, done in [(0.0, 100), (0.2, 200), (0.49, 300), (0.5, 400), (0.9, 500), (1.0, 500)]:
        q.now = at
        download.send(progress(done))
    q.now = 2.0
    download.send(progress(500))  # long enough, but the same numbers as the last one sent?
    sent = q.flush()
    assert all(isinstance(event, TaskProgress) for event in sent)
    # 0.0 and 0.5 pass; 1.0 passes with 500; at 2.0 nothing has changed.
    assert trail(sent, task_id) == ["10%", "40%", "50%"]


def test_no_old_progress_arrives_after_the_status_changed(q: Harness) -> None:
    task_id, download = q.downloading()
    download.send(progress(100))
    q.now = 0.1
    download.send(progress(900))  # too soon: dropped, not kept for later
    download.send(PostProcessing())
    q.now = 5.0
    download.end(RESULT)
    assert trail(q.flush(), task_id) == ["queued", "downloading", "10%", "converting", "done"]


def test_retrying_is_reported_each_attempt_and_keeps_the_percentage(q: Harness) -> None:
    task_id, download = q.downloading()
    download.send(progress(300))
    q.flush()
    download.send(ConnectionLost(1))
    download.send(ConnectionLost(2))
    q.now = 0.1  # sooner than half a second: a status change is never held back
    download.send(progress(350))
    events = q.flush()
    assert trail(events, task_id) == ["retrying", "retrying", "downloading"]
    items = [event.tasks[0] for event in events if isinstance(event, TasksChanged)]
    assert [item.attempt for item in items] == [1, 2, None]
    assert items[0].progress == Progress(300, 30, 1000, None, None)  # no speed, no time left
    assert items[2].progress == Progress(350, 35, 1000, 100.0, 6)


def test_mp4_is_one_bar_from_0_to_100(q: Harness) -> None:
    task_id, download = q.downloading(Format.MP4)
    download.send(FileSizes((900, 100)))  # video, then audio
    for index, done in [(0, 450), (0, 900), (1, 0), (1, 50), (1, 100)]:
        q.now += 1
        download.send(FileProgress(index, 2, done, None, 10.0))
    sent = [event for event in q.flush() if isinstance(event, TaskProgress)]
    # The audio starting at 0 bytes changes nothing, so it is not sent at all.
    assert [event.progress.percent for event in sent] == [45, 90, 95, 100]
    assert [event.progress.done_bytes for event in sent] == [450, 900, 950, 1000]
    assert all(event.progress.total_bytes == 1000 for event in sent)
    download.send(PostProcessing())
    assert q.item(task_id).status is S.MERGING


def test_the_percentage_never_goes_down_within_one_download(q: Harness) -> None:
    task_id, download = q.downloading()
    for done in (500, 300, 100, 600):  # yt-dlp restarted the file
        q.now += 1
        download.send(progress(done))
    assert trail(q.flush(), task_id)[2:] == ["50%", "50%", "50%", "60%"]


# ---- the handler on the download's thread


def test_an_event_the_task_cannot_take_does_not_abort_the_download(q: Harness) -> None:
    task_id, download = q.downloading()
    download.send(PostProcessing())
    download.send(PostProcessing())  # converting -> converting is not a legal step
    download.send(progress(10))  # no progress while converting
    download.end(RESULT)  # send() would have timed out had the handler raised
    assert q.item(task_id).status is S.DONE


def test_a_slow_or_failing_listener_does_not_hold_up_the_download(make: Make) -> None:
    gate = threading.Event()
    received: list[QueueEvent] = []

    def listener(event: QueueEvent) -> None:
        assert gate.wait(WAIT * 2)
        received.append(event)
        if len(received) == 1:
            raise RuntimeError("the UI is gone")

    q = make(emit=listener)
    task_id, download = q.downloading()
    download.send(progress(500))  # returns although the listener has not taken one event
    download.end(RESULT)
    assert q.item(task_id).status is S.DONE and received == []
    gate.set()
    q.service.shutdown()  # lets the sender finish
    assert trail(received, task_id) == ["queued", "downloading", "50%", "done"]


# ---- starting and closing the app


def test_start_cleans_the_folders_the_settings_name(q: Harness) -> None:
    q.settings.dirs_to_clean = lambda: ["C:\\dl", "D:\\old"]  # type: ignore[method-assign]
    q.service.start()
    assert q.engine.cleaned == ["C:\\dl", "D:\\old"]

    def broken(dest_dir: str) -> None:
        raise OSError("drive is gone")

    q.engine.remove_stale_temp = broken  # type: ignore[method-assign]
    q.service.start()  # does not stop the app from starting


def test_shutdown_stops_every_download_and_starts_nothing_more(make: Make) -> None:
    q = make(max_concurrent=1)
    q.add(2)
    download = q.started()
    q.service.shutdown()
    assert q.engine.stopped and not download.thread.is_alive()
    assert q.engine.started.empty() and q.statuses().count(S.DOWNLOADING) == 1
    assert q.service.add(["https://example.com/late"], Format.MP3, 320) == []
    q.service.retry("anything")
    q.service.shutdown()  # twice is fine


def test_shutdown_reaches_a_download_whose_process_did_not_exist_yet(q: Harness) -> None:
    _, download = q.downloading()
    q.engine.ignore_cancel = True
    threading.Thread(target=q.service.shutdown).start()  # waits for the download to end
    while not q.engine.stopped:
        threading.Event().wait(0)  # yield; ends as soon as shutdown has called stop_all()
    q.engine.ignore_cancel = False
    download.send(FileSizes((1,)))  # the process appears: the queue cancels it now
    download.wait_ended()
