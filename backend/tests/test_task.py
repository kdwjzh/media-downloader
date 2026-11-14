from collections.abc import Callable

import pytest

from app.domain.errors import RETRYABLE, ErrorCode, InvalidTransition
from app.domain.media import Format
from app.domain.task import FINISHED, TRANSITIONS, DownloadTask, TaskStatus

S = TaskStatus


def make(status: TaskStatus, format: Format | None = None, title: str | None = "t") -> DownloadTask:
    """A task driven to `status` through legal steps only."""
    if format is None:
        format = Format.MP4 if status is S.MERGING else Format.MP3
    if status is S.FETCHING:
        title = None
    quality = 320 if format is Format.MP3 else 1080
    task = DownloadTask("id1", "https://example.com/v", format, quality, title)
    if status in (S.FETCHING, S.QUEUED):
        return task
    if status is S.CANCELLED:
        task.cancel()
        return task
    task.start()
    task.report_progress(0, 1, 50, 100, 10.0)
    if status is S.RETRYING:
        task.connection_lost(1)
    elif status in (S.CONVERTING, S.MERGING):
        task.begin_post_processing()
    elif status is S.DONE:
        task.complete(100)
    elif status is S.FAILED:
        task.fail(ErrorCode.NETWORK)
    assert task.status is status
    return task


ACTIONS: dict[str, Callable[[DownloadTask], None]] = {
    "info_resolved": lambda t: t.info_resolved("title", "thumb"),
    "start": lambda t: t.start(),
    "report_progress": lambda t: t.report_progress(0, 1, 60, 100),
    "connection_lost": lambda t: t.connection_lost(2),
    "begin_post_processing": lambda t: t.begin_post_processing(),
    "complete": lambda t: t.complete(123),
    "skip": lambda t: t.skip(),
    "fail": lambda t: t.fail(ErrorCode.UNKNOWN),
    "cancel": lambda t: t.cancel(),
    "retry": lambda t: t.retry(),
    "readd": lambda t: t.readd(),
}

# action -> {status before: status after}. Every pair not listed must raise.
LEGAL: dict[str, dict[TaskStatus, TaskStatus]] = {
    "info_resolved": {S.FETCHING: S.QUEUED},
    "start": {S.QUEUED: S.DOWNLOADING},
    "report_progress": {S.DOWNLOADING: S.DOWNLOADING, S.RETRYING: S.DOWNLOADING},
    "connection_lost": {S.DOWNLOADING: S.RETRYING, S.RETRYING: S.RETRYING},
    "begin_post_processing": {S.DOWNLOADING: S.CONVERTING},
    "complete": {S.DOWNLOADING: S.DONE, S.CONVERTING: S.DONE, S.MERGING: S.DONE},
    "skip": {S.QUEUED: S.DONE, S.DOWNLOADING: S.DONE},
    "fail": {s: S.FAILED for s in (S.FETCHING, S.DOWNLOADING, S.RETRYING, S.CONVERTING, S.MERGING)},
    "cancel": {
        s: S.CANCELLED
        for s in (S.FETCHING, S.QUEUED, S.DOWNLOADING, S.RETRYING, S.CONVERTING, S.MERGING)
    },
    "retry": {S.FAILED: S.QUEUED},
    "readd": {S.CANCELLED: S.QUEUED},
}

MATRIX = [(action, status) for action in ACTIONS for status in S]


@pytest.mark.parametrize(("action", "before"), MATRIX)
def test_every_action_from_every_status(action: str, before: TaskStatus) -> None:
    task = make(before)
    after = LEGAL[action].get(before)
    if after is None:
        with pytest.raises(InvalidTransition):
            ACTIONS[action](task)
        assert task.status is before
    else:
        ACTIONS[action](task)
        assert task.status is after


def test_the_tests_cover_exactly_the_transition_table() -> None:
    covered = {(b, a) for moves in LEGAL.values() for b, a in moves.items() if a is not b}
    # Covered by the dedicated tests below.
    covered |= {(S.DOWNLOADING, S.MERGING), (S.FAILED, S.FETCHING), (S.CANCELLED, S.FETCHING)}
    assert covered == {(b, a) for b, targets in TRANSITIONS.items() for a in targets}


def test_new_task_waits_for_a_slot_when_its_title_is_known() -> None:
    assert make(S.QUEUED).status is S.QUEUED


def test_new_task_looks_up_info_when_only_the_url_is_known() -> None:
    assert DownloadTask("a", "u", Format.MP3, 320).status is S.FETCHING


def test_quality_must_belong_to_the_format() -> None:
    with pytest.raises(ValueError):
        DownloadTask("a", "u", Format.MP3, 1080)


def test_mp4_post_processing_is_merging() -> None:
    task = make(S.DOWNLOADING, Format.MP4)
    task.begin_post_processing()
    assert task.status is S.MERGING


def test_lookup_failure_can_be_retried_and_looks_up_again() -> None:
    task = make(S.FETCHING)
    task.fail(ErrorCode.NETWORK)
    task.retry()
    assert task.status is S.FETCHING
    assert task.error is None


def test_task_cancelled_during_lookup_is_readded_as_a_lookup() -> None:
    task = make(S.FETCHING)
    task.cancel()
    task.readd()
    assert task.status is S.FETCHING


@pytest.mark.parametrize("error", [e for e in ErrorCode if e not in RETRYABLE])
def test_errors_that_cannot_succeed_are_not_retried(error: ErrorCode) -> None:
    task = make(S.DOWNLOADING)
    task.fail(error)
    with pytest.raises(InvalidTransition):
        task.retry()
    assert task.status is S.FAILED


def test_skip_is_done_with_a_flag_and_no_size() -> None:
    task = make(S.QUEUED)
    task.skip()
    assert (task.status, task.skipped, task.size_bytes) == (S.DONE, True, None)


def test_complete_records_the_file_size() -> None:
    task = make(S.CONVERTING)
    task.complete(1234)
    assert (task.size_bytes, task.skipped, task.is_finished) == (1234, False, True)


def test_finished_statuses() -> None:
    assert {s for s in S if make(s).is_finished} == FINISHED == {S.DONE, S.FAILED, S.CANCELLED}


def test_download_starts_at_zero_percent() -> None:
    task = make(S.QUEUED)
    task.start()
    assert task.progress is not None
    assert (task.progress.percent, task.progress.done_bytes) == (0, 0)


def test_retrying_keeps_the_percentage_but_drops_speed_and_eta() -> None:
    task = make(S.RETRYING)
    assert task.attempt == 1
    assert task.progress is not None
    p = task.progress
    assert (p.percent, p.speed_bps, p.eta_sec) == (50, None, None)
    task.connection_lost(2)
    assert task.attempt == 2


def test_progress_after_a_retry_resumes_the_download() -> None:
    task = make(S.RETRYING)
    task.report_progress(0, 1, 60, 100)
    assert task.status is S.DOWNLOADING
    assert task.attempt is None
    assert task.progress is not None and task.progress.percent == 60


@pytest.mark.parametrize("status", [S.CONVERTING, S.MERGING, S.DONE, S.FAILED, S.CANCELLED])
def test_progress_numbers_disappear_once_downloading_is_over(status: TaskStatus) -> None:
    task = make(status)
    assert task.progress is None
    assert task.attempt is None


def test_a_retried_download_starts_from_zero_again() -> None:
    task = make(S.FAILED)
    task.retry()
    task.start()
    task.report_progress(0, 1, 10, 100)
    assert task.progress is not None and task.progress.percent == 10


def test_file_sizes_known_in_advance_feed_the_percentage() -> None:
    task = make(S.QUEUED, Format.MP4)
    task.start()
    task.expect_file_sizes([900, 100])
    task.report_progress(0, 2, 450)
    assert task.progress is not None and task.progress.percent == 45
    with pytest.raises(InvalidTransition):
        make(S.QUEUED).expect_file_sizes([1])
