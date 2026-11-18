"""Starting the packaged app when an external program is gone (ADR 0018)."""

import sys
from pathlib import Path

import pytest

from app import main
from app.infrastructure import binaries


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    index = tmp_path / "index.html"
    index.write_text("")
    shown: list[str] = []
    monkeypatch.setattr(main, "DIST_INDEX", index)
    monkeypatch.setattr(sys, "argv", ["app"])
    monkeypatch.setattr(main, "show_error", shown.append)

    def build(*_: object) -> None:
        raise AssertionError("must stop before building the backend")

    monkeypatch.setattr(main, "build", build)
    return shown


def test_packaged_app_says_to_reinstall_and_stops(
    monkeypatch: pytest.MonkeyPatch, started: list[str]
) -> None:
    monkeypatch.setattr(main, "FROZEN", True)
    monkeypatch.setattr(binaries, "missing", lambda: ["yt-dlp.exe", "deno.exe"])
    with pytest.raises(SystemExit) as stopped:
        main.main()
    assert stopped.value.code == 1
    [message] = started
    assert "yt-dlp.exe、deno.exe" in message
    assert "yt-dlp.exe, deno.exe" in message
    assert "重新安裝" in message and "Install Media Downloader again" in message


def test_development_points_to_the_fetch_script(
    monkeypatch: pytest.MonkeyPatch, started: list[str]
) -> None:
    monkeypatch.setattr(main, "FROZEN", False)
    monkeypatch.setattr(binaries, "missing", lambda: ["ffmpeg.exe"])
    with pytest.raises(SystemExit, match="fetch_binaries"):
        main.main()
    assert started == []
