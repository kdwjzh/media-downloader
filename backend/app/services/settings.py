"""SettingsService: the settings, kept in a file (sections 2.10 and 3.4 of the contract).

No deadlock with the queue, by construction:
- reading takes no lock: the settings are one immutable object that is swapped as a whole,
  so the queue can read them while it holds its own lock;
- changing takes self._write, and on_change is called inside it (so listeners see the
  changes in order). on_change may take the queue's lock; the queue never changes a setting
  while holding its lock. The only order is settings -> queue.
"""

import logging
import os
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace

from app.domain.engine import OnDuplicate
from app.domain.media import Format
from app.domain.settings import EDITABLE, Settings, apply
from app.services.ports import KeyValueFile

log = logging.getLogger(__name__)

_OLD_DIRS = "old_download_dirs"


@dataclass(frozen=True)
class SettingsChanged:
    settings: Settings


class SettingsService:
    def __init__(
        self,
        file: KeyValueFile,
        default_download_dir: str,
        on_change: Callable[[SettingsChanged], None],
    ) -> None:
        """on_change must be quick, must not raise and must not change a setting."""
        self._file = file
        self._on_change = on_change
        self._write = threading.Lock()
        data = file.load() or {}
        self._settings = _from_file(data, default_download_dir)
        old = data.get(_OLD_DIRS)
        # Download folders that were changed away from: a run that ended abnormally may have
        # left temporary folders there (dirs_to_clean).
        self._old_dirs = [d for d in old if isinstance(d, str)] if isinstance(old, list) else []

    # ---- what the queue reads (QueueSettings); no lock

    @property
    def download_dir(self) -> str:
        return self._settings.download_dir

    @property
    def max_concurrent(self) -> int:
        return self._settings.max_concurrent

    @property
    def on_duplicate(self) -> OnDuplicate:
        return self._settings.on_duplicate

    def get(self) -> Settings:
        return self._settings

    # ---- changes

    def update(self, changes: Mapping[str, object]) -> Settings:
        """Raises ValueError for a field that cannot be changed or a value out of range;
        nothing is changed then."""
        with self._write:
            self._commit(apply(self._settings, changes))
            return self._settings

    def set_download_dir(self, path: str) -> Settings:
        """For the folder dialog. Raises ValueError unless path is an absolute path of an
        existing folder that can be written to."""
        if not os.path.isabs(path) or not os.path.isdir(path):
            raise ValueError("not an existing folder")
        path = os.path.normpath(path)
        try:
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError as error:
            raise ValueError("the folder cannot be written to") from error
        with self._write:
            old = self._settings.download_dir
            if path != old:
                self._old_dirs = [d for d in self._old_dirs if d not in (old, path)] + [old]
                self._commit(replace(self._settings, download_dir=path))
            return self._settings

    def remember_format(self, format: Format, quality: int) -> None:
        field = "mp3_bitrate" if format is Format.MP3 else "mp4_height"
        with self._write:
            try:
                self._commit(apply(self._settings, {"format": format, field: quality}))
            except ValueError:
                log.exception("could not remember %s %s", format, quality)

    def dirs_to_clean(self) -> list[str]:
        with self._write:
            current = self._settings.download_dir
            dirs = [current] + [d for d in self._old_dirs if d != current]
            if self._old_dirs:
                self._old_dirs = []
                self._save()
            return dirs

    def _commit(self, new: Settings) -> None:
        """(self._write held)"""
        if new == self._settings:
            return
        self._settings = new
        self._save()
        try:
            self._on_change(SettingsChanged(new))
        except Exception:
            log.exception("the settings listener failed")

    def _save(self) -> None:
        """(self._write held) A change that cannot be saved still holds until the app closes."""
        try:
            self._file.save({**asdict(self._settings), _OLD_DIRS: self._old_dirs})
        except OSError:
            log.exception("could not save the settings")


def _from_file(data: Mapping[str, object], default_download_dir: str) -> Settings:
    """A value the file has wrong (edited by hand, or written by another version) becomes
    the default; the other values are kept."""
    settings = Settings(default_download_dir)
    folder = data.get("download_dir")
    if isinstance(folder, str) and os.path.isabs(folder):
        settings = replace(settings, download_dir=folder)
    for name in EDITABLE:
        if name in data:
            try:
                settings = apply(settings, {name: data[name]})
            except ValueError as error:
                log.warning("setting %s in the file is ignored: %s", name, error)
    return settings
