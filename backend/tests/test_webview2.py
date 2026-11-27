"""Asking WebView2's own loader whether the runtime can start (ADR 0023)."""

from pathlib import Path

import pytest
import webview

from app.infrastructure import webview2

LOADER = Path(webview.__file__).parent / "lib/runtimes/win-x64/native/WebView2Loader.dll"


def test_a_runtime_folder_without_the_runtime_is_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The loader honours this variable, so an empty folder stands in for the Windows Sandbox
    # whose registry names a version that is not on disk: both fail with 0x80070002.
    monkeypatch.setenv("WEBVIEW2_BROWSER_EXECUTABLE_FOLDER", str(tmp_path))
    assert webview2.problem(LOADER) == 0x80070002


def test_without_the_loader_it_cannot_tell_and_does_not_stop_the_app(tmp_path: Path) -> None:
    assert webview2.problem(tmp_path / "WebView2Loader.dll") is None
