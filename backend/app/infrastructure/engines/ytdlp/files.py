"""The per-task temporary folder, and moving the finished file into the download folder."""

import ctypes
import os
import shutil
import time
from pathlib import Path

from app.domain.engine import OnDuplicate
from app.domain.media import Format

TEMP_PREFIX = ".md-tmp-"
_FILE_ATTRIBUTE_HIDDEN = 0x2
# Windows refuses these as a file name, with or without an extension. yt-dlp leaves them alone.
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10))}


def create_task_dir(dest_dir: str, task_id: str) -> Path:
    """An empty, hidden folder inside the download folder (same drive, so the final move is a
    rename). Raises ValueError for an id that could point outside of it."""
    if not task_id or not all(c.isalnum() or c in "-_" for c in task_id):
        raise ValueError(f"bad task id: {task_id!r}")
    path = Path(dest_dir) / f"{TEMP_PREFIX}{task_id}"
    remove_dir(path)
    path.mkdir(parents=True)
    ctypes.windll.kernel32.SetFileAttributesW(str(path), _FILE_ATTRIBUTE_HIDDEN)
    return path


def remove_dir(path: Path) -> None:
    # A process that was just killed can hold its files for a moment.
    for _ in range(20):
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
        time.sleep(0.1)


def remove_stale(dest_dir: str) -> None:
    """Deletes task folders a previous run left behind. Only call while nothing is downloading."""
    try:
        leftovers = [p for p in Path(dest_dir).iterdir() if p.name.startswith(TEMP_PREFIX)]
    except OSError:
        return
    for path in leftovers:
        if path.is_dir():
            remove_dir(path)


def final_name(printed: str, format: Format) -> str:
    """The name the finished file will have, from the name yt-dlp prints before downloading
    (which for MP3 still has the extension of the source audio)."""
    stem = Path(printed).stem
    if stem.split(".")[0].strip().upper() in _RESERVED:
        stem = f"_{stem}"
    return f"{stem}.{format}"


def target(dest_dir: str, name: str) -> Path:
    path = Path(dest_dir) / name
    # The name comes from a video title; it must stay a plain file name in the chosen folder.
    if path.name != name or path.resolve().parent != Path(dest_dir).resolve():
        raise ValueError(f"file name leaves the download folder: {name!r}")
    return path


def place(source: Path, dest_dir: str, name: str, on_duplicate: OnDuplicate) -> tuple[Path, bool]:
    """Moves source to dest_dir/name following the duplicate rule.
    Returns (where the file is, True if it was skipped and source was left alone)."""
    wanted = target(dest_dir, name)
    if on_duplicate is OnDuplicate.OVERWRITE:
        os.replace(source, wanted)
        return wanted, False
    stem, suffix = wanted.stem, wanted.suffix
    number = 0
    while True:
        candidate = wanted if number == 0 else wanted.with_name(f"{stem} ({number}){suffix}")
        try:
            # On Windows this fails if the target exists, so two tasks cannot overwrite each other.
            os.rename(source, candidate)
            return candidate, False
        except FileExistsError:
            if on_duplicate is OnDuplicate.SKIP:
                return candidate, True
            number += 1
