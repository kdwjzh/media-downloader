"""UpdateService: is there a newer app, updating the engine, and the "about" data
(sections 2.11-2.13 and 3.5 of the contract)."""

import logging
import re
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from app.domain.engine import EngineError, MediaEngine
from app.services.ports import KeyValueFile

log = logging.getLogger(__name__)

# GitHub allows 60 anonymous requests an hour per address, and the app asks at every start.
FOUND_TTL = 24 * 3600
# Offline, no release yet, a private repository: ask again sooner, but not at every start.
FAILED_TTL = 3600


@dataclass(frozen=True)
class AppUpdateInfo:
    current_version: str
    latest_version: str | None = None  # only when it is newer than the current one


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


def parse_version(text: str) -> tuple[int, int, int] | None:
    """"v1.2.3" or "1.2.3". Anything else (a pre-release, two numbers) is None."""
    found = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    return (int(found[1]), int(found[2]), int(found[3])) if found else None


class UpdateService:
    def __init__(
        self,
        engine: MediaEngine,
        app_version: str,
        latest_tag: Callable[[], str],
        cache: KeyValueFile,
        components: Sequence[tuple[Component, Callable[[], str | None] | None]],
        now: Callable[[], float] = time.time,
    ) -> None:
        """latest_tag asks the network and raises OSError or ValueError when it cannot tell.
        components: each third-party component, with how to read its version if it has one."""
        self._engine = engine
        self._app_version = app_version
        self._latest_tag = latest_tag
        self._cache = cache
        self._components = components
        self._now = now
        self._lock = threading.Lock()
        self._about: AboutInfo | None = None

    def check_app_update(self) -> AppUpdateInfo:
        """Never raises: whatever goes wrong means "no newer version"."""
        try:
            latest, current = self._latest(), parse_version(self._app_version)
            if latest and current and latest > current:
                return AppUpdateInfo(self._app_version, ".".join(map(str, latest)))
        except Exception:
            log.exception("could not check for a new version")
        return AppUpdateInfo(self._app_version)

    def _latest(self) -> tuple[int, int, int] | None:
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
            return parse_version(tag) if tag else None

    def update_engine(self) -> EngineUpdateResult:
        """Raises EngineError (NETWORK or UNKNOWN)."""
        try:
            updated = self._engine.update()
            version = self._engine.version()
        except EngineError as error:
            log.warning("engine update failed: %s: %s", error.code, error.detail)
            raise
        with self._lock:
            self._about = None
        return EngineUpdateResult(updated, version)

    def get_about(self) -> AboutInfo:
        """Reading the versions starts the programs, so it is done once and kept."""
        with self._lock:
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
