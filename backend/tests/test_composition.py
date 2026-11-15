"""build() really wires the real parts together. Nothing is downloaded, started or opened,
and the data goes to a temporary folder."""

import logging
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.composition import Backend, Event, build
from app.domain.media import Format
from app.services.settings import SettingsChanged


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def backend(
    tmp_path: Path, events: list[Event], monkeypatch: pytest.MonkeyPatch
) -> Iterator[Backend]:
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # put back after the test
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    root = logging.getLogger()
    before, level = list(root.handlers), root.level
    backend = build(events.append, tmp_path / "data", tmp_path / "local")
    yield backend
    backend.shutdown()
    for handler in set(root.handlers) - set(before):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)


def test_the_services_work_together_on_real_files(
    backend: Backend, events: list[Event], tmp_path: Path
) -> None:
    # start() is left out on purpose: it would clean the real Downloads folder.
    assert backend.history.list() == []
    backend.settings.set_download_dir(str(tmp_path))
    backend.settings.update({"max_concurrent": 1, "format": Format.MP4})
    assert [type(event) for event in events] == [SettingsChanged, SettingsChanged]
    assert (tmp_path / "data" / "settings.json").is_file()
    assert backend.queue.items() == []
    assert backend.external.open_task_folder("nothing") == "none"
    assert backend.history.redownload("nothing") is None
    assert "Media Downloader" in (tmp_path / "local" / "logs" / "app.log").read_text("utf-8")
    components = [component.name for component, _ in backend.updates._components]
    assert components == ["yt-dlp", "FFmpeg", "Deno", "Noto Sans TC", "Bricolage Grotesque"]
