"""AppUpdateService with a fake installer store, a fake clock and work run on the test's own
thread (each step pushed by the test). No network, no installer is started."""

import hashlib
from collections.abc import Callable

import pytest

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.services.updates import (
    PROGRESS_INTERVAL,
    AppUpdateChanged,
    AppUpdateInfo,
    AppUpdateService,
    AppUpdateStatus,
    Stage,
    parse_checksum,
)

INSTALLER = b"installer bytes" * 1000
DIGEST = hashlib.sha256(INSTALLER).hexdigest()
NAME = "MediaDownloader-Setup-1.0.0-rc.2.exe"


class FakeStore:
    def __init__(self) -> None:
        self.checksum = f"{DIGEST}  {NAME}\n"
        self.content = INSTALLER
        self.chunks = 4
        self.fail_download: Exception | None = None
        self.fail_checksum: Exception | None = None
        self.fail_launch: Exception | None = None
        self.on_chunk: Callable[[int], None] = lambda index: None
        self.part: bytes | None = None
        self.accepted: bytes | None = None
        self.launched: list[str] = []
        self.discarded = 0

    def expected_name(self, version: str) -> str:
        return f"MediaDownloader-Setup-{version}.exe"

    def checksum_text(self, version: str) -> str:
        if self.fail_checksum:
            raise self.fail_checksum
        return self.checksum

    def download(
        self,
        version: str,
        on_progress: Callable[[int, int | None], None],
        cancelled: Callable[[], bool],
    ) -> tuple[int, str] | None:
        if self.fail_download:
            raise self.fail_download
        self.part = b""
        size = len(self.content)
        step = size // self.chunks + 1
        for index in range(self.chunks):
            self.on_chunk(index)
            if cancelled():
                self.part = None
                return None
            self.part += self.content[index * step : (index + 1) * step]
            on_progress(len(self.part), size)
        return len(self.part), hashlib.sha256(self.part).hexdigest()

    def accept(self, version: str) -> None:
        self.accepted, self.part = self.part, None

    def digest(self, version: str) -> tuple[int, str]:
        assert self.accepted is not None
        return len(self.accepted), hashlib.sha256(self.accepted).hexdigest()

    def launch(self, version: str) -> None:
        if self.fail_launch:
            raise self.fail_launch
        self.launched.append(version)

    def discard(self) -> None:
        self.discarded += 1
        self.part = self.accepted = None


class Box:
    def __init__(self, latest: str | None = "1.0.0-rc.2", run_now: bool = True) -> None:
        self.store = FakeStore()
        self.latest = latest
        self.events: list[AppUpdateStatus] = []
        self.now = 100.0
        self.pending: list[Callable[[], None]] = []
        self.service = AppUpdateService(
            lambda: AppUpdateInfo("1.0.0-rc.1", self.latest),
            self.store,
            self.emit,
            lambda: self.now,
            (lambda work: work()) if run_now else self.pending.append,
        )

    def emit(self, event: AppUpdateChanged) -> None:
        self.events.append(event.status)

    def stages(self) -> list[Stage]:
        return [status.stage for status in self.events]


# ---- the checksum file


@pytest.mark.parametrize(
    ("text", "found"),
    [
        (f"{DIGEST}  {NAME}\n", DIGEST),
        (f"{DIGEST.upper()} *{NAME}", DIGEST),  # binary-mode marker, upper case
        (f"{DIGEST} {NAME}", DIGEST),
        (f"{DIGEST}  MediaDownloader-Setup-1.0.0-rc.1.exe", None),  # another file
        (f"{DIGEST[:-1]}  {NAME}", None),  # too short
        (f"{DIGEST}x  {NAME}", None),
        (f"{DIGEST}", None),  # no name
        (f"{DIGEST}  {NAME}\n{DIGEST}  other.exe", None),  # more than one line
        ("<html>Not Found</html>", None),
        ("", None),
        (f"{DIGEST}  {NAME}" + " " * 2000, None),  # longer than a checksum file can be
    ],
)
def test_parse_checksum(text: str, found: str | None) -> None:
    assert parse_checksum(text, NAME) == found


# ---- downloading and checking


def test_a_good_download_becomes_ready_and_installs() -> None:
    box = Box()
    box.now = 0.0
    assert box.service.start() == AppUpdateStatus(Stage.DOWNLOADING, 0)
    assert box.stages()[0] is Stage.DOWNLOADING
    assert box.stages()[-2:] == [Stage.VERIFYING, Stage.READY]
    assert box.store.accepted == INSTALLER
    assert box.service.info().status == AppUpdateStatus(Stage.READY)
    assert box.service.install() is True
    assert box.store.launched == ["1.0.0-rc.2"]
    assert box.stages()[-2:] == [Stage.VERIFYING, Stage.INSTALLING]


def test_progress_is_sent_at_most_every_half_second() -> None:
    box = Box()
    box.store.chunks = 4
    box.store.on_chunk = lambda index: setattr(box, "now", box.now + PROGRESS_INTERVAL / 2)
    box.service.start()
    downloading = [s for s in box.events if s.stage is Stage.DOWNLOADING]
    # The first value (0) plus every second chunk: the others came too early and were dropped.
    assert [s.received_bytes for s in downloading][0] == 0
    assert len(downloading) == 3
    assert all(s.total_bytes == len(INSTALLER) for s in downloading[1:])


def test_without_a_newer_version_nothing_starts() -> None:
    box = Box(latest=None)
    assert box.service.start() == AppUpdateStatus(Stage.IDLE)
    assert box.events == [] and box.store.part is None
    assert box.service.info() == AppUpdateInfo("1.0.0-rc.1")


def test_starting_twice_does_one_download() -> None:
    box = Box(run_now=False)
    box.service.start()
    assert box.service.start() == AppUpdateStatus(Stage.DOWNLOADING, 0)
    assert len(box.pending) == 1


def test_a_checksum_that_does_not_match_never_installs() -> None:
    box = Box()
    box.store.checksum = f"{'0' * 64}  {NAME}"
    box.service.start()
    assert box.events[-1] == AppUpdateStatus(Stage.FAILED, error=ErrorCode.CHECKSUM_MISMATCH)
    assert box.store.accepted is None and box.store.part is None and box.store.discarded
    assert box.service.install() is False
    assert box.store.launched == []


@pytest.mark.parametrize("text", ["<html>404</html>", f"{DIGEST}  other.exe", ""])
def test_a_checksum_file_that_cannot_be_read_never_installs(text: str) -> None:
    box = Box()
    box.store.checksum = text
    box.service.start()
    assert box.events[-1].error is ErrorCode.CHECKSUM_MISMATCH
    assert box.store.part is None  # not even downloaded
    assert box.service.install() is False


def test_an_incomplete_download_never_installs() -> None:
    box = Box()
    box.store.content = INSTALLER[:-100]  # the server stopped early without saying so
    box.service.start()
    assert box.events[-1].error is ErrorCode.CHECKSUM_MISMATCH
    assert box.service.install() is False


@pytest.mark.parametrize(
    ("where", "code"),
    [
        ("download", ErrorCode.NETWORK),
        ("download", ErrorCode.UNKNOWN),
        ("checksum", ErrorCode.NETWORK),
        ("checksum", ErrorCode.UNKNOWN),
    ],
)
def test_a_failed_step_says_why_and_can_be_retried(where: str, code: ErrorCode) -> None:
    box = Box()
    setattr(box.store, f"fail_{where}", EngineError(code, "x"))
    box.service.start()
    assert box.events[-1] == AppUpdateStatus(Stage.FAILED, error=code)
    assert box.service.info().status == AppUpdateStatus(Stage.FAILED, error=code)
    assert box.store.discarded
    setattr(box.store, f"fail_{where}", None)
    box.service.start()  # retry
    assert box.stages()[-1] is Stage.READY


def test_a_bug_in_a_step_is_unknown_not_a_crash(caplog: pytest.LogCaptureFixture) -> None:
    box = Box()
    box.store.fail_download = KeyError("bug")
    box.service.start()
    assert box.events[-1].error is ErrorCode.UNKNOWN
    assert "app update failed" in caplog.text


def test_cancelling_a_download_leaves_nothing_behind() -> None:
    box = Box(run_now=False)
    def cancel_at_third_chunk(index: int) -> None:
        if index == 2:
            box.service.cancel()

    box.store.on_chunk = cancel_at_third_chunk
    box.service.start()
    box.pending.pop()()  # the worker runs and notices the cancel
    assert box.events[-1] == AppUpdateStatus(Stage.IDLE)
    assert box.store.part is None and box.store.accepted is None and box.store.discarded
    assert box.service.info().status is None


def test_a_cancelled_worker_sends_nothing_more_and_a_new_start_waits_for_it() -> None:
    box = Box(run_now=False)
    box.service.start()
    first = box.pending.pop()
    box.service.cancel()
    box.service.start()
    second = box.pending.pop()
    first()  # the cancelled one ends without a word
    assert box.stages() == [Stage.DOWNLOADING, Stage.IDLE, Stage.DOWNLOADING]
    second()
    assert box.stages()[-1] is Stage.READY


def test_cancel_is_too_late_once_ready_or_installing() -> None:
    box = Box()
    box.service.start()
    box.service.cancel()
    assert box.stages()[-1] is Stage.READY


# ---- installing


def test_installing_without_a_ready_update_does_nothing() -> None:
    box = Box(run_now=False)
    assert box.service.install() is False
    box.service.start()
    assert box.service.install() is False  # still downloading
    assert box.store.launched == []


def test_an_installer_changed_on_the_disk_is_not_started() -> None:
    box = Box()
    box.service.start()
    box.store.accepted = b"something else"
    with pytest.raises(EngineError) as raised:
        box.service.install()
    assert raised.value.code is ErrorCode.CHECKSUM_MISMATCH
    assert box.store.launched == [] and box.store.discarded
    assert box.events[-1] == AppUpdateStatus(Stage.FAILED, error=ErrorCode.CHECKSUM_MISMATCH)


def test_an_installer_that_will_not_start_fails_and_the_app_stays_open() -> None:
    box = Box()
    box.service.start()
    box.store.fail_launch = OSError("blocked by antivirus")
    with pytest.raises(EngineError) as raised:
        box.service.install()
    assert raised.value.code is ErrorCode.UNKNOWN
    assert box.events[-1] == AppUpdateStatus(Stage.FAILED, error=ErrorCode.UNKNOWN)
    assert box.service.install() is False


def test_clean_at_start_deletes_old_downloads_and_never_raises() -> None:
    box = Box()

    def broken() -> None:
        raise OSError("in use")

    box.store.discard = broken  # type: ignore[method-assign]
    box.service.clean()
