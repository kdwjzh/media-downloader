"""HistoryService on a real SQLite file in a temporary folder. No network: thumbnails come
from a fake."""

import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import JPEG, FakeThumbnails

from app.domain.history import HistoryRecord, data_url
from app.domain.media import Format
from app.infrastructure.storage.history_db import HistoryDb
from app.services.history import HistoryAdded, HistoryService
from app.services.ports import FinishedDownload

URL = "https://www.youtube.com/watch?v=abc"
THUMB = "https://i.ytimg.com/vi/abc/maxresdefault.jpg"


def download(title: str = "Song", format: Format = Format.MP3, quality: int = 320,
             thumb: str | None = THUMB) -> FinishedDownload:  # fmt: skip
    return FinishedDownload(URL, title, format, quality, 1234, f"C:\\dl\\{title}.{format}", thumb)


class Box:
    def __init__(self, folder: Path) -> None:
        self.path = folder / "history.db"
        self.thumbnails = FakeThumbnails()
        self.events: list[HistoryAdded] = []
        self.requeued: list[HistoryRecord] = []
        self.now = datetime(2026, 11, 13, 6, 20, 0, tzinfo=UTC)
        self.service = self.open()

    def open(self) -> HistoryService:
        """A service on the same file, as after a restart."""
        return HistoryService(
            HistoryDb(self.path), self.thumbnails, self.events.append, self.requeue,
            lambda: self.now,
        )  # fmt: skip

    def requeue(self, record: HistoryRecord) -> str:
        self.requeued.append(record)
        return "new-task"


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def test_a_finished_download_is_recorded_with_a_small_thumbnail(box: Box) -> None:
    box.service.record(download())
    [entry] = box.service.list()
    assert (entry.url, entry.title, entry.format, entry.quality, entry.size_bytes) == (
        URL, "Song", Format.MP3, 320, 1234,
    )  # fmt: skip
    assert entry.finished_at == "2026-11-13T06:20:00Z"
    assert entry.thumb == data_url(JPEG) and entry.thumb.startswith("data:image/jpeg;base64,")
    assert box.thumbnails.asked == [THUMB]
    assert box.events == [HistoryAdded(entry)]
    assert box.open().list() == [entry]  # still there after a restart


def test_without_a_thumbnail_the_download_is_recorded_all_the_same(box: Box) -> None:
    box.thumbnails.image = None  # could not be fetched
    box.service.record(download("A"))
    box.service.record(download("B", thumb=None))  # the source had none
    assert [(e.title, e.thumb) for e in box.service.list()] == [("B", None), ("A", None)]
    assert box.thumbnails.asked == [THUMB]
    assert [event.entry.title for event in box.events] == ["A", "B"]


def test_the_newest_is_listed_first_even_within_one_second(box: Box) -> None:
    for title in "ABC":
        box.service.record(download(title))
    assert [entry.title for entry in box.service.list()] == ["C", "B", "A"]


def test_the_same_video_twice_is_two_entries_and_deleting_one_keeps_the_other(box: Box) -> None:
    # C10 of the old version: deleting one entry of a video deleted the wrong one.
    box.service.record(download(format=Format.MP3, quality=320))
    box.service.record(download(format=Format.MP4, quality=1080))
    mp4, mp3 = box.service.list()
    assert mp4.id != mp3.id and (mp4.url, mp4.title) == (mp3.url, mp3.title)
    box.service.delete(mp3.id)
    assert box.service.list() == [mp4]
    assert box.service.file_path(mp3.id) is None
    box.service.delete(mp3.id)  # already gone: nothing happens
    box.service.delete("no such id")
    assert box.service.list() == [mp4]


def test_delete_and_clear_never_touch_the_downloaded_files(tmp_path: Path) -> None:
    box = Box(tmp_path)
    files = [tmp_path / "one.mp3", tmp_path / "two.mp3"]
    for file in files:
        file.write_bytes(b"music")
        box.service.record(FinishedDownload(URL, file.stem, Format.MP3, 320, 5, str(file), THUMB))
    box.service.delete(box.service.list()[0].id)
    box.service.clear()
    assert box.service.list() == []
    assert all(file.read_bytes() == b"music" for file in files)
    assert box.path.stat().st_size < 50_000  # nothing of the thumbnails is left to pile up


def test_download_again_requeues_with_the_original_format_and_thumbnail_address(box: Box) -> None:
    box.service.record(download(format=Format.MP4, quality=720))
    [entry] = box.service.list()
    assert box.service.redownload(entry.id) == "new-task"
    [record] = box.requeued
    assert (record.entry.url, record.entry.title, record.entry.format, record.entry.quality) == (
        URL, "Song", Format.MP4, 720,
    )  # fmt: skip
    assert record.thumb_url == THUMB  # not the data URL: the queue shows the real picture
    assert box.service.redownload("no such id") is None
    assert box.service.list() == [entry]  # the old entry is not touched


def test_the_file_path_stays_in_the_back_end(box: Box) -> None:
    box.service.record(download())
    [entry] = box.service.list()
    assert box.service.file_path(entry.id) == "C:\\dl\\Song.mp3"
    assert not hasattr(entry, "file_path") and not hasattr(box.events[0].entry, "file_path")


@pytest.mark.parametrize(
    "content", [b"this is not a database, " * 100, b"SQLite format 3\x00" + b"x" * 5000]
)
def test_a_broken_database_is_set_aside_and_history_starts_empty(
    box: Box, content: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    box.path.write_bytes(content)
    assert box.service.list() == []
    [kept] = box.path.parent.glob("history.broken-*.db")
    assert kept.read_bytes() == content
    assert "history database is unusable" in caplog.text
    box.service.record(download())
    assert len(box.service.list()) == 1


def test_a_title_cannot_be_read_as_sql(box: Box) -> None:
    title = "Robert'); DROP TABLE history;-- \"x\""
    box.service.record(download(title))
    box.service.record(download("other"))
    assert [entry.title for entry in box.service.list()] == ["other", title]
    box.service.delete("' OR '1'='1")
    assert len(box.service.list()) == 2


def test_downloads_finishing_at_the_same_time_are_all_recorded(box: Box) -> None:
    threads, per_thread = 8, 10
    ready = threading.Barrier(threads)
    errors: list[BaseException] = []

    def work(n: int) -> None:
        try:
            ready.wait(5)
            for i in range(per_thread):
                box.service.record(download(f"{n}-{i}"))
        except BaseException as error:
            errors.append(error)

    workers = [threading.Thread(target=work, args=(n,)) for n in range(threads)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(30)
    assert errors == []
    entries = box.service.list()
    assert len(entries) == len({entry.id for entry in entries}) == threads * per_thread
    assert {entry.title for entry in entries} == {
        f"{n}-{i}" for n in range(threads) for i in range(per_thread)
    }
    assert len(box.events) == threads * per_thread
