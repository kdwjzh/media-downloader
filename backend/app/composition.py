"""Builds every service with the real engine, files and Windows. The one place that knows
which implementation goes where; the bridge (stage 4) and scripts/manual/ start from here.

Not a layer of its own: it sits beside main.py, above everything it wires together.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app import __version__
from app.domain.history import HistoryRecord
from app.infrastructure import binaries, releases
from app.infrastructure.app_installer import AppInstaller
from app.infrastructure.engines.ytdlp import urls
from app.infrastructure.engines.ytdlp.engine import YtDlpEngine
from app.infrastructure.logging.setup import setup as setup_logging
from app.infrastructure.shell import WindowsShell
from app.infrastructure.storage import paths
from app.infrastructure.storage.history_db import HistoryDb
from app.infrastructure.storage.json_file import JsonFile
from app.infrastructure.thumbnails import ThumbnailMaker
from app.services.external import ExternalService
from app.services.history import HistoryAdded, HistoryService
from app.services.media_info import MediaInfoService
from app.services.queue import QueueEvent, QueueService
from app.services.settings import SettingsChanged, SettingsService
from app.services.updates import AppUpdateChanged, AppUpdateService, Component, UpdateService

log = logging.getLogger(__name__)

Event = QueueEvent | HistoryAdded | SettingsChanged | AppUpdateChanged


@dataclass(frozen=True)
class Backend:
    media_info: MediaInfoService
    queue: QueueService
    settings: SettingsService
    history: HistoryService
    updates: UpdateService
    app_update: AppUpdateService
    external: ExternalService

    def start(self) -> None:
        """Call once, before anything is added to the queue."""
        self.queue.start()
        self.app_update.clean()

    def shutdown(self) -> None:
        self.queue.shutdown()


def build(
    emit: Callable[[Event], None],
    data_dir: Path | None = None,
    local_dir: Path | None = None,
) -> Backend:
    """emit receives every event of section 4 of the contract. Queue events come on the
    queue's own sender thread; history and settings events on the thread that caused them,
    so emit must be quick and must not call back into the services.
    data_dir (settings, history) and local_dir (log files, caches) default to the app's
    folders in %APPDATA% and %LOCALAPPDATA%."""
    data_dir = data_dir or paths.data_dir()
    local_dir = local_dir or paths.local_dir()
    log_file = setup_logging(local_dir / "logs")
    log.info("Media Downloader %s started", __version__)

    engine = YtDlpEngine()
    media_info = MediaInfoService(engine)

    def settings_changed(event: SettingsChanged) -> None:
        queue.settings_changed()  # the number of simultaneous downloads may be what changed
        emit(event)

    def requeue(record: HistoryRecord) -> str | None:
        entry = record.entry
        media_info.remember(entry.url, entry.title, record.thumb_url)
        added = queue.add([entry.url], entry.format, entry.quality, remember=False)
        return added[0] if added else None

    settings = SettingsService(
        JsonFile(data_dir / "settings.json"), paths.downloads_dir(), settings_changed
    )
    history = HistoryService(
        HistoryDb(data_dir / "history.db"), ThumbnailMaker(urls.THUMB_HOSTS), emit, requeue
    )
    queue = QueueService(engine, media_info, settings, history, emit)
    updates = UpdateService(
        engine,
        __version__,
        releases.latest_tag,
        JsonFile(local_dir / "update-check.json"),
        [
            (Component("yt-dlp", "Unlicense"), engine.version),
            (Component("FFmpeg", "GPL-3.0-or-later"), binaries.ffmpeg_version),
            (Component("Deno", "MIT"), binaries.deno_version),
            (Component("Noto Sans TC", "OFL-1.1"), None),
            (Component("Bricolage Grotesque", "OFL-1.1"), None),
        ],
        JsonFile(local_dir / "engine-update.json"),
    )
    app_update = AppUpdateService(
        updates.check_app_update, AppInstaller(local_dir / "updates"), emit
    )
    external = ExternalService(WindowsShell(), queue.file_path, history.file_path, log_file)
    return Backend(media_info, queue, settings, history, updates, app_update, external)
