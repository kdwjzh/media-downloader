"""ExternalService: opens folders, the log file and two fixed web pages
(sections 2.14 and 3.6 of the contract, and the two "open folder" commands)."""

import logging
import os
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from app import REPOSITORY
from app.services.ports import Shell

log = logging.getLogger(__name__)

# The UI only names a page; it cannot make the back end open an address of its choosing.
LINKS = {
    "releasePage": f"https://github.com/{REPOSITORY}/releases/latest",
    "sourceCode": f"https://github.com/{REPOSITORY}",
}


class Opened(StrEnum):
    FILE = "file"  # File Explorer is open with the file selected
    FOLDER = "folder"  # the file is gone; its folder was opened instead
    NONE = "none"  # the folder is gone too


class ExternalService:
    def __init__(
        self,
        shell: Shell,
        task_path: Callable[[str], str | None],
        history_path: Callable[[str], str | None],
        log_file: Path,
    ) -> None:
        """task_path and history_path give the finished file of a task id or a history id."""
        self._shell = shell
        self._task_path = task_path
        self._history_path = history_path
        self._log_file = log_file

    def open_task_folder(self, task_id: str) -> Opened:
        return self._reveal(self._task_path(task_id))

    def open_history_folder(self, entry_id: str) -> Opened:
        return self._reveal(self._history_path(entry_id))

    def open_log_file(self) -> None:
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._log_file.touch()
        self._shell.open_path(str(self._log_file))

    def open_log_folder(self) -> None:
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._shell.open_path(str(self._log_file.parent))

    def open_link(self, target: str) -> None:
        """Raises ValueError for a name that is not in LINKS."""
        if target not in LINKS:
            raise ValueError(f"{target!r} is not a page this app opens")
        self._shell.open_url(LINKS[target])

    def _reveal(self, path: str | None) -> Opened:
        if not path:
            return Opened.NONE
        for exists, open_it, target, result in (
            (os.path.isfile, self._shell.select_file, path, Opened.FILE),
            (os.path.isdir, self._shell.open_path, os.path.dirname(path), Opened.FOLDER),
        ):
            if exists(target):
                try:
                    open_it(target)
                    return result
                except OSError:
                    log.exception("Windows could not open it")  # the path is not logged
        return Opened.NONE
