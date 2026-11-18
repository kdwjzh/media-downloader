"""Where the external programs are looked for, and noticing when they are gone (ADR 0018)."""

import sys
from pathlib import Path

import pytest

from app.infrastructure import binaries
from app.infrastructure.storage import paths

REPO = Path(__file__).resolve().parents[2]


def test_development_uses_the_repository_bin_folder() -> None:
    assert not getattr(sys, "frozen", False)
    assert binaries.bin_dir() == REPO / "bin"
    assert binaries.yt_dlp() == REPO / "bin" / "yt-dlp.exe"


def test_packaged_uses_the_shared_folder_under_local_app_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths, "local_dir", lambda: tmp_path / "media-downloader")
    assert binaries.bin_dir() == tmp_path / "media-downloader" / "bin"
    assert binaries.ffmpeg() == tmp_path / "media-downloader" / "bin" / "ffmpeg.exe"
    assert binaries.deno() == tmp_path / "media-downloader" / "bin" / "deno.exe"


def test_missing_lists_the_programs_that_are_not_there(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(binaries, "bin_dir", lambda: tmp_path)
    assert binaries.missing() == ["yt-dlp.exe", "ffmpeg.exe", "deno.exe"]
    (tmp_path / "ffmpeg.exe").write_bytes(b"")
    (tmp_path / "deno.exe").write_bytes(b"")
    assert binaries.missing() == ["yt-dlp.exe"]
    (tmp_path / "yt-dlp.exe").write_bytes(b"")
    assert binaries.missing() == []


def test_a_folder_with_the_program_name_does_not_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(binaries, "bin_dir", lambda: tmp_path)
    for name in ("yt-dlp.exe", "ffmpeg.exe", "deno.exe"):
        (tmp_path / name).mkdir()
    assert binaries.missing() == ["yt-dlp.exe", "ffmpeg.exe", "deno.exe"]
