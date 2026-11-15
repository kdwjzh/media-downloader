"""ExternalService with a fake shell: nothing is really opened."""

from pathlib import Path

import pytest
from fakes import FakeShell

from app.services.external import LINKS, ExternalService, Opened

# Everything File Explorer's command line would trip over.
NAME = "歌手 - 歌名, Pt. 2 (Live) & more; 100% =x.mp3"


class Box:
    def __init__(self, folder: Path) -> None:
        self.shell = FakeShell()
        self.tasks: dict[str, str] = {}
        self.history: dict[str, str] = {}
        self.log_file = folder / "logs" / "app.log"
        self.service = ExternalService(
            self.shell, self.tasks.get, self.history.get, self.log_file
        )


@pytest.fixture
def box(tmp_path: Path) -> Box:
    return Box(tmp_path)


def test_a_file_that_is_there_is_selected(box: Box, tmp_path: Path) -> None:
    file = tmp_path / NAME
    file.write_bytes(b"x")
    box.tasks["t1"] = box.history["h1"] = str(file)
    assert box.service.open_task_folder("t1") is Opened.FILE
    assert box.service.open_history_folder("h1") is Opened.FILE
    assert box.shell.calls == [("select_file", str(file))] * 2  # the path, whole and unchanged


def test_when_the_file_is_gone_its_folder_is_opened(box: Box, tmp_path: Path) -> None:
    box.tasks["t1"] = box.history["h1"] = str(tmp_path / NAME)
    assert box.service.open_task_folder("t1") is Opened.FOLDER
    assert box.service.open_history_folder("h1") is Opened.FOLDER
    assert box.shell.calls == [("open_path", str(tmp_path))] * 2


def test_when_the_folder_is_gone_too_nothing_is_opened(box: Box, tmp_path: Path) -> None:
    box.tasks["t1"] = box.history["h1"] = str(tmp_path / "moved away" / NAME)
    assert box.service.open_task_folder("t1") is Opened.NONE
    assert box.service.open_history_folder("h1") is Opened.NONE
    # A task that is not done, or an id nobody knows, has no path at all.
    assert box.service.open_task_folder("unknown") is Opened.NONE
    assert box.service.open_history_folder("unknown") is Opened.NONE
    assert box.shell.calls == []


def test_a_folder_is_never_taken_for_the_file(box: Box, tmp_path: Path) -> None:
    (tmp_path / "Song.mp3").mkdir()
    box.tasks["t1"] = str(tmp_path / "Song.mp3")
    assert box.service.open_task_folder("t1") is Opened.FOLDER
    assert box.shell.calls == [("open_path", str(tmp_path))]


def test_when_windows_refuses_to_select_the_folder_is_opened_instead(
    box: Box, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    file = tmp_path / NAME
    file.write_bytes(b"x")
    box.tasks["t1"] = str(file)
    box.shell.refuse = {"select_file"}
    assert box.service.open_task_folder("t1") is Opened.FOLDER
    box.shell.refuse = {"select_file", "open_path"}
    assert box.service.open_task_folder("t1") is Opened.NONE
    assert NAME not in caplog.text  # titles and paths stay out of the log


def test_the_log_file_is_created_if_needed_then_opened(box: Box) -> None:
    box.service.open_log_file()
    assert box.log_file.read_bytes() == b""
    box.log_file.write_text("a line")
    box.service.open_log_file()
    assert box.log_file.read_text() == "a line"  # an existing one is not emptied
    box.service.open_log_folder()
    assert box.shell.calls == [
        ("open_path", str(box.log_file)),
        ("open_path", str(box.log_file)),
        ("open_path", str(box.log_file.parent)),
    ]


def test_only_the_two_named_pages_can_be_opened(box: Box) -> None:
    box.service.open_link("releasePage")
    box.service.open_link("sourceCode")
    assert box.shell.calls == [
        ("open_url", "https://github.com/kdwjzh/media-downloader/releases/latest"),
        ("open_url", "https://github.com/kdwjzh/media-downloader"),
    ]
    assert set(LINKS) == {"releasePage", "sourceCode"}
    for bad in ("https://example.com", "file:///C:/Windows/System32/calc.exe", "", "releasepage"):
        with pytest.raises(ValueError):
            box.service.open_link(bad)
    assert len(box.shell.calls) == 2
