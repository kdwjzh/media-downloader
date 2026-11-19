"""UpdateService with a fake engine, a fake clock and a fake "ask GitHub". No network."""

import pytest
from fake_engine import FakeEngine
from fakes import MemoryFile

from app.domain import version
from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.services.updates import (
    ENGINE_CHECKED_TTL,
    ENGINE_FAILED_TTL,
    FAILED_TTL,
    FOUND_TTL,
    AboutInfo,
    AppUpdateInfo,
    Component,
    EngineUpdateResult,
    UpdateService,
)


class Box:
    def __init__(self, current: str = "1.2.3", latest: str | Exception = "v1.2.3") -> None:
        self.engine = FakeEngine()
        self.latest = latest
        self.asked = 0
        self.now = 1_000_000.0
        self.cache = MemoryFile()
        self.engine_cache = MemoryFile()
        self.reads = 0
        self.service = self.open(current)

    def open(self, current: str) -> UpdateService:
        """A service on the same cache file, as after a restart."""
        return UpdateService(
            self.engine,
            current,
            self.ask,
            self.cache,
            [
                (Component("Engine", "Unlicense"), lambda: self.engine.version()),
                (Component("Tool", "MIT"), self.tool_version),
                (Component("Broken", "MIT"), self.broken),
                (Component("Font", "OFL-1.1"), None),
            ],
            self.engine_cache,
            lambda: self.now,
        )

    def ask(self) -> str:
        self.asked += 1
        if isinstance(self.latest, Exception):
            raise self.latest
        return self.latest

    def tool_version(self) -> str | None:
        self.reads += 1
        return "2.9.8"

    def broken(self) -> str | None:
        raise EngineError(ErrorCode.UNKNOWN, "not found")


@pytest.mark.parametrize(
    ("current", "latest", "newer"),
    [
        ("1.2.3", "v1.2.4", "1.2.4"),
        ("1.2.3", "1.3.0", "1.3.0"),
        ("1.9.0", "v1.10.0", "1.10.0"),  # numbers, not text
        ("0.9.9", "v1.0.0", "1.0.0"),
        ("1.2.3", "v1.2.3", None),
        ("1.2.3", "v1.2.2", None),
        ("1.10.0", "v1.9.9", None),
        ("2.0.0", "v1.99.99", None),
        ("1.2.3", "v1.2.4-beta.1", "1.2.4-beta.1"),  # a pre-release of a newer version
        ("1.0.0-rc.1", "v1.0.0-rc.2", "1.0.0-rc.2"),
        ("1.0.0-rc.2", "v1.0.0", "1.0.0"),
        ("1.0.0-rc.9", "v1.0.0-rc.10", "1.0.0-rc.10"),  # numbers, not text
        ("1.0.0-rc.2", "v1.0.0-rc.1", None),
        ("1.0.0", "v1.0.0-rc.9", None),  # the release is newer than its pre-releases
        ("1.0.0-rc.1", "v1.0.0-rc.1+build.5", None),  # build metadata does not count
        ("1.2.3", "v1.2.4+build.5", "1.2.4"),  # and is not shown or used in addresses
        ("1.2.3", "v1.3", None),
        ("1.2.3", "v01.3.0", None),  # leading zeros are not SemVer
        ("1.2.3", "v1.3.0-", None),
        ("1.2.3", "v1.3.0-rc.01", None),
        ("1.2.3", "latest", None),
        ("1.2.3", "", None),
        ("dev", "v9.9.9", None),  # our own version is not understood: say nothing
    ],
)
def test_only_a_higher_release_number_is_a_new_version(
    current: str, latest: str, newer: str | None
) -> None:
    assert Box(current, latest).service.check_app_update() == AppUpdateInfo(current, newer)


def test_versions_sort_like_the_semver_example() -> None:
    ordered = [
        "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2",
        "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0", "1.0.1", "1.1.0", "2.0.0",
    ]  # fmt: skip
    keys = [version.parse(v) for v in ordered]
    assert None not in keys
    assert keys == sorted(keys)  # type: ignore[type-var]
    assert len(set(keys)) == len(keys)


def test_what_is_not_a_version() -> None:
    assert version.parse("v1.2.3") == version.parse(" 1.2.3\n")
    bad_ones = ("1.2", "1.2.3.4", "v1.2.x", "V1.2.3", "-1.2.3", "", "01.2.3", "1.2.3-",
                "1.2.3-a..b", "1.2.3-é", "1.2.3+", "../1.2.3", "1.2.3/x", "1 2.3")  # fmt: skip
    for bad in bad_ones:
        assert version.parse(bad) is None, bad
        assert version.plain(bad) is None
    assert version.plain("v1.0.0-rc.1+build.7") == "1.0.0-rc.1"


@pytest.mark.parametrize(
    "problem", [OSError("no network"), ValueError("HTTP 404: a private repository"), KeyError("x")]
)
def test_when_it_cannot_be_checked_there_is_no_new_version(problem: Exception) -> None:
    box = Box(latest=problem)
    assert box.service.check_app_update() == AppUpdateInfo("1.2.3")


def test_a_cache_file_that_cannot_be_read_or_written_is_no_error() -> None:
    box = Box(latest="v2.0.0")
    box.cache.data = {"checked_at": "yesterday", "latest": 5}
    box.cache.fail = True
    assert box.service.check_app_update().latest_version == "2.0.0"


def test_an_answer_is_kept_for_a_day_also_across_restarts() -> None:
    box = Box(latest="v1.3.0")
    assert box.service.check_app_update().latest_version == "1.3.0"
    box.latest = "v1.4.0"
    box.now += FOUND_TTL - 1
    assert box.open("1.2.3").check_app_update().latest_version == "1.3.0"
    assert box.asked == 1
    box.now += 1
    assert box.service.check_app_update().latest_version == "1.4.0"
    assert box.asked == 2


def test_after_installing_the_new_version_the_kept_answer_says_nothing_new() -> None:
    box = Box(latest="v1.3.0")
    box.service.check_app_update()
    assert box.open("1.3.0").check_app_update() == AppUpdateInfo("1.3.0")
    assert box.asked == 1


def test_a_failed_check_is_tried_again_after_an_hour_not_at_once() -> None:
    box = Box(latest=OSError("no network"))
    box.service.check_app_update()
    box.latest = "v1.3.0"
    box.now += FAILED_TTL - 1
    assert box.service.check_app_update().latest_version is None
    assert box.asked == 1
    box.now += 1
    assert box.service.check_app_update().latest_version == "1.3.0"
    assert box.asked == 2


def test_a_clock_that_was_set_back_does_not_keep_an_answer_forever() -> None:
    box = Box(latest="v1.3.0")
    box.service.check_app_update()
    box.now -= 10 * FOUND_TTL
    box.service.check_app_update()
    assert box.asked == 2


def test_update_engine_reports_what_the_engine_did() -> None:
    box = Box()
    assert box.service.update_engine() == EngineUpdateResult(False, "fake")
    box.engine.update = lambda: True  # type: ignore[method-assign]
    box.engine.version = lambda: "2026.11.01"  # type: ignore[method-assign]
    assert box.service.update_engine() == EngineUpdateResult(True, "2026.11.01")


def test_a_failed_engine_update_keeps_its_code_and_logs_the_raw_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    box = Box()

    def fail() -> bool:
        raise EngineError(ErrorCode.NETWORK, "ERROR: Unable to obtain version info")

    box.engine.update = fail  # type: ignore[method-assign]
    with pytest.raises(EngineError) as raised:
        box.service.update_engine()
    assert raised.value.code is ErrorCode.NETWORK
    assert "Unable to obtain version info" in caplog.text


def test_about_lists_every_component_and_reads_versions_once() -> None:
    box = Box()
    about = box.service.get_about()
    assert about == AboutInfo(
        "1.2.3",
        (
            Component("Engine", "Unlicense", "fake"),
            Component("Tool", "MIT", "2.9.8"),
            Component("Broken", "MIT", None),  # unreadable: listed without a version
            Component("Font", "OFL-1.1", None),
        ),
    )
    assert box.service.get_about() is about and box.reads == 1
    box.engine.version = lambda: "newer"  # type: ignore[method-assign]
    box.service.update_engine()
    assert box.service.get_about().components[0].version == "newer"  # read again after an update


# ---- updating the engine at start (ADR 0019)


def test_the_engine_updates_itself_at_the_first_start() -> None:
    box = Box()
    calls: list[str] = []

    def update() -> bool:
        calls.append("update")
        return True

    box.engine.update = update  # type: ignore[method-assign]
    box.service.auto_update_engine()
    assert calls == ["update"]
    assert box.engine_cache.data == {"checked_at": box.now, "ok": True}


def test_the_engine_is_checked_once_a_day() -> None:
    box = Box()
    calls: list[str] = []

    def update() -> bool:
        calls.append("update")
        return False

    box.engine.update = update  # type: ignore[method-assign]
    box.service.auto_update_engine()
    box.now += ENGINE_CHECKED_TTL - 1
    box.open("1.2.3").auto_update_engine()  # a restart
    assert calls == ["update"]
    box.now += 1
    box.service.auto_update_engine()
    assert calls == ["update", "update"]


def test_a_failed_engine_check_is_tried_again_after_an_hour_and_never_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    box = Box()
    calls: list[str] = []

    def fail() -> bool:
        calls.append("update")
        raise EngineError(ErrorCode.NETWORK, "offline")

    box.engine.update = fail  # type: ignore[method-assign]
    box.service.auto_update_engine()
    assert box.engine_cache.data == {"checked_at": box.now, "ok": False}
    assert "could not update the engine at start" in caplog.text
    box.now += ENGINE_FAILED_TTL - 1
    box.service.auto_update_engine()
    assert calls == ["update"]
    box.now += 1
    box.service.auto_update_engine()
    assert calls == ["update", "update"]


def test_a_broken_engine_cache_is_no_error() -> None:
    box = Box()
    box.engine_cache.data = {"checked_at": "soon", "ok": "yes"}
    box.engine_cache.fail = True
    box.service.auto_update_engine()  # reads nothing usable, updates, cannot save: no raise


def test_the_about_list_waits_for_an_update_that_is_running() -> None:
    import threading

    box = Box()
    started, release = threading.Event(), threading.Event()

    def slow_update() -> bool:
        started.set()
        release.wait(5)
        box.engine.version = lambda: "new"  # type: ignore[method-assign]
        return True

    box.engine.update = slow_update  # type: ignore[method-assign]
    updater = threading.Thread(target=box.service.auto_update_engine)
    updater.start()
    assert started.wait(5)
    versions: list[str | None] = []
    reader = threading.Thread(
        target=lambda: versions.append(box.service.get_about().components[0].version)
    )
    reader.start()
    reader.join(0.2)
    assert reader.is_alive()  # waiting, not reading the old version
    release.set()
    updater.join(5)
    reader.join(5)
    assert versions == ["new"]
