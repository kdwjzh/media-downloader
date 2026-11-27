"""The log file: personal paths are masked before anything is written, and it rotates."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.infrastructure.logging.setup import BACKUPS, file_handler, mask, masker, short_path

HOME = "C:\\Users\\Some One"
M = masker(HOME)


@pytest.mark.parametrize(
    ("text", "masked"),
    [
        ("C:\\Users\\Some One\\Music\\a.mp3", "%USERPROFILE%\\Music\\a.mp3"),
        ("c:\\users\\some one\\Music", "%USERPROFILE%\\Music"),  # Windows ignores case
        ("C:/Users/Some One/Music/a.mp3", "%USERPROFILE%/Music/a.mp3"),
        ("'C:\\\\Users\\\\Some One\\\\Music'", "'%USERPROFILE%\\\\Music'"),  # a repr()
        ("/c/Users/Some One/bin", "/c/%USERPROFILE%/bin"),
        ("\\\\?\\C:\\Users\\Some One", "\\\\?\\%USERPROFILE%"),
        ("at C:\\Users\\Some One.", "at %USERPROFILE%."),
        ("two: C:\\Users\\Some One\\a and C:\\Users\\Some One\\b",
         "two: %USERPROFILE%\\a and %USERPROFILE%\\b"),
        # Someone else's folder that only starts the same is left alone.
        ("C:\\Users\\Some One2\\x", "C:\\Users\\Some One2\\x"),
        ("D:\\Music\\a.mp3", "D:\\Music\\a.mp3"),
    ],
)  # fmt: skip
def test_the_users_folder_is_masked_however_it_is_written(text: str, masked: str) -> None:
    assert mask(text, M) == masked


def test_the_short_8_3_name_of_the_users_folder_is_masked_too(tmp_path: Path) -> None:
    # Windows often gives the 8.3 form (TEMP is C:\Users\SOMEON~1\AppData\Local\Temp);
    # masking only the long form left the user's name in the log.
    short = "C:\\Users\\SOMEON~1"
    both = masker(HOME, short)
    assert mask("C:\\Users\\SOMEON~1\\AppData\\Local\\Temp\\x", both) == (
        "%USERPROFILE%\\AppData\\Local\\Temp\\x"
    )
    assert mask("/c/Users/someon~1/bin", both) == "/c/%USERPROFILE%/bin"
    assert mask(f"{HOME}\\Music", both) == "%USERPROFILE%\\Music"
    assert mask("C:\\Users\\SOMEON~12\\x", both) == "C:\\Users\\SOMEON~12\\x"
    handler = file_handler(tmp_path / "app.log", HOME, short)
    record = logging.LogRecord("t", logging.INFO, "", 0, "temp is %s", (short + "\\Temp",), None)
    assert "SOMEON~1" not in handler.format(record)
    handler.close()


def test_short_path_falls_back_to_the_path_it_was_given() -> None:
    missing = "C:\\no such folder here\\at all"
    assert short_path(missing) == missing


def test_a_signed_media_url_loses_its_query_but_a_video_url_does_not() -> None:
    signed = "https://rr3---sn-abc.googlevideo.com/videoplayback?expire=1&ip=203.0.113.7&" + (
        "sig=" + "A" * 200
    )
    video = "https://www.youtube.com/watch?v=jNQXAC9IVRw&list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
    text = mask(f"ERROR: unable to download {signed}: timed out; from {video}", M)
    assert "203.0.113.7" not in text and "sig=" not in text
    assert "https://rr3---sn-abc.googlevideo.com/videoplayback?..." in text
    assert video in text and "timed out" in text


@pytest.fixture
def logger(tmp_path: Path) -> Iterator[logging.Logger]:
    logger = logging.getLogger("test-log-file")
    logger.propagate = False
    logger.setLevel(logging.INFO)
    handler = file_handler(tmp_path / "logs" / "app.log", HOME, max_bytes=2000)
    logger.addHandler(handler)
    yield logger
    logger.removeHandler(handler)
    handler.close()


def test_the_raw_error_of_a_failed_download_is_in_the_file_without_the_users_name(
    logger: logging.Logger, tmp_path: Path
) -> None:
    # C11 of the old version: errors were only printed. The line is the one the queue logs.
    raw = "ERROR: unable to open for writing: 'C:\\Users\\Some One\\Music\\.md-tmp-1\\歌.part'"
    error = EngineError(ErrorCode.UNKNOWN, raw)
    logger.warning("task %s failed: %s: %s", "abc", error.code, error.detail)
    try:
        raise OSError(13, "Permission denied", "C:\\Users\\Some One\\Music\\x.mp3")
    except OSError:
        logger.exception("could not finish")  # the traceback is masked too
    text = (tmp_path / "logs" / "app.log").read_text("utf-8")
    assert "unable to open for writing: '%USERPROFILE%\\Music\\.md-tmp-1\\歌.part'" in text
    assert "WARNING test-log-file: task abc failed: unknown:" in text
    assert "Traceback" in text and "PermissionError" in text
    assert "Some One" not in text


def test_the_file_rotates_and_keeps_a_fixed_number_of_old_files(
    logger: logging.Logger, tmp_path: Path
) -> None:
    for n in range(400):
        logger.info("line %s %s", n, "x" * 50)
    files = sorted(path.name for path in (tmp_path / "logs").iterdir())
    assert files == ["app.log", "app.log.1", "app.log.2", "app.log.3"]
    assert len(files) == BACKUPS + 1
    assert all(path.stat().st_size <= 2000 for path in (tmp_path / "logs").iterdir())
    assert "line 399" in (tmp_path / "logs" / "app.log").read_text("utf-8")
