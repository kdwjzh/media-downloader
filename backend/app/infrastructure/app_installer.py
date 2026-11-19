"""Downloads, keeps and starts the installer of a newer version of this app (the
InstallerStore of services/ports.py; docs/decisions/0019).

The files go to <%LOCALAPPDATA%>\\media-downloader\\updates, a folder only this user (and
administrators) can write to, under names made here from a checked version number.
"""

import hashlib
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.infrastructure import http as fetch
from app.infrastructure import process, releases

# The installer is about 110 MB; a much larger answer is not ours.
MAX_INSTALLER_BYTES = 300 * 1024 * 1024
MAX_CHECKSUM_BYTES = 1024
READ_TIMEOUT = 30
# Inno Setup's switches (packaging/installer.iss): a progress window but no questions, no
# restart of Windows, and /UPDATE=1 makes it wait for the app to close and reopen it after.
INSTALLER_ARGS = ["/SILENT", "/NORESTART", "/UPDATE=1"]


def _error(error: Exception) -> EngineError:
    """Network trouble is NETWORK; an answer we did not expect, or the disk, is UNKNOWN."""
    if isinstance(error, EngineError):
        return error
    code = ErrorCode.NETWORK if fetch.is_network_error(error) else ErrorCode.UNKNOWN
    return EngineError(code, repr(error))


class AppInstaller:
    def __init__(self, folder: Path, source: Callable[[], releases.Source] = releases.source):
        self._folder = folder
        self._source = source

    def expected_name(self, version: str) -> str:
        return releases.installer_name(version)

    def _file(self, version: str) -> Path:
        return self._folder / self.expected_name(version)

    def _part(self, version: str) -> Path:
        return self._folder / (self.expected_name(version) + ".part")

    def checksum_text(self, version: str) -> str:
        where = self._source()
        try:
            data = fetch.get(
                releases.installer_url(version, where) + ".sha256", where.download_hosts,
                MAX_CHECKSUM_BYTES, READ_TIMEOUT, loopback_http=where.loopback_http,
            )  # fmt: skip
        except Exception as error:
            raise _error(error) from error
        return data.decode("ascii", errors="replace")

    def download(
        self,
        version: str,
        on_progress: Callable[[int, int | None], None],
        cancelled: Callable[[], bool],
    ) -> tuple[int, str] | None:
        where = self._source()
        part = self._part(version)
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
            done = fetch.download(
                releases.installer_url(version, where), where.download_hosts, part,
                MAX_INSTALLER_BYTES, READ_TIMEOUT, on_progress, cancelled,
                loopback_http=where.loopback_http,
            )  # fmt: skip
        except Exception as error:
            part.unlink(missing_ok=True)
            raise _error(error) from error
        if done is None:
            part.unlink(missing_ok=True)
        return done

    def accept(self, version: str) -> None:
        try:
            self._part(version).replace(self._file(version))
        except OSError as error:
            raise _error(error) from error

    def digest(self, version: str) -> tuple[int, str]:
        hashed = hashlib.sha256()
        size = 0
        try:
            with self._file(version).open("rb") as file:
                while chunk := file.read(1024 * 1024):
                    size += len(chunk)
                    hashed.update(chunk)
        except OSError as error:
            raise _error(error) from error
        return size, hashed.hexdigest()

    def launch(self, version: str) -> None:
        if not getattr(sys, "frozen", False):
            # Development: installing would put a packaged app over nothing we run here.
            raise EngineError(ErrorCode.UNKNOWN, "installers are only started by the packaged app")
        try:
            process.launch_detached([str(self._file(version)), *INSTALLER_ARGS])
        except OSError as error:
            raise _error(error) from error

    def discard(self) -> None:
        # A file still in use (an installer that is running) stays until the next start.
        shutil.rmtree(self._folder, ignore_errors=True)
