"""UpdateService: is there a newer app, updating the engine, and the "about" data.
AppUpdateService: downloading, checking and starting a newer app's installer.
Sections 2.11-2.15 and 3.5 of the contract; docs/decisions/0019."""

import logging
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from app.domain import version
from app.domain.engine import EngineError, MediaEngine
from app.domain.errors import ErrorCode
from app.services.ports import InstallerStore, KeyValueFile

log = logging.getLogger(__name__)

# GitHub allows 60 anonymous requests an hour per address, and the app asks at every start.
FOUND_TTL = 24 * 3600
# Offline, no release yet, a private repository: ask again sooner, but not at every start.
FAILED_TTL = 3600
# yt-dlp updates itself through the same GitHub API, so the same limits apply (ADR 0019).
ENGINE_CHECKED_TTL = 24 * 3600
ENGINE_FAILED_TTL = 3600


class Stage(StrEnum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    READY = "ready"  # checked and waiting for install_app_update
    INSTALLING = "installing"  # the installer was started; the app closes
    FAILED = "failed"


@dataclass(frozen=True)
class AppUpdateStatus:
    stage: Stage
    received_bytes: int | None = None  # downloading only
    total_bytes: int | None = None  # downloading, when the server says
    error: ErrorCode | None = None  # failed only


@dataclass(frozen=True)
class AppUpdateChanged:
    status: AppUpdateStatus


@dataclass(frozen=True)
class AppUpdateInfo:
    current_version: str
    latest_version: str | None = None  # only when it is newer than the current one
    status: AppUpdateStatus | None = None  # only when an update is under way or failed


@dataclass(frozen=True)
class EngineUpdateResult:
    updated: bool
    version: str


@dataclass(frozen=True)
class Component:
    name: str
    license: str
    version: str | None = None


@dataclass(frozen=True)
class AboutInfo:
    app_version: str
    components: tuple[Component, ...]


class UpdateService:
    def __init__(
        self,
        engine: MediaEngine,
        app_version: str,
        latest_tag: Callable[[], str],
        cache: KeyValueFile,
        components: Sequence[tuple[Component, Callable[[], str | None] | None]],
        engine_cache: KeyValueFile,
        now: Callable[[], float] = time.time,
    ) -> None:
        """latest_tag asks the network and raises OSError or ValueError when it cannot tell.
        components: each third-party component, with how to read its version if it has one.
        engine_cache: when the engine last updated itself at start."""
        self._engine = engine
        self._app_version = app_version
        self._latest_tag = latest_tag
        self._cache = cache
        self._components = components
        self._engine_cache = engine_cache
        self._now = now
        self._lock = threading.Lock()
        # Held while the engine updates itself, and while its version is read: reading it
        # halfway through an update would show the old one. Taken before _lock, never after.
        self._engine_lock = threading.Lock()
        self._about: AboutInfo | None = None

    def check_app_update(self) -> AppUpdateInfo:
        """Never raises: whatever goes wrong means "no newer version"."""
        try:
            tag, current = self._latest(), version.parse(self._app_version)
            latest = version.parse(tag) if tag else None
            if latest and current and latest > current:
                return AppUpdateInfo(self._app_version, version.plain(tag or ""))
        except Exception:
            log.exception("could not check for a new version")
        return AppUpdateInfo(self._app_version)

    def _latest(self) -> str | None:
        with self._lock:  # two checks at once ask the network once
            now = self._now()
            cached = self._cache.load() or {}
            at, tag = cached.get("checked_at"), cached.get("latest")
            if not isinstance(tag, str):
                tag = None
            ttl = FOUND_TTL if tag else FAILED_TTL
            if not isinstance(at, int | float) or not 0 <= now - at < ttl:
                try:
                    tag = self._latest_tag()
                except (OSError, ValueError) as error:
                    log.info("no answer about a new version: %s", error)
                    tag = None
                try:
                    self._cache.save({"checked_at": now, "latest": tag})
                except OSError:
                    log.exception("could not save the result of the version check")
            return tag

    def update_engine(self) -> EngineUpdateResult:
        """Raises EngineError (NETWORK or UNKNOWN). One update at a time: a second caller
        waits for the first and then asks again, which is quick."""
        with self._engine_lock:
            try:
                updated = self._engine.update()
                found = self._engine.version()
            except EngineError as error:
                log.warning("engine update failed: %s: %s", error.code, error.detail)
                raise
            with self._lock:
                self._about = None
        return EngineUpdateResult(updated, found)

    def auto_update_engine(self) -> None:
        """At start, on a thread of its own: updates the engine when the last try is old
        enough. Never raises; the outcome only goes to the log file."""
        try:
            cached = self._engine_cache.load() or {}
        except Exception:
            cached = {}
        at, ok = cached.get("checked_at"), cached.get("ok") is True
        ttl = ENGINE_CHECKED_TTL if ok else ENGINE_FAILED_TTL
        now = self._now()
        if isinstance(at, int | float) and 0 <= now - at < ttl:
            return
        try:
            result = self.update_engine()
            log.info("engine checked at start: %s %s",
                     "updated to" if result.updated else "already", result.version)  # fmt: skip
            ok = True
        except Exception:
            log.exception("could not update the engine at start")
            ok = False
        try:
            self._engine_cache.save({"checked_at": now, "ok": ok})
        except OSError:
            log.exception("could not save when the engine was checked")

    def get_about(self) -> AboutInfo:
        """Reading the versions starts the programs, so it is done once and kept."""
        with self._engine_lock, self._lock:
            if self._about is None:
                self._about = AboutInfo(
                    self._app_version,
                    tuple(
                        replace(component, version=_safely(read) if read else None)
                        for component, read in self._components
                    ),
                )
            return self._about


def _safely(read: Callable[[], str | None]) -> str | None:
    try:
        return read()
    except Exception as error:
        log.warning("could not read a component's version: %s", error)
        return None


# Like the queue's progress: at most every 0.5 s, and a value that comes too early is dropped.
PROGRESS_INTERVAL = 0.5
_CHECKSUM = re.compile(r"([0-9a-fA-F]{64}) [ *]?(\S+)")


def parse_checksum(text: str, name: str) -> str | None:
    """The SHA-256 (lower case) that a "<hex>  <file name>" line gives for name; None for
    anything else, so that a file we cannot read is never taken as a match."""
    found = _CHECKSUM.fullmatch(text.strip()) if len(text) < 1024 else None
    return found[1].lower() if found and found[2] == name else None


def _daemon(work: Callable[[], None]) -> None:
    threading.Thread(target=work, daemon=True).start()


class AppUpdateService:
    """One update at a time. State changes reach the page as AppUpdateChanged, emitted
    while holding the lock so that they arrive in order."""

    def __init__(
        self,
        check: Callable[[], AppUpdateInfo],
        store: InstallerStore,
        emit: Callable[[AppUpdateChanged], None],
        now: Callable[[], float] = time.monotonic,
        spawn: Callable[[Callable[[], None]], None] = _daemon,
    ) -> None:
        """check is UpdateService.check_app_update. emit must be quick."""
        self._check = check
        self._store = store
        self._emit = emit
        self._now = now
        self._spawn = spawn
        self._lock = threading.Lock()
        self._status = AppUpdateStatus(Stage.IDLE)
        self._run = 0  # which start() the worker belongs to; a cancelled one is outdated
        self._ready: tuple[str, int, str] | None = None  # version, size, SHA-256
        self._last_progress = float("-inf")
        self._done = threading.Event()  # the last worker no longer touches the files
        self._done.set()

    def clean(self) -> None:
        """At start: what an earlier run downloaded is not needed any more."""
        self._discard()

    def info(self) -> AppUpdateInfo:
        info = self._check()
        with self._lock:
            status = self._status
        return replace(info, status=None if status.stage is Stage.IDLE else status)

    def start(self) -> AppUpdateStatus:
        """Starts downloading the newer version. Does nothing when there is none or an
        update is already under way."""
        if not self._can_start():
            return self.status()
        newer = self._check().latest_version
        with self._lock:
            if newer is None or self._status.stage not in (Stage.IDLE, Stage.FAILED):
                return self._status
            self._run += 1
            run, previous, mine = self._run, self._done, threading.Event()
            self._done = mine
            self._ready = None
            self._last_progress = float("-inf")
            self._set(AppUpdateStatus(Stage.DOWNLOADING, 0))
            status = self._status
        self._spawn(lambda: self._work(newer, run, previous, mine))
        return status

    def status(self) -> AppUpdateStatus:
        with self._lock:
            return self._status

    def cancel(self) -> None:
        """Stops a download or check; nothing is left behind. Too late once ready."""
        with self._lock:
            if self._status.stage in (Stage.DOWNLOADING, Stage.VERIFYING):
                self._run += 1
                self._set(AppUpdateStatus(Stage.IDLE))

    def install(self) -> bool:
        """Starts the checked installer; True when it runs and the app must close now,
        False when nothing is ready. Raises EngineError when it cannot be started: the file
        changed since it was checked (CHECKSUM_MISMATCH) or would not start (UNKNOWN)."""
        with self._lock:
            ready = self._ready if self._status.stage is Stage.READY else None
            if ready is None:
                return False
            self._set(AppUpdateStatus(Stage.VERIFYING))
        newer, size, digest = ready
        try:
            # Checked again: it may have waited on the disk for a while.
            if self._store.digest(newer) != (size, digest):
                raise EngineError(ErrorCode.CHECKSUM_MISMATCH, "changed after it was checked")
            self._store.launch(newer)
        except Exception as error:
            code = error.code if isinstance(error, EngineError) else ErrorCode.UNKNOWN
            log.error("could not start the installer: %s: %s", code, error)
            self._discard()
            with self._lock:
                self._ready = None
                self._set(AppUpdateStatus(Stage.FAILED, error=code))
            raise EngineError(code, str(error)) from error
        with self._lock:
            self._set(AppUpdateStatus(Stage.INSTALLING))
        return True

    # ---- the worker thread

    def _work(self, newer: str, run: int, previous: threading.Event, mine: threading.Event) -> None:
        previous.wait()  # a cancelled worker may still be closing its partial file
        try:
            if self._outdated(run):
                return
            expected = parse_checksum(
                self._store.checksum_text(newer), self._store.expected_name(newer)
            )
            if expected is None:
                raise EngineError(ErrorCode.CHECKSUM_MISMATCH, "unreadable checksum file")
            done = self._store.download(
                newer, lambda got, total: self._progress(run, got, total),
                lambda: self._outdated(run),
            )  # fmt: skip
            if done is None or not self._advance(run, AppUpdateStatus(Stage.VERIFYING)):
                return
            size, digest = done
            if digest != expected:
                raise EngineError(ErrorCode.CHECKSUM_MISMATCH, f"{digest}, expected {expected}")
            self._store.accept(newer)
            with self._lock:
                if self._run == run:
                    self._ready = (newer, size, digest)
                    self._set(AppUpdateStatus(Stage.READY))
        except Exception as error:
            code = error.code if isinstance(error, EngineError) else ErrorCode.UNKNOWN
            level = logging.INFO if code is ErrorCode.NETWORK else logging.ERROR
            log.log(level, "app update failed: %s: %s", code, error)
            self._discard()
            self._advance(run, AppUpdateStatus(Stage.FAILED, error=code))
        finally:
            if self._outdated(run):
                self._discard()  # cancelled: nothing is left behind
            mine.set()

    def _progress(self, run: int, received: int, total: int | None) -> None:
        with self._lock:
            now = self._now()
            if self._run != run or now - self._last_progress < PROGRESS_INTERVAL:
                return
            self._last_progress = now
            self._set(AppUpdateStatus(Stage.DOWNLOADING, received, total))

    def _advance(self, run: int, status: AppUpdateStatus) -> bool:
        with self._lock:
            if self._run != run:
                return False
            self._set(status)
            return True

    def _outdated(self, run: int) -> bool:
        with self._lock:
            return self._run != run

    def _can_start(self) -> bool:
        with self._lock:
            return self._status.stage in (Stage.IDLE, Stage.FAILED)

    def _set(self, status: AppUpdateStatus) -> None:
        """Holding the lock."""
        if status != self._status:
            self._status = status
            self._emit(AppUpdateChanged(status))

    def _discard(self) -> None:
        try:
            self._store.discard()
        except Exception:
            log.exception("could not delete the downloaded installer")
