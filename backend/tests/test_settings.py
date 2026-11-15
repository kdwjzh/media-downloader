"""SettingsService and the file it is kept in. Only temporary folders are touched."""

import json
from pathlib import Path

import pytest
from fake_engine import THUMB, WAIT, FakeEngine
from fakes import InMemoryHistory, MemoryFile

from app.domain.engine import OnDuplicate
from app.domain.media import Format
from app.domain.settings import Language, Settings
from app.infrastructure.storage.json_file import JsonFile
from app.services.media_info import MediaInfoService
from app.services.queue import QueueService
from app.services.settings import SettingsChanged, SettingsService

DEFAULT_DIR = "C:\\Users\\someone\\Downloads"


class Box:
    def __init__(self, data: dict[str, object] | None = None) -> None:
        self.file = MemoryFile(data)
        self.events: list[SettingsChanged] = []
        self.service = SettingsService(self.file, DEFAULT_DIR, self.events.append)


def test_defaults_are_those_of_the_contract() -> None:
    assert Box().service.get() == Settings(
        download_dir=DEFAULT_DIR,
        max_concurrent=3,
        on_duplicate=OnDuplicate.RENAME,
        format=Format.MP3,
        mp3_bitrate=320,
        mp4_height=1080,
        language=Language.SYSTEM,
    )


LEGAL = [
    ("max_concurrent", 1),
    ("max_concurrent", 2),
    ("on_duplicate", "skip"),
    ("on_duplicate", "overwrite"),
    ("format", "mp4"),
    ("mp3_bitrate", 128),
    ("mp3_bitrate", 192),
    ("mp4_height", 144),
    ("mp4_height", 2160),
    ("language", "zh-TW"),
    ("language", "en"),
]


@pytest.mark.parametrize(("name", "value"), LEGAL)
def test_a_legal_value_is_taken_saved_and_announced(name: str, value: object) -> None:
    box = Box()
    after = box.service.update({name: value})
    assert getattr(after, name) == value
    assert box.service.get() == after == box.events[-1].settings
    assert box.file.data is not None and box.file.data[name] == value


ILLEGAL = [
    ("max_concurrent", 0),
    ("max_concurrent", 4),
    ("max_concurrent", "2"),
    ("max_concurrent", 2.0),
    ("max_concurrent", True),
    ("max_concurrent", None),
    ("on_duplicate", "delete"),
    ("on_duplicate", 1),
    ("format", "flac"),
    ("format", None),
    ("mp3_bitrate", 256),
    ("mp3_bitrate", 1080),
    ("mp4_height", 320),
    ("mp4_height", "1080"),
    ("language", "fr"),
    ("language", ""),
    ("download_dir", "C:\\elsewhere"),  # only the folder dialog changes it
    ("downloadDir", "C:\\elsewhere"),
    ("no_such_setting", 1),
]


@pytest.mark.parametrize(("name", "value"), ILLEGAL)
def test_an_illegal_value_changes_nothing(name: str, value: object) -> None:
    box = Box()
    before = box.service.get()
    with pytest.raises(ValueError):
        box.service.update({"max_concurrent": 1, name: value})  # the legal one is not taken
    assert box.service.get() == before
    assert box.events == [] and box.file.data is None


def test_settings_are_still_there_after_a_restart(tmp_path: Path) -> None:
    # C5 of the old version: settings were never saved.
    changes = {"max_concurrent": 2, "on_duplicate": "skip", "format": "mp4", "mp4_height": 720,
               "mp3_bitrate": 192, "language": "en"}  # fmt: skip
    first = SettingsService(JsonFile(tmp_path / "settings.json"), DEFAULT_DIR, lambda _: None)
    first.update(changes)
    first.set_download_dir(str(tmp_path))
    second = SettingsService(JsonFile(tmp_path / "settings.json"), DEFAULT_DIR, lambda _: None)
    assert second.get() == first.get() != Settings(DEFAULT_DIR)
    assert second.get().download_dir == str(tmp_path)


@pytest.mark.parametrize("content", [b"{ this is not JSON", b"[1, 2]", b"\xff\xfe\x00", b""])
def test_a_broken_file_is_set_aside_and_the_defaults_are_used(
    tmp_path: Path, content: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "settings.json"
    path.write_bytes(content)
    service = SettingsService(JsonFile(path), DEFAULT_DIR, lambda _: None)
    assert service.get() == Settings(DEFAULT_DIR)
    [kept] = tmp_path.glob("settings.broken-*.json")
    assert kept.read_bytes() == content and not path.exists()
    assert "settings.json is unusable" in caplog.text
    service.update({"max_concurrent": 1})  # and it works from here on
    assert json.loads(path.read_text("utf-8"))["max_concurrent"] == 1


def test_one_bad_value_in_the_file_only_loses_that_value(caplog: pytest.LogCaptureFixture) -> None:
    box = Box({"max_concurrent": 9, "format": "mp4", "language": "en", "download_dir": "music",
               "from_a_newer_version": 1})  # fmt: skip
    assert box.service.get() == Settings(DEFAULT_DIR, format=Format.MP4, language=Language.EN)
    assert "max_concurrent" in caplog.text


def test_a_save_that_fails_halfway_leaves_the_old_file(tmp_path: Path) -> None:
    file = JsonFile(tmp_path / "settings.json")
    file.save({"max_concurrent": 2})
    with pytest.raises(TypeError):
        file.save({"max_concurrent": 3, "later": object()})  # json gives up in the middle
    assert file.load() == {"max_concurrent": 2}


def test_a_change_that_cannot_be_saved_still_holds(caplog: pytest.LogCaptureFixture) -> None:
    box = Box()
    box.file.fail = True
    assert box.service.update({"max_concurrent": 1}).max_concurrent == 1
    assert box.service.max_concurrent == 1 and len(box.events) == 1
    assert "could not save the settings" in caplog.text


def test_a_failing_listener_does_not_undo_the_change(tmp_path: Path) -> None:
    def listener(event: SettingsChanged) -> None:
        raise RuntimeError("the window is gone")

    service = SettingsService(MemoryFile(), DEFAULT_DIR, listener)
    assert service.update({"max_concurrent": 1}).max_concurrent == 1


def test_remember_format_keeps_the_other_formats_quality() -> None:
    box = Box()
    box.service.remember_format(Format.MP4, 720)
    assert box.service.get() == Settings(DEFAULT_DIR, format=Format.MP4, mp4_height=720)
    box.service.remember_format(Format.MP3, 128)
    assert box.service.get() == Settings(DEFAULT_DIR, mp3_bitrate=128, mp4_height=720)
    assert len(box.events) == 2
    box.service.remember_format(Format.MP3, 128)
    assert len(box.events) == 2  # nothing changed: nothing announced


def test_the_download_folder_must_be_an_existing_absolute_folder(tmp_path: Path) -> None:
    box = Box()
    file = tmp_path / "a file.txt"
    file.write_text("x")
    for bad in ("music", "", str(tmp_path / "missing"), str(file)):
        with pytest.raises(ValueError):
            box.service.set_download_dir(bad)
    assert box.service.download_dir == DEFAULT_DIR and box.events == []
    folder = tmp_path / "音樂, 2026 (new)"
    folder.mkdir()
    assert box.service.set_download_dir(str(folder)).download_dir == str(folder)
    assert box.events[-1].settings.download_dir == str(folder)
    assert list(folder.iterdir()) == []  # the write test left nothing behind


def test_folders_changed_away_from_are_cleaned_once(tmp_path: Path) -> None:
    a, b, c = (str(tmp_path / name) for name in "abc")
    for folder in (a, b, c):
        Path(folder).mkdir()
    file = MemoryFile()
    service = SettingsService(file, a, lambda _: None)
    assert service.dirs_to_clean() == [a]
    service.set_download_dir(b)
    service.set_download_dir(c)
    # Not cleaned yet when the app is closed: the next run still knows them.
    service = SettingsService(file, a, lambda _: None)
    assert service.dirs_to_clean() == [c, a, b]
    assert service.dirs_to_clean() == [c]
    assert SettingsService(file, a, lambda _: None).dirs_to_clean() == [c]


def test_going_back_to_an_old_folder_does_not_list_it_twice(tmp_path: Path) -> None:
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    Path(a).mkdir()
    Path(b).mkdir()
    service = SettingsService(MemoryFile(), a, lambda _: None)
    service.set_download_dir(b)
    service.set_download_dir(a)
    assert service.dirs_to_clean() == [a, b]


def test_raising_the_limit_reaches_the_queue_without_a_deadlock() -> None:
    # Wired as app/composition.py does it: the queue is told inside the settings' write
    # lock, and reads the settings inside its own.
    engine = FakeEngine()
    media = MediaInfoService(engine)

    def changed(event: SettingsChanged) -> None:
        queue.settings_changed()

    settings = SettingsService(MemoryFile({"max_concurrent": 1}), DEFAULT_DIR, changed)
    queue = QueueService(engine, media, settings, InMemoryHistory(), lambda _: None)
    try:
        urls = [f"https://example.com/v/{n}" for n in range(3)]
        for url in urls:
            media.remember(url, "Title", THUMB)
        queue.add(urls, Format.MP4, 720)  # remembers the format: settings -> queue
        assert settings.get().mp4_height == 720
        engine.started.get(timeout=WAIT)
        assert engine.started.empty()
        settings.update({"max_concurrent": 3})
        engine.started.get(timeout=WAIT)
        engine.started.get(timeout=WAIT)
    finally:
        queue.shutdown()
