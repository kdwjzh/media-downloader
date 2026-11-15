"""Task folders, final names, the duplicate rules, binaries, and the job that holds a process
tree. Real files and real (Python) processes; no network, no yt-dlp."""

import ctypes
import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.engine import OnDuplicate
from app.domain.media import Format
from app.infrastructure import binaries
from app.infrastructure.engines.ytdlp import files
from app.infrastructure.process import JobProcess, run


def test_task_dir_is_empty_hidden_and_inside_the_download_folder(tmp_path: Path) -> None:
    stale = tmp_path / ".md-tmp-a1" / "half.part"
    stale.parent.mkdir()
    stale.write_text("x")
    path = files.create_task_dir(str(tmp_path), "a1")
    assert path == tmp_path / ".md-tmp-a1" and list(path.iterdir()) == []
    assert ctypes.windll.kernel32.GetFileAttributesW(str(path)) & 0x2


@pytest.mark.parametrize("task_id", ["", "..", "a/b", "a\\b", "..\\x", "a b", "C:x"])
def test_task_id_cannot_point_elsewhere(tmp_path: Path, task_id: str) -> None:
    with pytest.raises(ValueError):
        files.create_task_dir(str(tmp_path), task_id)


def test_remove_stale_deletes_only_our_folders(tmp_path: Path) -> None:
    (tmp_path / ".md-tmp-old" / "sub").mkdir(parents=True)
    (tmp_path / ".md-tmp-old" / "sub" / "x.part").write_text("x")
    (tmp_path / "My Music").mkdir()
    (tmp_path / "song.mp3").write_text("x")
    (tmp_path / ".md-tmp-file").write_text("a file, not a folder: left alone")
    files.remove_stale(str(tmp_path))
    assert sorted(p.name for p in tmp_path.iterdir()) == [".md-tmp-file", "My Music", "song.mp3"]
    files.remove_stale(str(tmp_path / "does not exist"))


@pytest.mark.parametrize(
    ("printed", "format", "expected"),
    [
        ("C:\\dl\\.md-tmp-1\\歌名.webm", Format.MP3, "歌名.mp3"),
        ("C:\\dl\\.md-tmp-1\\歌名.mp4", Format.MP4, "歌名.mp4"),
        ("C:\\dl\\.md-tmp-1\\Vol. 2 - feat. X.m4a", Format.MP3, "Vol. 2 - feat. X.mp3"),
        ("C:\\dl\\.md-tmp-1\\trailing dot..webm", Format.MP3, "trailing dot..mp3"),
        ("C:\\dl\\.md-tmp-1\\CON.webm", Format.MP3, "_CON.mp3"),
        ("C:\\dl\\.md-tmp-1\\com1.live.mp4", Format.MP4, "_com1.live.mp4"),
        ("C:\\dl\\.md-tmp-1\\CONCERT.mp4", Format.MP4, "CONCERT.mp4"),
    ],
)
def test_final_name(printed: str, format: Format, expected: str) -> None:
    assert files.final_name(printed, format) == expected


@pytest.mark.parametrize("name", ["..\\x.mp3", "sub\\x.mp3", "sub/x.mp3", "C:\\other\\x.mp3", ".."])
def test_target_must_stay_in_the_download_folder(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError):
        files.target(str(tmp_path), name)


def finished(tmp_path: Path, text: str = "new") -> Path:
    source = tmp_path / ".md-tmp-1" / "song.mp3"
    source.parent.mkdir(exist_ok=True)
    source.write_text(text)
    return source


@pytest.mark.parametrize("rule", list(OnDuplicate))
def test_without_a_duplicate_the_file_is_simply_moved(tmp_path: Path, rule: OnDuplicate) -> None:
    source = finished(tmp_path)
    assert files.place(source, str(tmp_path), "song.mp3", rule) == (tmp_path / "song.mp3", False)
    assert (tmp_path / "song.mp3").read_text() == "new" and not source.exists()


def test_rename_takes_the_next_free_number(tmp_path: Path) -> None:
    (tmp_path / "song.mp3").write_text("old")
    assert files.place(finished(tmp_path), str(tmp_path), "song.mp3", OnDuplicate.RENAME) == (
        tmp_path / "song (1).mp3",
        False,
    )
    assert files.place(finished(tmp_path), str(tmp_path), "song.mp3", OnDuplicate.RENAME) == (
        tmp_path / "song (2).mp3",
        False,
    )
    assert (tmp_path / "song.mp3").read_text() == "old"


def test_overwrite_replaces_the_old_file(tmp_path: Path) -> None:
    (tmp_path / "song.mp3").write_text("old")
    files.place(finished(tmp_path), str(tmp_path), "song.mp3", OnDuplicate.OVERWRITE)
    assert (tmp_path / "song.mp3").read_text() == "new"
    assert [p.name for p in tmp_path.glob("song*")] == ["song.mp3"]


def test_skip_leaves_the_old_file_and_says_so(tmp_path: Path) -> None:
    (tmp_path / "song.mp3").write_text("old")
    source = finished(tmp_path)
    assert files.place(source, str(tmp_path), "song.mp3", OnDuplicate.SKIP) == (
        tmp_path / "song.mp3",
        True,
    )
    assert (tmp_path / "song.mp3").read_text() == "old" and source.exists()


def test_binaries_in_development_are_in_the_repository_bin() -> None:
    repo = Path(__file__).resolve().parents[2]
    assert binaries.yt_dlp() == repo / "bin" / "yt-dlp.exe"
    assert binaries.ffmpeg() == repo / "bin" / "ffmpeg.exe"
    assert binaries.deno() == repo / "bin" / "deno.exe"


def test_binaries_when_packaged_are_next_to_the_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Media Downloader.exe"))
    assert binaries.yt_dlp() == tmp_path.resolve() / "bin" / "yt-dlp.exe"
    assert binaries.deno().is_absolute()


def test_run_returns_code_and_both_outputs_as_utf8() -> None:
    script = (
        "import sys; sys.stdout.buffer.write('歌'.encode());"
        "sys.stderr.write('warn'); sys.exit(3)"
    )
    assert run([sys.executable, "-c", script], timeout=30) == (3, "歌", "warn")


def test_run_gives_up_after_the_timeout() -> None:
    with pytest.raises(TimeoutError):
        run([sys.executable, "-c", "import time; time.sleep(60)"], timeout=1)


# A parent that starts a child and prints the child's pid: the shape of yt-dlp.exe.
TREE = (
    "import subprocess, sys, time;"
    "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']);"
    "print(c.pid, flush=True); time.sleep(60)"
)


def exited(pid: int) -> bool:
    synchronize = 0x100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return True
    try:
        return bool(ctypes.windll.kernel32.WaitForSingleObject(handle, 5000) == 0)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


@pytest.mark.parametrize("how", ["kill", "close"])
def test_the_whole_tree_ends_on_kill_and_when_the_job_handle_goes_away(how: str) -> None:
    process = JobProcess([sys.executable, "-c", TREE])
    assert process.popen.stdout
    child = int(process.popen.stdout.readline())
    assert not exited(process.popen.pid) or pytest.fail("ended too early")
    # close() alone is what happens when the app dies: Windows closes its handles.
    process.kill() if how == "kill" else process.close()
    assert process.popen.wait(timeout=5) is not None
    assert exited(child)
    process.kill()  # harmless afterwards
    process.close()


def test_no_console_window_flag_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, int] = {}
    real = subprocess.Popen

    def spy(*args: object, **kwargs: object) -> "subprocess.Popen[str]":
        seen["flags"] = int(kwargs["creationflags"])  # type: ignore[call-overload]
        return real(*args, **kwargs)  # type: ignore[call-overload,no-any-return]

    monkeypatch.setattr(subprocess, "Popen", spy)
    run([sys.executable, "-c", "pass"], timeout=30)
    assert seen["flags"] & subprocess.CREATE_NO_WINDOW
