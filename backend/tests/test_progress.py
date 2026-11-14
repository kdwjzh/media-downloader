import pytest

from app.domain.progress import ProgressTracker


def test_single_file_percent_is_bytes_over_total() -> None:
    p = ProgressTracker().update(0, 1, 250, 1000, speed_bps=50.0)
    assert (p.percent, p.done_bytes, p.total_bytes, p.eta_sec) == (25, 250, 1000, 15)


def test_percent_never_goes_down() -> None:
    tracker = ProgressTracker()
    assert tracker.update(0, 1, 600, 1000).percent == 60
    # yt-dlp can restart a fragment, or revise an estimated total upwards.
    assert tracker.update(0, 1, 300, 1000).percent == 60
    assert tracker.update(0, 1, 700, 2000).percent == 60
    assert tracker.update(0, 1, 1400, 2000).percent == 70


def test_percent_is_capped_at_100_when_the_estimate_was_too_small() -> None:
    assert ProgressTracker().update(0, 1, 1200, 1000).percent == 100


def test_mp4_with_known_sizes_runs_from_0_to_100_once() -> None:
    tracker = ProgressTracker()
    tracker.expect([900, 100])
    seen = [
        tracker.update(0, 2, 0, 900).percent,
        tracker.update(0, 2, 450, 900).percent,
        tracker.update(0, 2, 900, 900).percent,
        # The audio file's byte count starts again from zero.
        tracker.update(1, 2, 0, 100).percent,
        tracker.update(1, 2, 50, 100).percent,
        tracker.update(1, 2, 100, 100).percent,
    ]
    assert seen == [0, 45, 90, 90, 95, 100]


def test_mp4_totals_are_the_sum_of_both_files() -> None:
    tracker = ProgressTracker()
    tracker.expect([900, 100])
    p = tracker.update(1, 2, 50, 100, speed_bps=10.0)
    assert (p.done_bytes, p.total_bytes, p.eta_sec) == (950, 1000, 5)


def test_unknown_second_file_gives_each_file_an_equal_share() -> None:
    tracker = ProgressTracker()
    first = tracker.update(0, 2, 450, 900, speed_bps=10.0)
    assert (first.percent, first.total_bytes, first.eta_sec) == (25, None, None)
    assert tracker.update(0, 2, 900, 900).percent == 50
    # Once the audio size arrives every size is known; the bar must not jump back.
    second = tracker.update(1, 2, 50, 100)
    assert (second.percent, second.total_bytes) == (95, 1000)


def test_no_size_at_all_means_no_percent_but_bytes_and_speed_remain() -> None:
    p = ProgressTracker().update(0, 1, 4096, None, speed_bps=100.0)
    assert (p.percent, p.total_bytes, p.eta_sec) == (None, None, None)
    assert (p.done_bytes, p.speed_bps) == (4096, 100.0)


def test_zero_size_is_treated_as_unknown() -> None:
    assert ProgressTracker().update(0, 1, 10, 0).percent is None


def test_no_eta_without_speed() -> None:
    assert ProgressTracker().update(0, 1, 10, 100).eta_sec is None
    assert ProgressTracker().update(0, 1, 10, 100, speed_bps=0.0).eta_sec is None


def test_file_index_must_exist() -> None:
    with pytest.raises(ValueError):
        ProgressTracker().update(2, 2, 0)
