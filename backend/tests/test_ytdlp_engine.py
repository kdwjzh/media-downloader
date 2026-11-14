"""YtDlpEngine.download around the process: a stand-in prints what yt-dlp would print.
Real files; no network, no yt-dlp."""

import errno
from pathlib import Path

import pytest

from app.domain.engine import DownloadRequest, EngineError, OnDuplicate
from app.domain.errors import ErrorCode
from app.domain.media import Format
from app.infrastructure.engines.ytdlp import args, files
from app.infrastructure.engines.ytdlp import engine as engine_module
from app.infrastructure.engines.ytdlp.engine import YtDlpEngine

URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


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
