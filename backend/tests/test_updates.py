"""UpdateService with a fake engine, a fake clock and a fake "ask GitHub". No network."""

import pytest
from fake_engine import FakeEngine
from fakes import MemoryFile

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.services.updates import (
    FAILED_TTL,
    FOUND_TTL,
    AboutInfo,
    AppUpdateInfo,
    Component,
    EngineUpdateResult,
    UpdateService,
    parse_version,
)


class Box:
    def __init__(self, current: str = "1.2.3", latest: str | Exception = "v1.2.3") -> None:
        self.engine = FakeEngine()
        self.latest = latest
        self.asked = 0
        self.now = 1_000_000.0
        self.cache = MemoryFile()
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
        ("1.2.3", "v1.2.4-beta.1", None),  # not a release number we understand
        ("1.2.3", "v1.3", None),
        ("1.2.3", "latest", None),
        ("1.2.3", "", None),
        ("dev", "v9.9.9", None),  # our own version is not understood: say nothing
    ],
)
def test_only_a_higher_release_number_is_a_new_version(
    current: str, latest: str, newer: str | None
) -> None:
    assert Box(current, latest).service.check_app_update() == AppUpdateInfo(current, newer)


def test_parse_version() -> None:
    assert parse_version("v1.2.3") == parse_version(" 1.2.3\n") == (1, 2, 3)
    assert parse_version("v01.002.3") == (1, 2, 3)
    for bad in ("1.2", "1.2.3.4", "v1.2.x", "V1.2.3", "1.2.3-rc1", "-1.2.3", ""):
        assert parse_version(bad) is None


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
