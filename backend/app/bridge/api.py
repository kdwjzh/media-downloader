"""The commands of docs/介面與後端的約定.md section 3, exposed to the page through pywebview.

pywebview exposes every attribute of this object whose name does not start with "_",
including the attributes of attributes: everything that is not a command is private.
Every command replies {ok: true[, data]} or {ok: false, error: <ErrorCode>}; no exception
reaches the page (the hand-over, 3.1).
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.bridge import shapes
from app.bridge.events import EventSender
from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.domain.media import Format
from app.domain.settings import EDITABLE
from app.domain.task import FINISHED

if TYPE_CHECKING:  # the type only: the bridge never builds anything (main.py does)
    from app.composition import Backend

log = logging.getLogger(__name__)

Reply = dict[str, object]

# camelCase name in the contract -> field of Settings. Unknown names pass through unchanged
# and are refused by the settings service.
_SETTING_FIELDS = {shapes.camel(name): name for name in EDITABLE}


def _run(command: str, work: Callable[[], object]) -> Reply:
    try:
        data = work()
    except EngineError as error:
        log.info("%s failed: %s: %s", command, error.code, error.detail)
        return {"ok": False, "error": error.code.value}
    except Exception:
        # A bug, or arguments the contract does not allow. The page only learns "unknown".
        log.exception("%s failed", command)
        return {"ok": False, "error": ErrorCode.UNKNOWN.value}
    return {"ok": True} if data is None else {"ok": True, "data": data}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TypeError("expected a list of strings")
    return value


class BridgeApi:
    def __init__(
        self,
        backend: "Backend",
        events: EventSender,
        choose_folder: Callable[[str], str | None],
        close_window: Callable[[], None],
    ) -> None:
        """choose_folder opens the system's folder dialog at a folder and returns the chosen
        one, or None. close_window closes the window (_on_closing then lets it go)."""
        self._backend = backend
        self._events = events
        self._choose_folder = choose_folder
        self._close_window = close_window
        self._close_confirmed = False

    # ---- the window (not commands)

    def _on_closing(self) -> bool:
        """Runs on the UI thread when the window is about to close; False keeps it open.
        It must not wait for the page (that would deadlock), so it only queues an event."""
        try:
            busy = any(item.status not in FINISHED for item in self._backend.queue.items())
        except Exception:
            log.exception("could not tell whether tasks are running")
            busy = False
        if self._close_confirmed or not busy:
            self._close_confirmed = True
            self._events.close()
            return True
        self._events.emit(shapes.CloseRequested())
        return False

    def _close_now(self) -> None:
        self._close_confirmed = True
        self._close_window()

    # ---- lookup and queue

    def lookup(self, url: str) -> Reply:
        return _run("lookup", lambda: shapes.lookup(self._backend.media_info.lookup(url)))

    def add_to_queue(self, urls: list[str], format: str, quality: int) -> Reply:
        def work() -> object:
            ids = self._backend.queue.add(_strings(urls), Format(format), quality)
            return {"taskIds": ids}

        return _run("add_to_queue", work)

    def get_queue(self) -> Reply:
        return _run("get_queue", lambda: shapes.to_json(self._backend.queue.items()))

    def cancel_task(self, id: str) -> Reply:
        return _run("cancel_task", lambda: self._backend.queue.cancel(id))

    def retry_task(self, id: str) -> Reply:
        return _run("retry_task", lambda: self._backend.queue.retry(id))

    def readd_task(self, id: str) -> Reply:
        return _run("readd_task", lambda: self._backend.queue.readd(id))

    def remove_task(self, id: str) -> Reply:
        return _run("remove_task", lambda: self._backend.queue.remove(id))

    def clear_finished(self) -> Reply:
        return _run("clear_finished", self._backend.queue.clear_finished)

    def open_task_folder(self, id: str) -> Reply:
        return _run(
            "open_task_folder",
            lambda: {"opened": self._backend.external.open_task_folder(id).value},
        )

    # ---- history

    def list_history(self) -> Reply:
        return _run("list_history", lambda: shapes.to_json(self._backend.history.list()))

    def redownload_history(self, id: str) -> Reply:
        def work() -> object:
            task_id = self._backend.history.redownload(id)
            return {"taskId": task_id} if task_id else {}

        return _run("redownload_history", work)

    def open_history_folder(self, id: str) -> Reply:
        return _run(
            "open_history_folder",
            lambda: {"opened": self._backend.external.open_history_folder(id).value},
        )

    def delete_history(self, id: str) -> Reply:
        return _run("delete_history", lambda: self._backend.history.delete(id))

    def clear_history(self) -> Reply:
        return _run("clear_history", self._backend.history.clear)

    # ---- settings

    def get_settings(self) -> Reply:
        return _run("get_settings", lambda: shapes.to_json(self._backend.settings.get()))

    def update_settings(self, changes: dict[str, object]) -> Reply:
        def work() -> object:
            if not isinstance(changes, dict):
                raise TypeError("expected an object")
            named = {_SETTING_FIELDS.get(key, key): value for key, value in changes.items()}
            return shapes.to_json(self._backend.settings.update(named))

        return _run("update_settings", work)

    def choose_download_folder(self) -> Reply:
        def work() -> object:
            current = self._backend.settings.get()
            chosen = self._choose_folder(current.download_dir)
            # Cancelled: the settings as they were. A folder that cannot be written to:
            # ValueError, which the page shows with its own message (contract 3.4).
            settings = self._backend.settings.set_download_dir(chosen) if chosen else current
            return shapes.to_json(settings)

        return _run("choose_download_folder", work)

    # ---- updates and about

    def check_app_update(self) -> Reply:
        return _run("check_app_update", lambda: shapes.to_json(self._backend.app_update.info()))

    def start_app_update(self) -> Reply:
        return _run(
            "start_app_update", lambda: shapes.to_json(self._backend.app_update.start())
        )

    def cancel_app_update(self) -> Reply:
        return _run("cancel_app_update", self._backend.app_update.cancel)

    def install_app_update(self) -> Reply:
        def work() -> None:
            # The installer waits for this app to end; closing stops every download.
            if self._backend.app_update.install():
                self._close_now()

        return _run("install_app_update", work)

    def update_engine(self) -> Reply:
        return _run("update_engine", lambda: shapes.to_json(self._backend.updates.update_engine()))

    def get_about(self) -> Reply:
        return _run("get_about", lambda: shapes.to_json(self._backend.updates.get_about()))

    # ---- outside the app

    def open_log_file(self) -> Reply:
        return _run("open_log_file", self._backend.external.open_log_file)

    def open_log_folder(self) -> Reply:
        return _run("open_log_folder", self._backend.external.open_log_folder)

    def open_link(self, target: str) -> Reply:
        return _run("open_link", lambda: self._backend.external.open_link(target))

    # ---- the window

    def confirm_close(self) -> Reply:
        return _run("confirm_close", self._close_now)

    def ping(self) -> Reply:
        return {"ok": True, "data": "pong"}
