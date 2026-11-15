"""What the app fetches itself: which addresses it may ask, thumbnails, the latest release.
The network and FFmpeg are replaced; nothing leaves this computer."""

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app import REPOSITORY
from app.infrastructure import binaries, http, releases, thumbnails
from app.infrastructure.engines.ytdlp.urls import THUMB_HOSTS

JPEG = b"\xff\xd8\xff" + b"j" * 100


class Opener:
    """Stands in for urllib: answers every request with the same body."""

    def __init__(self, body: bytes = b"", error: Exception | None = None) -> None:
        self.body, self.error = body, error
        self.requests: list[tuple[str, dict[str, str], float]] = []

    def open(self, request: urllib.request.Request, timeout: float) -> io.BytesIO:
        self.requests.append((request.full_url, dict(request.header_items()), timeout))
        if self.error:
            raise self.error
        return io.BytesIO(self.body)


@pytest.fixture
def net(monkeypatch: pytest.MonkeyPatch) -> Opener:
    opener = Opener()
    monkeypatch.setattr(http, "_opener", opener)
    return opener


@pytest.mark.parametrize(
    "url",
    [
        "http://i.ytimg.com/vi/a/1.jpg",  # not https
        "https://evil.example/1.jpg",
        "https://ytimg.com.evil.example/1.jpg",
        "https://evilytimg.com/1.jpg",
        "https://i.ytimg.com@evil.example/1.jpg",  # the part before @ is a user name
        "https://i.ytimg.com:8443/1.jpg",
        "https://127.0.0.1/1.jpg",
        "https://localhost/1.jpg",
        "https://[::1]/1.jpg",
        "https://192.168.1.1/admin",
        "file:///C:/Windows/win.ini",
        "ftp://i.ytimg.com/1.jpg",
        "data:image/jpeg;base64,AAAA",
        "//i.ytimg.com/1.jpg",
        "https://i.ytimg.com:port/1.jpg",
        "",
    ],
)
def test_an_address_that_is_not_allowed_is_never_asked(url: str, net: Opener) -> None:
    with pytest.raises(ValueError):
        http.get(url, THUMB_HOSTS, 1000, 5)
    assert net.requests == []


@pytest.mark.parametrize(
    "url",
    ["https://i.ytimg.com/vi/a/1.jpg", "https://I9.YTIMG.COM./x", "https://ytimg.com:443/x"],
)
def test_an_allowed_host_or_its_subdomain_is_asked(url: str, net: Opener) -> None:
    net.body = b"picture"
    assert http.get(url, THUMB_HOSTS, 1000, 5) == b"picture"
    assert [(asked, timeout) for asked, _, timeout in net.requests] == [(url, 5)]


def test_an_answer_that_is_too_large_is_refused(net: Opener) -> None:
    net.body = b"x" * 1001
    with pytest.raises(ValueError):
        http.get("https://i.ytimg.com/1.jpg", THUMB_HOSTS, 1000, 5)
    net.body = b"x" * 1000
    assert len(http.get("https://i.ytimg.com/1.jpg", THUMB_HOSTS, 1000, 5)) == 1000


def test_redirects_are_not_followed() -> None:
    handlers = http._opener.handlers  # type: ignore[attr-defined]
    [ours] = [h for h in handlers if isinstance(h, urllib.request.HTTPRedirectHandler)]
    assert type(ours) is http._NoRedirect  # it replaced the default one
    request = urllib.request.Request("https://i.ytimg.com/1.jpg")
    headers = {"location": "https://evil.example/"}
    # None: no new request is made, and urllib then raises the 302 as an HTTPError.
    assert ours.http_error_302(request, io.BytesIO(), 302, "Found", headers) is None  # type: ignore[arg-type]


# ---- thumbnails


@pytest.fixture
def ffmpeg(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Replaces FFmpeg: writes a "small picture" where the real one would."""
    runs: list[list[str]] = []

    def run(args: list[str], timeout: float) -> tuple[int, str, str]:
        runs.append(args)
        assert Path(args[args.index("-i") + 1]).read_bytes()  # the fetched image is there
        Path(args[-1]).write_bytes(b"small")
        return 0, "", ""

    monkeypatch.setattr(thumbnails, "run", run)
    return runs


@pytest.mark.parametrize(
    ("image", "demuxer"),
    [
        (JPEG, "jpeg_pipe"),
        (b"\x89PNG\r\n\x1a\n" + b"p" * 50, "png_pipe"),
        (b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"w" * 50, "webp_pipe"),
    ],
)
def test_a_thumbnail_is_fetched_and_shrunk(
    image: bytes, demuxer: str, net: Opener, ffmpeg: list[list[str]]
) -> None:
    net.body = image
    maker = thumbnails.ThumbnailMaker(THUMB_HOSTS)
    assert maker.make("https://i.ytimg.com/vi/a/maxresdefault.jpg") == b"small"
    [args] = ffmpeg
    assert args[0] == str(binaries.ffmpeg())  # the path comes from binaries, nowhere else
    assert args[args.index("-f") + 1] == demuxer  # FFmpeg is told the format, it does not guess
    assert args.index("-f") < args.index("-i")
    assert not Path(args[-1]).parent.exists()  # the temporary folder is gone


@pytest.mark.parametrize(
    "body",
    [
        b"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:1,\nfile:///C:/Users/x/secret.txt\n",
        b"ffconcat version 1.0\nfile 'C:/Windows/win.ini'\n",
        b"<html>not found</html>",
        b"",
    ],
)
def test_something_that_is_not_an_image_never_reaches_ffmpeg(
    body: bytes, net: Opener, ffmpeg: list[list[str]], caplog: pytest.LogCaptureFixture
) -> None:
    net.body = body
    assert thumbnails.ThumbnailMaker(THUMB_HOSTS).make("https://i.ytimg.com/1.jpg") is None
    assert ffmpeg == []
    assert "no thumbnail" in caplog.text


@pytest.mark.parametrize("url", ["https://evil.example/1.jpg", "data:image/jpeg;base64,AAAA", ""])
def test_a_thumbnail_from_elsewhere_is_not_fetched(
    url: str, net: Opener, ffmpeg: list[list[str]]
) -> None:
    assert thumbnails.ThumbnailMaker(THUMB_HOSTS).make(url) is None
    assert net.requests == [] and ffmpeg == []


def test_no_network_or_a_failing_ffmpeg_means_no_thumbnail_not_an_error(
    net: Opener, monkeypatch: pytest.MonkeyPatch
) -> None:
    maker = thumbnails.ThumbnailMaker(THUMB_HOSTS)
    net.error = OSError("no network")
    assert maker.make("https://i.ytimg.com/1.jpg") is None
    net.error, net.body = None, JPEG
    monkeypatch.setattr(thumbnails, "run", lambda args, timeout: (1, "", "Invalid data"))
    assert maker.make("https://i.ytimg.com/1.jpg") is None

    def hangs(args: list[str], timeout: float) -> tuple[int, str, str]:
        raise TimeoutError("no result")

    monkeypatch.setattr(thumbnails, "run", hangs)
    assert maker.make("https://i.ytimg.com/1.jpg") is None


# ---- the latest release


def test_the_latest_release_is_asked_from_github_only(net: Opener) -> None:
    net.body = json.dumps({"tag_name": "v1.2.3", "draft": False}).encode()
    assert releases.latest_tag() == "v1.2.3"
    [(url, headers, timeout)] = net.requests
    assert url == f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
    assert timeout == releases.TIMEOUT
    assert "User-agent" in headers  # GitHub refuses requests without one


@pytest.mark.parametrize("body", [b"not json", b"[]", b"{}", b'{"tag_name": 5}', b"\xff"])
def test_an_answer_without_a_tag_is_an_error_the_service_can_swallow(
    body: bytes, net: Opener
) -> None:
    net.body = body
    with pytest.raises((OSError, ValueError)):
        releases.latest_tag()


def test_a_private_repository_answers_404(net: Opener) -> None:
    net.error = urllib.error.HTTPError("url", 404, "Not Found", {}, None)  # type: ignore[arg-type]
    with pytest.raises(OSError):
        releases.latest_tag()


# ---- versions of the bundled programs


def test_tool_versions_are_read_from_their_first_line(monkeypatch: pytest.MonkeyPatch) -> None:
    outputs = {
        "-version": "ffmpeg version N-128757-g4b42530309-20261110 Copyright (c) 2000-2026\nbuilt",
        "--version": "deno 2.9.8 (stable, release, x86_64-pc-windows-msvc)\nv8 14.0\n",
    }
    monkeypatch.setattr(binaries, "run", lambda args, timeout: (0, outputs[args[-1]], ""))
    assert binaries.ffmpeg_version() == "N-128757-g4b42530309-20261110"
    assert binaries.deno_version() == "2.9.8"
    monkeypatch.setattr(binaries, "run", lambda args, timeout: (0, "something else", ""))
    assert binaries.ffmpeg_version() is None

    def missing(args: list[str], timeout: float) -> tuple[int, str, str]:
        raise FileNotFoundError(args[0])

    monkeypatch.setattr(binaries, "run", missing)
    assert binaries.deno_version() is None
