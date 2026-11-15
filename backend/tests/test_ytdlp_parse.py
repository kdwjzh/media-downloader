"""The engine's readers, fed with recorded yt-dlp output (tests/fixtures/ytdlp). No network."""

import json
from pathlib import Path

import pytest

from app.domain.engine import (
    ConnectionLost,
    EngineError,
    EngineEvent,
    FileProgress,
    FileSizes,
    PostProcessing,
)
from app.domain.errors import ErrorCode
from app.domain.media import QUALITIES, Format, MediaInfo, PlaylistInfo
from app.domain.progress import ProgressTracker
from app.infrastructure.engines.ytdlp import parse
from app.infrastructure.engines.ytdlp.errors import classify

FIXTURES = Path(__file__).parent / "fixtures" / "ytdlp"
SELECTED: dict[str, dict[str, str]] = json.loads((FIXTURES / "selected.json").read_text("utf-8"))


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def play(name: str) -> tuple[parse.DownloadOutput, list[EngineEvent]]:
    output = parse.DownloadOutput()
    lines = read(f"download/{name}.txt").splitlines(True)
    events = [event for line in lines if (event := output.feed(line))]
    return output, events


def kinds(events: list[EngineEvent]) -> list[type]:
    """Event types in order, with runs of the same type collapsed."""
    result: list[type] = []
    for event in events:
        if not result or result[-1] is not type(event):
            result.append(type(event))
    return result


def test_mp3_download_reports_sizes_then_progress_then_one_post_processing() -> None:
    output, events = play("mp3")
    # The cover is converted before the download; that must not count as post-processing.
    assert kinds(events) == [FileSizes, FileProgress, PostProcessing]
    assert events[0] == FileSizes((509908,))
    assert events[-2] == FileProgress(0, 1, 509908, 509908, events[-2].speed_bps)  # type: ignore[union-attr]
    assert output.name is not None and output.name.endswith("30秒搶先看！.webm")
    assert output.file is not None and output.file.endswith("30秒搶先看！.mp3")


def test_mp4_download_is_two_files_and_one_bar_from_0_to_100() -> None:
    output, events = play("mp4")
    assert kinds(events) == [FileSizes, FileProgress, PostProcessing]
    assert events[0] == FileSizes((19428926, 682151))
    progress = [e for e in events if isinstance(e, FileProgress)]
    assert [p.file_index for p in progress] == sorted(p.file_index for p in progress)
    assert {p.file_index for p in progress} == {0, 1} and {p.file_count for p in progress} == {2}
    # The same events through the domain's tracker: one bar that only goes up (old bug U3).
    tracker = ProgressTracker()
    tracker.expect(events[0].sizes)
    percents = [
        tracker.update(p.file_index, p.file_count, p.downloaded_bytes, p.total_bytes).percent
        for p in progress
    ]
    assert percents == sorted(percents) and percents[-1] == 100  # type: ignore[type-var]
    assert output.file is not None and output.file.endswith(".mp4")


def test_single_file_mp4_has_no_post_processing() -> None:
    _, events = play("mp4_single_file")
    assert kinds(events) == [FileSizes, FileProgress]
    assert {e.file_count for e in events if isinstance(e, FileProgress)} == {1}


def test_a_retry_that_works_reports_connection_lost_then_progress_again() -> None:
    _, events = play("retry_then_resume")
    assert kinds(events) == [FileSizes, FileProgress, ConnectionLost, FileProgress]
    assert [e for e in events if isinstance(e, ConnectionLost)] == [ConnectionLost(1)]


def test_retries_are_counted_here_because_yt_dlp_starts_over() -> None:
    output, events = play("retry_then_give_up")
    attempts = [e.attempt for e in events if isinstance(e, ConnectionLost)]
    assert "Retrying (1/3)" in read("download/retry_then_give_up.txt").split("Retrying (3/3)")[1]
    assert len(attempts) > 3 and attempts == list(range(1, len(attempts) + 1))
    assert output.file is None
    # The message is on the line after an empty "ERROR:".
    assert classify(output.other_text).code is ErrorCode.NETWORK


def lookup(name: str) -> MediaInfo | PlaylistInfo:
    return parse.info("https://example.invalid/pasted", read(f"info/{name}.json"))


@pytest.mark.parametrize("name", ["wide", "vertical", "uhd", "old43"])
def test_mp4_options_match_what_yt_dlp_really_selects(name: str) -> None:
    info = lookup(name)
    assert isinstance(info, MediaInfo)
    truth = SELECTED[name]
    ladder = QUALITIES[Format.MP4]
    # A quality is worth offering only when yt-dlp would download something different for it.
    expected = [
        q for i, q in enumerate(ladder) if i == 0 or truth[str(q)] != truth[str(ladder[i - 1])]
    ]
    assert [o.quality for o in info.options if o.format is Format.MP4] == expected
    formats = json.loads(read(f"info/{name}.json"))["formats"]
    for quality in expected:
        picked = parse.pick_formats(formats, quality)
        assert picked is not None
        assert "+".join(f["format_id"] for f in picked if f) == truth[str(quality)], quality


def test_wide_video_info() -> None:
    info = lookup("wide")
    assert isinstance(info, MediaInfo)
    assert (info.url, info.title, info.channel, info.duration_sec, info.platform) == (
        "https://example.invalid/pasted",
        "公視新創電影《最後的詩句》30秒搶先看！",
        "公視戲劇 PTS Drama",
        42,
        "youtube",
    )
    assert info.thumb == "https://i.ytimg.com/vi/FtSUD4KDscE/maxresdefault.jpg"
    sizes = {(o.format, o.quality): o.size_bytes for o in info.options}
    assert [k for k in sizes if k[0] is Format.MP3] == [(Format.MP3, q) for q in (128, 192, 320)]
    assert sizes[(Format.MP3, 320)] == 320_000 // 8 * 42
    assert sizes[(Format.MP4, 1080)] == 19428926 + 682151


def test_vertical_video_uses_the_short_side() -> None:
    info = lookup("vertical")
    assert isinstance(info, MediaInfo)
    assert max(o.quality for o in info.options if o.format is Format.MP4) == 1080  # 1080x1920


def test_playlist() -> None:
    info = lookup("playlist")
    assert isinstance(info, PlaylistInfo)
    assert info.title == "Top 100 Songs Global" and len(info.entries) == 99
    first = info.entries[0]
    assert first.available and first.title and first.duration_sec and first.channel
    assert first.url.startswith("https://www.youtube.com/watch?v=") and first.thumb


def test_private_playlist_entries_are_unavailable_and_carry_nothing_else() -> None:
    info = lookup("playlist_unavailable")
    assert isinstance(info, PlaylistInfo)
    gone = [e for e in info.entries if not e.available]
    assert len(info.entries) == 42 and len(gone) == 7
    assert all((e.title, e.duration_sec, e.channel, e.thumb) == (None,) * 4 and e.url for e in gone)


def test_live_stream_is_refused() -> None:
    with pytest.raises(EngineError) as error:
        lookup("live")
    assert error.value.code is ErrorCode.LIVE_NOT_SUPPORTED


def test_failed_lookup_output_is_unknown() -> None:
    with pytest.raises(EngineError) as error:
        parse.info("https://example.invalid/x", "null")
    assert error.value.code is ErrorCode.UNKNOWN


ERRORS = {
    "not_a_url": ErrorCode.INVALID_URL,
    "no_host": ErrorCode.INVALID_URL,
    "unsupported_site": ErrorCode.UNSUPPORTED_SITE,
    "not_found": ErrorCode.NOT_FOUND,
    "removed": ErrorCode.NOT_FOUND,
    "live_recording_gone": ErrorCode.NOT_FOUND,
    # A stream that has not started yet (2026-11-15): yt-dlp fails instead of answering.
    "live_upcoming": ErrorCode.LIVE_NOT_SUPPORTED,
    "private": ErrorCode.PRIVATE,
    "age_restricted": ErrorCode.AGE_RESTRICTED,
    "geo_blocked": ErrorCode.GEO_BLOCKED,
    # A real one (2026-11-15); the video id and the name of the level are masked.
    "members_only": ErrorCode.MEMBERS_ONLY,
    "playlist_not_found": ErrorCode.PLAYLIST_NOT_FOUND,
    "offline_lookup_proxy": ErrorCode.NETWORK,
    "offline_update_proxy": ErrorCode.NETWORK,
    # Wi-Fi really switched off (2026-11-14), as printed by scripts/manual/engine.py.
    "offline_lookup_real": ErrorCode.NETWORK,
    "offline_download_real": ErrorCode.NETWORK,
    "update_no_permission": ErrorCode.UNKNOWN,
    "http_403": ErrorCode.UNKNOWN,  # seen once while recording; the next try worked
}


def test_every_error_sample_has_an_expectation() -> None:
    assert {p.stem for p in (FIXTURES / "errors").glob("*.txt")} == set(ERRORS)


@pytest.mark.parametrize("name", ERRORS)
def test_error_samples_are_classified(name: str) -> None:
    text = read(f"errors/{name}.txt")
    error = classify(text)
    assert error.code is ERRORS[name]
    assert error.detail == text.strip()  # the raw text goes to the log file


def test_unmatched_text_is_unknown_and_keeps_the_original() -> None:
    text = "ERROR: something nobody has seen before"
    error = classify(text)
    assert (error.code, error.detail) == (ErrorCode.UNKNOWN, text)


def test_warnings_before_the_error_do_not_decide_the_code() -> None:
    text = "WARNING: skipped an entry: Private video\nERROR: something else broke"
    assert classify(text).code is ErrorCode.UNKNOWN


def test_update_result() -> None:
    assert parse.update_result(0, read("update_up_to_date.txt"), "") is False
    updated = "Updating to stable@2026.10.26 ...\nUpdated yt-dlp to stable@2026.10.26"
    assert parse.update_result(0, updated, "") is True
    with pytest.raises(EngineError) as error:
        parse.update_result(100, "", read("errors/update_no_permission.txt"))
    assert error.value.code is ErrorCode.UNKNOWN
    with pytest.raises(EngineError) as error:
        parse.update_result(100, "", read("errors/offline_update_proxy.txt"))
    assert error.value.code is ErrorCode.NETWORK
