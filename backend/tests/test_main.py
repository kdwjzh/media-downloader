"""Starting the packaged app when an external program is gone (ADR 0018)."""

import sys
from pathlib import Path

import pytest
import webview

from app import main
from app.infrastructure import binaries, webview2


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


class _Backend:
    started = False

    def start(self) -> None:
        self.started = True


@pytest.fixture
def no_webview2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    """A white, empty window was all the user got (1.0.1, Windows Sandbox)."""
    index = tmp_path / "index.html"
    index.write_text("")
    seen: dict[str, object] = {"opened": []}
    backend = _Backend()
    seen["backend"] = backend
    monkeypatch.setattr(main, "DIST_INDEX", index)
    monkeypatch.setattr(sys, "argv", ["app"])
    monkeypatch.setattr(main, "FROZEN", False)
    monkeypatch.setattr(binaries, "missing", lambda: [])
    monkeypatch.setattr(main, "build", lambda *_: backend)
    monkeypatch.setattr(webview2, "problem", lambda _: 0x80070002)

    class Shell:
        def open_url(self, url: str) -> None:
            seen["opened"].append(url)  # type: ignore[attr-defined]

    monkeypatch.setattr(main, "WindowsShell", Shell)

    def no_window(*_: object, **__: object) -> None:
        raise AssertionError("must stop before opening the window")

    monkeypatch.setattr(webview, "create_window", no_window)
    return seen


@pytest.mark.parametrize("open_page", [True, False])
def test_an_unusable_webview2_is_explained_instead_of_a_white_window(
    monkeypatch: pytest.MonkeyPatch,
    no_webview2: dict[str, object],
    caplog: pytest.LogCaptureFixture,
    open_page: bool,
) -> None:
    asked: list[str] = []

    def ask(message: str) -> bool:
        asked.append(message)
        return open_page

    monkeypatch.setattr(main, "ask", ask)
    with pytest.raises(SystemExit) as stopped:
        main.main()
    assert stopped.value.code == 1
    [message] = asked
    assert "WebView2" in message and "Evergreen Standalone Installer" in message
    assert "找不到或無法使用" in message and "missing or cannot be used" in message
    assert main.WEBVIEW2_URL in message and "0x80070002" in message
    assert no_webview2["opened"] == ([main.WEBVIEW2_URL] if open_page else [])
    assert not no_webview2["backend"].started  # type: ignore[attr-defined]
    assert "0x80070002" in caplog.text  # the original error stays in the log
