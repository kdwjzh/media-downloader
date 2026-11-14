"""URL checks and command lines: what may reach yt-dlp, and how. Nothing is started."""

from pathlib import Path

import pytest

from app.domain.engine import DownloadRequest, EngineError
from app.domain.errors import ErrorCode
from app.domain.media import Format
from app.infrastructure.engines.ytdlp import args, urls


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "http://youtube.com/watch?v=jNQXAC9IVRw",
        "https://m.youtube.com/watch?v=jNQXAC9IVRw",
        "https://music.youtube.com/watch?v=jNQXAC9IVRw&list=PLx",
        "https://youtu.be/jNQXAC9IVRw",
        "https://www.youtube.com/shorts/g4rArHjS30k",
        "https://www.youtube.com/playlist?list=PL4fGSI1pDJn6puJdseH2Rt9sMvt9E2M4i",
        "https://www.youtube-nocookie.com/embed/jNQXAC9IVRw",
        "https://WWW.YouTube.com/watch?v=jNQXAC9IVRw",
    ],
)
def test_youtube_urls_are_accepted(url: str) -> None:
    urls.check(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not a url",
        "www.youtube.com/watch?v=jNQXAC9IVRw",
        "ftp://www.youtube.com/watch?v=jNQXAC9IVRw",
        "file:///C:/Windows/win.ini",
        "javascript:alert(1)",
        "--exec=calc",
        "-U",
        "https://",
        "https://www.youtube.com/watch?v=x --exec calc",
        "https://www.youtube.com/watch?v=",
        "https://www.youtube.com/watch",
    ],
)
def test_non_urls_are_invalid(url: str) -> None:
    with pytest.raises(EngineError) as error:
        urls.check(url)
    assert error.value.code is ErrorCode.INVALID_URL


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "https://vimeo.com/123",
        "https://youtube.com.evil.example/watch?v=x",
        "https://notyoutube.com/watch?v=x",
        "https://evil.example/?u=youtube.com",
        "https://youtube.com@evil.example/watch?v=x",
        "https://127.0.0.1/watch?v=x",
    ],
)
def test_other_sites_are_unsupported(url: str) -> None:
    with pytest.raises(EngineError) as error:
        urls.check(url)
    assert error.value.code is ErrorCode.UNSUPPORTED_SITE


URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def follows(command: list[str], option: str) -> str:
    return command[command.index(option) + 1]


def request(format: Format, quality: int) -> DownloadRequest:
    return DownloadRequest("t1", URL, format, quality, "C:\\dl")


@pytest.mark.parametrize(
    "command",
    [args.info(URL), args.download(request(Format.MP3, 192), Path("C:\\dl\\.md-tmp-t1"))],
)
def test_every_yt_dlp_call_follows_the_house_rules(command: list[str]) -> None:
    assert all(isinstance(part, str) for part in command)
    assert Path(command[0]).is_absolute() and command[0].endswith("yt-dlp.exe")
    assert "--ignore-config" in command
    assert follows(command, "--encoding") == "utf-8"
    assert follows(command, "--color") == "never"
    assert Path(follows(command, "--ffmpeg-location")).is_absolute()
    runtime = follows(command, "--js-runtimes")
    assert runtime.startswith("deno:") and Path(runtime[5:]).is_absolute()
    # The URL is one argument, last, behind "--".
    assert command[-2:] == ["--", URL]
    assert "--no-playlist" in command


def test_lookup_treats_video_in_playlist_as_one_video_and_lists_playlists_flat() -> None:
    command = args.info(URL)
    assert {"-J", "--flat-playlist", "--no-playlist"} <= set(command)


def test_mp3_download_arguments() -> None:
    command = args.download(request(Format.MP3, 192), Path("C:\\dl\\.md-tmp-t1"))
    assert follows(command, "--audio-format") == "mp3"
    assert follows(command, "--audio-quality") == "192K"
    assert "--embed-thumbnail" in command
    assert follows(command, "--ppa").endswith("-vf \"crop='min(iw,ih)':'min(iw,ih)'\"")


def test_mp4_download_arguments() -> None:
    command = args.download(request(Format.MP4, 720), Path("C:\\dl\\.md-tmp-t1"))
    assert follows(command, "-S") == "res:720,vcodec:h264,acodec:m4a"
    assert follows(command, "--merge-output-format") == "mp4"
    assert not any("height<=" in part for part in command)  # picks wrongly for vertical videos
    assert "--embed-thumbnail" not in command


def test_download_stays_in_the_task_folder_and_prints_what_the_engine_reads() -> None:
    command = args.download(request(Format.MP4, 720), Path("C:\\dl\\.md-tmp-t1"))
    assert follows(command, "-P") == "C:\\dl\\.md-tmp-t1"
    assert follows(command, "-o") == "%(title)s.%(ext)s"  # title only, no video id
    assert "--windows-filenames" in command and follows(command, "--trim-filenames") == "100"
    # --print makes yt-dlp quiet, which hides progress and the retry lines.
    assert "--no-quiet" in command and "--progress" in command and "--newline" in command
    printed = [command[i + 1] for i, part in enumerate(command) if part == "--print"]
    assert [p.split(":")[0] for p in printed] == ["before_dl", "before_dl", "after_move"]


def test_engine_offers_the_domain_interface_and_refuses_bad_urls_before_starting() -> None:
    from app.domain.engine import MediaEngine
    from app.infrastructure.engines.ytdlp.engine import YtDlpEngine

    engine: MediaEngine = YtDlpEngine()  # mypy checks the shape
    cases = (("-U", ErrorCode.INVALID_URL), ("https://vimeo.com/1", ErrorCode.UNSUPPORTED_SITE))
    for url, code in cases:
        with pytest.raises(EngineError) as error:
            engine.fetch_info(url)
        assert error.value.code is code
        with pytest.raises(EngineError) as error:
            engine.download(DownloadRequest("t1", url, Format.MP3, 128, "Z:\nowhere"), print)
        assert error.value.code is code
    engine.cancel("no-such-task")  # ignored
    engine.stop_all()
    engine.remove_stale_temp("Z:\\nowhere")  # a missing folder is ignored
