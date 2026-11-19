"""YtDlpEngine.download around the process: a stand-in prints what yt-dlp would print.
Real files; no network, no yt-dlp."""

import errno
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from app.domain.engine import (
    DownloadCancelled,
    DownloadRequest,
    EngineError,
    FileSizes,
    OnDuplicate,
)
from app.domain.errors import ErrorCode
from app.domain.media import Format
from app.infrastructure import binaries
from app.infrastructure.engines.ytdlp import args, files
from app.infrastructure.engines.ytdlp import engine as engine_module
from app.infrastructure.engines.ytdlp.engine import YtDlpEngine

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
# Recorded 2026-11-16 with five downloads starting together: YouTube refused this one
# before a single byte of the file had moved. The same download works on the next try.
FORBIDDEN = (FIXTURES / "download" / "http_403.txt").read_text(encoding="utf-8").splitlines(True)
PRIVATE = (FIXTURES / "errors" / "private.txt").read_text(encoding="utf-8").splitlines(True)
# Not a recording: the recorded 403 with one progress line put before the error. A 403 in
# the middle of a file has never been caught on record.
FORBIDDEN_MIDWAY = [
    *FORBIDDEN[:-1],
    f'{args.DL}{{"format_id": "251"}} {{"status": "downloading", "downloaded_bytes": 1024}}\n',
    FORBIDDEN[-1],
]


class FakeProcess:
    """Stands in for JobProcess: "downloads" song.mp3 into the task folder."""

    def __init__(self, command: list[str], merge_stderr: bool = False) -> None:
        task_dir = Path(command[command.index("-P") + 1])
        (task_dir / "song.mp3").write_text("new")
        self.popen = self
        self.stdout = iter(
            [f"{args.NAME}{task_dir / 'song.webm'}\n", f"{args.FILE}{task_dir / 'song.mp3'}\n"]
        )

    def wait(self) -> int:
        return 0

    def kill(self) -> None: ...

    def close(self) -> None: ...


@pytest.fixture(autouse=True)
def no_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_module, "JobProcess", FakeProcess)


def download(dest: Path, rule: OnDuplicate = OnDuplicate.RENAME) -> str:
    request = DownloadRequest("t1", URL, Format.MP3, 128, str(dest), rule)
    return YtDlpEngine().download(request, lambda event: None).file_path


def fails_as_unknown(dest: Path, rule: OnDuplicate = OnDuplicate.RENAME) -> str:
    with pytest.raises(EngineError) as error:
        download(dest, rule)
    assert error.value.code is ErrorCode.UNKNOWN
    assert not (dest / ".md-tmp-t1").exists()
    return error.value.detail


def test_the_finished_file_is_moved_out_and_the_task_folder_removed(tmp_path: Path) -> None:
    assert download(tmp_path) == str(tmp_path / "song.mp3")
    assert [p.name for p in tmp_path.iterdir()] == ["song.mp3"]


def test_download_folder_that_cannot_exist_is_an_engine_error(tmp_path: Path) -> None:
    (tmp_path / "a file").write_text("x")
    assert "a file" in fails_as_unknown(tmp_path / "a file" / "downloads")


def test_download_folder_that_cannot_be_written_is_an_engine_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(dest_dir: str, task_id: str) -> Path:
        raise PermissionError(errno.EACCES, "Access is denied", dest_dir)

    monkeypatch.setattr(files, "create_task_dir", denied)
    assert "Access is denied" in fails_as_unknown(tmp_path)


def test_overwriting_a_file_another_program_has_open_is_an_engine_error(tmp_path: Path) -> None:
    old = tmp_path / "song.mp3"
    old.write_text("old")
    with old.open():  # Windows refuses to replace a file that is open
        assert "song.mp3" in fails_as_unknown(tmp_path, OnDuplicate.OVERWRITE)
    assert old.read_text() == "old"


def test_full_disk_is_an_engine_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def full(*_: object) -> tuple[Path, bool]:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(files, "place", full)
    assert "No space left on device" in fails_as_unknown(tmp_path)


class Scripted:
    """Stands in for JobProcess; every new process plays the next script. A script is the
    lines yt-dlp prints, or None for a download that works."""

    def __init__(self, command: list[str], merge_stderr: bool = False) -> None:
        self.task_dir = Path(command[command.index("-P") + 1])
        self.found = [p.name for p in self.task_dir.iterdir()]  # must be empty every time
        self.script = SCRIPTS.pop(0)
        self.killed = self.closed = False
        self.popen = self
        self.stdout = self.lines()
        (self.task_dir / ("song.mp3" if self.script is None else "cover.jpg")).write_text("new")
        STARTED.append(self)
        self.number = len(STARTED)

    def lines(self) -> Iterator[str]:
        script = self.script or [
            f"{args.NAME}{self.task_dir / 'song.webm'}",
            f"{args.FILE}{self.task_dir / 'song.mp3'}",
        ]
        for index, line in enumerate(script):
            HOOKS.get((self.number, "line", index), lambda: None)()
            if self.killed:
                return
            yield line

    def wait(self) -> int:
        return 0 if self.script is None and not self.killed else 1

    def kill(self) -> None:
        self.killed = True

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            HOOKS.get((self.number, "close"), lambda: None)()


SCRIPTS: list[list[str] | None] = []
STARTED: list[Scripted] = []
HOOKS: dict[tuple[object, ...], Callable[[], None]] = {}


def scripted(
    monkeypatch: pytest.MonkeyPatch, *scripts: list[str] | None
) -> tuple[YtDlpEngine, DownloadRequest]:
    SCRIPTS[:], STARTED[:] = scripts, []
    HOOKS.clear()
    monkeypatch.setattr(engine_module, "JobProcess", Scripted)
    return YtDlpEngine(), DownloadRequest("t1", URL, Format.MP3, 128, "")


def run(engine: YtDlpEngine, request: DownloadRequest, dest: Path) -> str:
    return engine.download(replace(request, dest_dir=str(dest)), lambda event: None).file_path


def test_a_403_before_any_data_is_tried_once_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN, None)
    assert run(engine, request, tmp_path) == str(tmp_path / "song.mp3")
    assert len(STARTED) == 2 and SCRIPTS == []


def test_the_second_try_starts_in_an_empty_task_folder_and_leaves_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN, None)
    run(engine, request, tmp_path)
    assert [p.found for p in STARTED] == [[], []]  # the first try's cover is gone
    assert [p.task_dir for p in STARTED] == [tmp_path / ".md-tmp-t1"] * 2
    assert [p.name for p in tmp_path.iterdir()] == ["song.mp3"]


def test_every_try_has_its_own_process_and_both_are_ended_and_released(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # kill() ends the whole job (yt-dlp, its inner process, ffmpeg); close() frees the handle.
    engine, request = scripted(monkeypatch, FORBIDDEN, None)
    run(engine, request, tmp_path)
    assert [(p.killed, p.closed) for p in STARTED] == [(True, True), (True, True)]


def test_a_second_403_is_reported_the_way_it_always_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN, FORBIDDEN, None)
    with pytest.raises(EngineError) as error:
        run(engine, request, tmp_path)
    assert error.value.code is ErrorCode.UNKNOWN
    assert "HTTP Error 403: Forbidden" in error.value.detail
    assert len(STARTED) == 2  # once more, not twice more
    assert list(tmp_path.iterdir()) == []


def test_a_403_after_data_has_moved_is_not_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN_MIDWAY, None)
    with pytest.raises(EngineError) as error:
        run(engine, request, tmp_path)
    assert error.value.code is ErrorCode.UNKNOWN and len(STARTED) == 1
    assert list(tmp_path.iterdir()) == []


def test_other_errors_are_not_tried_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    engine, request = scripted(monkeypatch, PRIVATE, None)
    with pytest.raises(EngineError) as error:
        run(engine, request, tmp_path)
    assert error.value.code is ErrorCode.PRIVATE and len(STARTED) == 1


def test_cancel_during_the_second_try_stops_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN, None)
    HOOKS[(2, "line", 1)] = lambda: engine.cancel("t1")
    with pytest.raises(DownloadCancelled):
        run(engine, request, tmp_path)
    assert STARTED[1].killed and STARTED[1].closed
    assert list(tmp_path.iterdir()) == []


def test_cancel_between_the_two_tries_is_not_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # While the first try's folder is being deleted there is no process to stop.
    engine, request = scripted(monkeypatch, FORBIDDEN, None)
    HOOKS[(1, "close")] = lambda: engine.cancel("t1")
    with pytest.raises(DownloadCancelled):
        run(engine, request, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_a_cancel_does_not_leak_into_the_next_download_of_the_same_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN, None, None)
    HOOKS[(2, "line", 1)] = lambda: engine.cancel("t1")
    with pytest.raises(DownloadCancelled):
        run(engine, request, tmp_path)
    HOOKS.clear()
    assert run(engine, request, tmp_path) == str(tmp_path / "song.mp3")


def test_the_retry_reports_the_file_sizes_again_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, request = scripted(monkeypatch, FORBIDDEN, FORBIDDEN)
    events: list[object] = []
    with pytest.raises(EngineError):
        engine.download(replace(request, dest_dir=str(tmp_path)), events.append)
    assert events == [FileSizes((252182,)), FileSizes((252182,))]


# ---- yt-dlp.exe.old (ADR 0019)


@pytest.fixture
def bin_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(binaries, "bin_dir", lambda: tmp_path)
    (tmp_path / "yt-dlp.exe").write_text("new")
    (tmp_path / "yt-dlp.exe.old").write_text("old")
    return tmp_path


def updater(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    monkeypatch.setattr(engine_module, "run", lambda command, timeout: (0, stdout, ""))


def test_a_successful_update_deletes_the_old_exe(
    monkeypatch: pytest.MonkeyPatch, bin_dir: Path
) -> None:
    updater(monkeypatch, "Updating to stable@2026.10.26 ...\nUpdated yt-dlp to stable@2026.10.26\n")
    assert YtDlpEngine().update() is True
    assert sorted(p.name for p in bin_dir.iterdir()) == ["yt-dlp.exe"]


def test_starting_the_app_deletes_an_old_exe_left_by_an_earlier_run(
    bin_dir: Path, tmp_path: Path
) -> None:
    YtDlpEngine().remove_stale_temp(str(tmp_path))
    assert not (bin_dir / "yt-dlp.exe.old").exists()
    assert (bin_dir / "yt-dlp.exe").exists()


def test_an_old_exe_still_in_use_is_left_for_the_next_start(
    monkeypatch: pytest.MonkeyPatch, bin_dir: Path, tmp_path: Path
) -> None:
    def in_use(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(13, "in use by a running download")

    monkeypatch.setattr(Path, "unlink", in_use)
    YtDlpEngine().remove_stale_temp(str(tmp_path))  # no error
    monkeypatch.undo()
    assert (bin_dir / "yt-dlp.exe.old").exists()
