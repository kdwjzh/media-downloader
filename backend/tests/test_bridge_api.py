"""BridgeApi: every command's reply, field by field against docs/介面與後端的約定.md
sections 1-3. The services are stand-ins; no window, no network."""

import logging
from collections.abc import Callable
from unittest.mock import Mock

import pytest

from app.bridge import shapes
from app.bridge.api import BridgeApi
from app.composition import Backend
from app.domain.engine import EngineError, OnDuplicate
from app.domain.errors import ErrorCode
from app.domain.history import HistoryEntry
from app.domain.media import Format, FormatOption, MediaInfo, PlaylistEntry, PlaylistInfo
from app.domain.progress import Progress
from app.domain.settings import Language, Settings
from app.domain.task import TaskStatus
from app.services.external import Opened
from app.services.queue import QueueItem
from app.services.updates import AboutInfo, AppUpdateInfo, Component, EngineUpdateResult

COMMANDS = [
    "lookup", "add_to_queue", "get_queue", "cancel_task", "retry_task", "readd_task",
    "remove_task", "clear_finished", "open_task_folder", "list_history", "redownload_history",
    "open_history_folder", "delete_history", "clear_history", "get_settings",
    "update_settings", "choose_download_folder", "check_app_update", "update_engine",
    "get_about", "open_log_file", "open_log_folder", "open_link", "confirm_close", "ping",
]  # fmt: skip
# Arguments that are valid for each command.
ARGS: dict[str, tuple[object, ...]] = {
    "lookup": ("https://youtu.be/x",),
    "add_to_queue": (["https://youtu.be/x"], "mp3", 320),
    "cancel_task": ("t1",), "retry_task": ("t1",), "readd_task": ("t1",),
    "remove_task": ("t1",), "open_task_folder": ("t1",), "redownload_history": ("h1",),
    "open_history_folder": ("h1",), "delete_history": ("h1",),
    "update_settings": ({"maxConcurrent": 2},), "open_link": ("sourceCode",),
}  # fmt: skip

SETTINGS = Settings("C:\\Users\\me\\Downloads")
SETTINGS_JSON = {
    "downloadDir": "C:\\Users\\me\\Downloads",
    "maxConcurrent": 3,
    "onDuplicate": "rename",
    "format": "mp3",
    "mp3Bitrate": 320,
    "mp4Height": 1080,
    "language": "system",
}


class Stage:
    """The bridge with stand-in services, a dialog and a window."""

    def __init__(self) -> None:
        self.media_info, self.queue, self.settings = Mock(), Mock(), Mock()
        self.history, self.updates, self.external = Mock(), Mock(), Mock()
        self.backend = Backend(
            self.media_info, self.queue, self.settings, self.history, self.updates, self.external
        )
        self.queue.items.return_value = []
        self.settings.get.return_value = SETTINGS
        self.events = Mock()
        self.chosen: str | None = None
        self.dialog_opened_at: list[str] = []
        self.closed = 0
        self.api = BridgeApi(self.backend, self.events, self.choose, self.close)

    def choose(self, start: str) -> str | None:
        self.dialog_opened_at.append(start)
        return self.chosen

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def stage() -> Stage:
    return Stage()


def call(stage: Stage, command: str, *args: object) -> object:
    method: Callable[..., object] = getattr(stage.api, command)
    return method(*args)


# ---- what every command shares (section 1)


def test_the_page_sees_exactly_the_commands_of_the_contract(stage: Stage) -> None:
    # pywebview exposes every public attribute, nested ones included.
    public = {name for name in dir(stage.api) if not name.startswith("_")}
    assert public == set(COMMANDS) and len(COMMANDS) == 25


@pytest.mark.parametrize("command", COMMANDS)
def test_no_exception_ever_reaches_the_page(
    stage: Stage, command: str, caplog: pytest.LogCaptureFixture
) -> None:
    class Broken:
        def __getattr__(self, name: str) -> Callable[..., object]:
            def fail(*args: object) -> object:
                raise RuntimeError("a bug")

            return fail

    stage.api._backend = Backend(*(Broken() for _ in range(6)))  # type: ignore[arg-type]
    stage.chosen = "C:\\x"
    stage.close = Mock(side_effect=RuntimeError("a bug"))  # type: ignore[method-assign]
    stage.api._close_window = stage.close
    reply = call(stage, command, *ARGS.get(command, ()))
    if command == "ping":
        assert reply == {"ok": True, "data": "pong"}
    else:
        assert reply == {"ok": False, "error": "unknown"}
        assert f"{command} failed" in caplog.text and "a bug" in caplog.text


@pytest.mark.parametrize("code", list(ErrorCode))
def test_an_engine_error_replies_with_its_code(stage: Stage, code: ErrorCode) -> None:
    stage.media_info.lookup.side_effect = EngineError(code, "raw text")
    assert stage.api.lookup("x") == {"ok": False, "error": code.value}


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("add_to_queue", ("https://youtu.be/x", "mp3", 320)),  # a string, not a list
        ("add_to_queue", ([1], "mp3", 320)),
        ("add_to_queue", (["https://youtu.be/x"], "wav", 320)),
        ("update_settings", (["maxConcurrent"],)),
    ],
)
def test_arguments_the_contract_does_not_allow_are_unknown(
    stage: Stage, command: str, args: tuple[object, ...]
) -> None:
    assert call(stage, command, *args) == {"ok": False, "error": "unknown"}
    stage.queue.add.assert_not_called()
    stage.settings.update.assert_not_called()


# ---- lookup (2.3-2.6, 3.1)


def test_lookup_of_a_video_with_every_field(stage: Stage) -> None:
    stage.media_info.lookup.return_value = MediaInfo(
        "https://www.youtube.com/watch?v=a", "歌", 42, "youtube",
        (FormatOption(Format.MP3, 128, 672000), FormatOption(Format.MP4, 1080, 20111077)),
        channel="頻道", thumb="https://i.ytimg.com/vi/a/maxresdefault.jpg",
    )  # fmt: skip
    assert stage.api.lookup("youtu.be/a") == {
        "ok": True,
        "data": {
            "kind": "video",
            "info": {
                "url": "https://www.youtube.com/watch?v=a",
                "title": "歌",
                "channel": "頻道",
                "durationSec": 42,
                "platform": "youtube",
                "thumb": "https://i.ytimg.com/vi/a/maxresdefault.jpg",
                "options": [
                    {"format": "mp3", "quality": 128, "sizeBytes": 672000},
                    {"format": "mp4", "quality": 1080, "sizeBytes": 20111077},
                ],
            },
        },
    }
    stage.media_info.lookup.assert_called_once_with("youtu.be/a")


def test_lookup_leaves_out_what_has_no_value(stage: Stage) -> None:
    stage.media_info.lookup.return_value = MediaInfo(
        "u", "t", 0, "youtube", (FormatOption(Format.MP4, 720),)
    )
    assert stage.api.lookup("u") == {
        "ok": True,
        "data": {
            "kind": "video",
            "info": {
                "url": "u", "title": "t", "durationSec": 0, "platform": "youtube",
                "options": [{"format": "mp4", "quality": 720}],
            },
        },
    }  # fmt: skip


def test_lookup_of_a_playlist(stage: Stage) -> None:
    stage.media_info.lookup.return_value = PlaylistInfo(
        "https://www.youtube.com/playlist?list=PL",
        "清單",
        "youtube",
        (
            PlaylistEntry("u1", title="一", channel="c", duration_sec=61, thumb="https://t/1"),
            PlaylistEntry("u2", title="沒有時長"),
            PlaylistEntry("u3", available=False),  # private: nothing but the URL
        ),
        channel="c",
    )
    assert stage.api.lookup("x") == {
        "ok": True,
        "data": {
            "kind": "playlist",
            "playlist": {
                "url": "https://www.youtube.com/playlist?list=PL",
                "title": "清單",
                "channel": "c",
                "platform": "youtube",
                "entries": [
                    {"url": "u1", "title": "一", "channel": "c", "durationSec": 61,
                     "thumb": "https://t/1", "available": True},
                    {"url": "u2", "title": "沒有時長", "available": True},
                    {"url": "u3", "available": False},
                ],  # fmt: skip
            },
        },
    }


def test_an_empty_playlist_keeps_its_empty_list(stage: Stage) -> None:
    stage.media_info.lookup.return_value = PlaylistInfo("u", "", "youtube", ())
    reply = stage.api.lookup("u")
    assert reply["data"] == {
        "kind": "playlist",
        "playlist": {"url": "u", "title": "", "platform": "youtube", "entries": []},
    }


# ---- queue (2.7, 3.2)


def test_add_to_queue(stage: Stage) -> None:
    stage.queue.add.return_value = ["a1", "a2"]
    assert stage.api.add_to_queue(["u1", "u2"], "mp4", 1080) == {
        "ok": True,
        "data": {"taskIds": ["a1", "a2"]},
    }
    stage.queue.add.assert_called_once_with(["u1", "u2"], Format.MP4, 1080)


def test_add_to_queue_while_closing_adds_nothing(stage: Stage) -> None:
    stage.queue.add.return_value = []
    assert stage.api.add_to_queue(["u"], "mp3", 128) == {"ok": True, "data": {"taskIds": []}}


@pytest.mark.parametrize(
    ("raised", "code"),
    [(EngineError(ErrorCode.INVALID_URL), "invalidUrl"), (ValueError("quality"), "unknown")],
)
def test_add_to_queue_failures(stage: Stage, raised: Exception, code: str) -> None:
    stage.queue.add.side_effect = raised
    assert stage.api.add_to_queue(["u"], "mp3", 999) == {"ok": False, "error": code}


QUEUE = [
    (QueueItem("f", "u", Format.MP3, 320, TaskStatus.FETCHING),
     {"id": "f", "url": "u", "format": "mp3", "quality": 320, "status": "fetching"}),
    (QueueItem("q", "u", Format.MP4, 1080, TaskStatus.QUEUED, title="t", thumb="https://t"),
     {"id": "q", "url": "u", "format": "mp4", "quality": 1080, "status": "queued",
      "title": "t", "thumb": "https://t"}),
    (QueueItem("d", "u", Format.MP4, 720, TaskStatus.DOWNLOADING, title="t",
               progress=Progress(1000, 12, 8000, 2500.6, 3)),
     {"id": "d", "url": "u", "format": "mp4", "quality": 720, "status": "downloading",
      "title": "t", "percent": 12, "doneBytes": 1000, "totalBytes": 8000, "speedBps": 2501,
      "etaSec": 3}),
    # Downloading without any size known: no percent, no total, no speed, no time left.
    (QueueItem("n", "u", Format.MP3, 128, TaskStatus.DOWNLOADING, title="t",
               progress=Progress(0, None)),
     {"id": "n", "url": "u", "format": "mp3", "quality": 128, "status": "downloading",
      "title": "t", "doneBytes": 0}),
    (QueueItem("r", "u", Format.MP3, 128, TaskStatus.RETRYING, title="t",
               progress=Progress(500, 50, 1000), attempt=2),
     {"id": "r", "url": "u", "format": "mp3", "quality": 128, "status": "retrying",
      "title": "t", "percent": 50, "doneBytes": 500, "totalBytes": 1000, "attempt": 2}),
    (QueueItem("c", "u", Format.MP3, 128, TaskStatus.CONVERTING, title="t"),
     {"id": "c", "url": "u", "format": "mp3", "quality": 128, "status": "converting",
      "title": "t"}),
    (QueueItem("ok", "u", Format.MP3, 128, TaskStatus.DONE, title="t", size_bytes=4096),
     {"id": "ok", "url": "u", "format": "mp3", "quality": 128, "status": "done", "title": "t",
      "sizeBytes": 4096}),
    (QueueItem("s", "u", Format.MP3, 128, TaskStatus.DONE, title="t", size_bytes=10,
               skipped=True),
     {"id": "s", "url": "u", "format": "mp3", "quality": 128, "status": "done", "title": "t",
      "sizeBytes": 10, "skipped": True}),
    (QueueItem("x", "u", Format.MP3, 128, TaskStatus.FAILED, error=ErrorCode.PLAYLIST_URL),
     {"id": "x", "url": "u", "format": "mp3", "quality": 128, "status": "failed",
      "error": "playlistUrl"}),
    (QueueItem("z", "u", Format.MP3, 128, TaskStatus.CANCELLED),
     {"id": "z", "url": "u", "format": "mp3", "quality": 128, "status": "cancelled"}),
]  # fmt: skip


def test_get_queue_flattens_progress_and_leaves_out_what_has_no_value(stage: Stage) -> None:
    stage.queue.items.return_value = [item for item, _ in QUEUE]
    assert stage.api.get_queue() == {"ok": True, "data": [json for _, json in QUEUE]}


def test_get_queue_when_empty(stage: Stage) -> None:
    assert stage.api.get_queue() == {"ok": True, "data": []}


@pytest.mark.parametrize(
    ("command", "method"),
    [("cancel_task", "cancel"), ("retry_task", "retry"), ("readd_task", "readd"),
     ("remove_task", "remove")],
)  # fmt: skip
def test_task_commands_reply_ok_without_data(stage: Stage, command: str, method: str) -> None:
    stage.queue.configure_mock(**{f"{method}.return_value": None})
    assert call(stage, command, "t1") == {"ok": True}
    getattr(stage.queue, method).assert_called_once_with("t1")


def test_clear_finished(stage: Stage) -> None:
    stage.queue.clear_finished.return_value = None
    assert stage.api.clear_finished() == {"ok": True}


@pytest.mark.parametrize("opened", list(Opened))
def test_open_task_folder(stage: Stage, opened: Opened) -> None:
    stage.external.open_task_folder.return_value = opened
    assert stage.api.open_task_folder("t1") == {"ok": True, "data": {"opened": opened.value}}
    stage.external.open_task_folder.assert_called_once_with("t1")


# ---- history (2.9, 3.3)


def test_list_history(stage: Stage) -> None:
    stage.history.list.return_value = [
        HistoryEntry("h2", "u", "新", Format.MP4, 1080, 99, "2026-11-16T01:02:03Z",
                     "data:image/jpeg;base64,AA=="),
        HistoryEntry("h1", "u", "舊", Format.MP3, 320, 5, "2026-11-13T06:20:00Z"),
    ]  # fmt: skip
    assert stage.api.list_history() == {
        "ok": True,
        "data": [
            {"id": "h2", "url": "u", "title": "新", "format": "mp4", "quality": 1080,
             "sizeBytes": 99, "finishedAt": "2026-11-16T01:02:03Z",
             "thumb": "data:image/jpeg;base64,AA=="},
            {"id": "h1", "url": "u", "title": "舊", "format": "mp3", "quality": 320,
             "sizeBytes": 5, "finishedAt": "2026-11-13T06:20:00Z"},
        ],
    }  # fmt: skip


def test_list_history_that_cannot_be_read_is_unknown(stage: Stage) -> None:
    stage.history.list.side_effect = OSError("database is locked")
    assert stage.api.list_history() == {"ok": False, "error": "unknown"}


def test_redownload_history(stage: Stage) -> None:
    stage.history.redownload.return_value = "new"
    assert stage.api.redownload_history("h1") == {"ok": True, "data": {"taskId": "new"}}
    stage.history.redownload.return_value = None
    assert stage.api.redownload_history("gone") == {"ok": True, "data": {}}


def test_open_history_folder(stage: Stage) -> None:
    stage.external.open_history_folder.return_value = Opened.FOLDER
    assert stage.api.open_history_folder("h1") == {"ok": True, "data": {"opened": "folder"}}


def test_delete_and_clear_history(stage: Stage) -> None:
    stage.history.delete.return_value = None
    stage.history.clear.return_value = None
    assert stage.api.delete_history("h1") == {"ok": True}
    stage.history.delete.assert_called_once_with("h1")
    assert stage.api.clear_history() == {"ok": True}


# ---- settings (2.10, 3.4)


def test_get_settings(stage: Stage) -> None:
    assert stage.api.get_settings() == {"ok": True, "data": SETTINGS_JSON}


def test_update_settings_takes_the_contract_names(stage: Stage) -> None:
    changed = Settings("D:\\", 5, OnDuplicate.SKIP, Format.MP4, 128, 2160, Language.EN)
    stage.settings.update.return_value = changed
    changes = {"maxConcurrent": 5, "onDuplicate": "skip", "format": "mp4", "mp3Bitrate": 128,
               "mp4Height": 2160, "language": "en"}  # fmt: skip
    assert stage.api.update_settings(changes) == {
        "ok": True,
        "data": {"downloadDir": "D:\\", **changes},
    }
    stage.settings.update.assert_called_once_with(
        {"max_concurrent": 5, "on_duplicate": "skip", "format": "mp4", "mp3_bitrate": 128,
         "mp4_height": 2160, "language": "en"}  # fmt: skip
    )


@pytest.mark.parametrize("changes", [{"downloadDir": "C:\\"}, {"fooBar": 1}, {"maxConcurrent": 9}])
def test_update_settings_refused_is_unknown(stage: Stage, changes: dict[str, object]) -> None:
    stage.settings.update.side_effect = ValueError("refused")
    assert stage.api.update_settings(changes) == {"ok": False, "error": "unknown"}


def test_choose_download_folder(stage: Stage) -> None:
    stage.chosen = "D:\\Music"
    stage.settings.set_download_dir.return_value = Settings("D:\\Music")
    reply = stage.api.choose_download_folder()
    assert reply == {"ok": True, "data": {**SETTINGS_JSON, "downloadDir": "D:\\Music"}}
    assert stage.dialog_opened_at == [SETTINGS.download_dir]
    stage.settings.set_download_dir.assert_called_once_with("D:\\Music")


def test_choose_download_folder_cancelled_replies_the_settings_as_they_were(stage: Stage) -> None:
    assert stage.api.choose_download_folder() == {"ok": True, "data": SETTINGS_JSON}
    stage.settings.set_download_dir.assert_not_called()


def test_choose_download_folder_that_cannot_be_written_to_is_an_error(stage: Stage) -> None:
    # Decided 2026-11-16 (stage 4 plan, section 1 item 3): the page shows its own message.
    stage.chosen = "C:\\Windows"
    stage.settings.set_download_dir.side_effect = ValueError("cannot be written to")
    assert stage.api.choose_download_folder() == {"ok": False, "error": "unknown"}


# ---- updates and about (2.11-2.13, 3.5)


def test_check_app_update(stage: Stage) -> None:
    stage.updates.check_app_update.return_value = AppUpdateInfo("0.1.0", "0.2.0")
    assert stage.api.check_app_update() == {
        "ok": True,
        "data": {"currentVersion": "0.1.0", "latestVersion": "0.2.0"},
    }
    stage.updates.check_app_update.return_value = AppUpdateInfo("0.1.0")
    assert stage.api.check_app_update() == {"ok": True, "data": {"currentVersion": "0.1.0"}}


def test_update_engine(stage: Stage) -> None:
    stage.updates.update_engine.return_value = EngineUpdateResult(False, "2026.10.26")
    assert stage.api.update_engine() == {
        "ok": True,
        "data": {"updated": False, "version": "2026.10.26"},
    }


@pytest.mark.parametrize("code", [ErrorCode.NETWORK, ErrorCode.UNKNOWN])
def test_update_engine_failures(stage: Stage, code: ErrorCode) -> None:
    stage.updates.update_engine.side_effect = EngineError(code, "raw")
    assert stage.api.update_engine() == {"ok": False, "error": code.value}


def test_get_about(stage: Stage) -> None:
    stage.updates.get_about.return_value = AboutInfo(
        "0.1.0", (Component("yt-dlp", "Unlicense", "2026.10.26"), Component("Deno", "MIT"))
    )
    assert stage.api.get_about() == {
        "ok": True,
        "data": {
            "appVersion": "0.1.0",
            "components": [
                {"name": "yt-dlp", "license": "Unlicense", "version": "2026.10.26"},
                {"name": "Deno", "license": "MIT"},
            ],
        },
    }


# ---- outside the app (3.6)


@pytest.mark.parametrize("command", ["open_log_file", "open_log_folder"])
def test_open_log(stage: Stage, command: str) -> None:
    method = getattr(stage.external, command)
    method.return_value = None
    assert call(stage, command) == {"ok": True}
    method.side_effect = OSError("no program for .log")
    assert call(stage, command) == {"ok": False, "error": "unknown"}


def test_open_link(stage: Stage) -> None:
    stage.external.open_link.return_value = None
    assert stage.api.open_link("releasePage") == {"ok": True}
    stage.external.open_link.side_effect = ValueError("not a link we know")
    assert stage.api.open_link("https://evil.example") == {"ok": False, "error": "unknown"}


def test_ping(stage: Stage) -> None:
    assert stage.api.ping() == {"ok": True, "data": "pong"}


def test_a_failure_is_logged_with_its_reason(
    stage: Stage, caplog: pytest.LogCaptureFixture
) -> None:
    stage.settings.update.side_effect = ValueError("'fooBar' is not a setting")
    with caplog.at_level(logging.INFO):
        stage.api.update_settings({"fooBar": 1})
        stage.media_info.lookup.side_effect = EngineError(ErrorCode.PRIVATE, "Private")
        stage.api.lookup("u")
    assert "update_settings failed" in caplog.text and "fooBar" in caplog.text
    assert "lookup failed: private: Private" in caplog.text


# ---- closing the window (section 4, closeRequested)


def running(stage: Stage, *statuses: TaskStatus) -> None:
    stage.queue.items.return_value = [
        QueueItem(str(i), "u", Format.MP3, 128, status) for i, status in enumerate(statuses)
    ]


@pytest.mark.parametrize(
    "statuses",
    [(), (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)],
)
def test_closing_with_nothing_running_closes_at_once(
    stage: Stage, statuses: tuple[TaskStatus, ...]
) -> None:
    running(stage, *statuses)
    assert stage.api._on_closing() is True
    stage.events.close.assert_called_once()
    stage.events.emit.assert_not_called()


@pytest.mark.parametrize(
    "status", [s for s in TaskStatus if s not in (TaskStatus.DONE, TaskStatus.FAILED,
                                                  TaskStatus.CANCELLED)]
)  # fmt: skip
def test_closing_while_a_task_runs_asks_the_page(stage: Stage, status: TaskStatus) -> None:
    running(stage, TaskStatus.DONE, status)
    assert stage.api._on_closing() is False
    stage.events.emit.assert_called_once_with(shapes.CloseRequested())
    stage.events.close.assert_not_called()


def test_confirm_close_closes_and_the_window_then_goes(stage: Stage) -> None:
    running(stage, TaskStatus.DOWNLOADING)
    assert stage.api.confirm_close() == {"ok": True}
    assert stage.closed == 1
    assert stage.api._on_closing() is True  # what closing the window calls next
    stage.events.close.assert_called_once()


def test_closing_when_the_queue_cannot_be_read_still_closes(stage: Stage) -> None:
    stage.queue.items.side_effect = RuntimeError("a bug")
    assert stage.api._on_closing() is True
