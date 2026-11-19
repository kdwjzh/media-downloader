"""The network gate: allowed addresses, redirects, downloads. No network: redirects are fed
to the handler directly and answers come from a stand-in opener."""

import hashlib
import io
import urllib.error
import urllib.request
from email.message import Message
from http.client import HTTPMessage, IncompleteRead
from pathlib import Path
from typing import Any

import pytest

from app.infrastructure import http

GITHUB = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/a/b/releases/download/v1.0.0/x.exe",
        "https://release-assets.githubusercontent.com/github-production-release-asset/1/2",
        "https://objects.githubusercontent.com/x",
        "https://GitHub.com./x",  # case and a trailing dot
        "https://github.com:443/x",
    ],
)
def test_allowed(url: str) -> None:
    http.check(url, GITHUB)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/x",  # not https
        "https://github.com:8443/x",
        "https://raw.githubusercontent.com/someone/else/main/x.exe",  # not on the list
        "https://github.com.evil.example/x",
        "https://evilgithub.com/x",
        "https://user@evil.example/x",
        "ftp://github.com/x",
        "file:///C:/Windows/notepad.exe",
        "https://[::1/x",  # does not parse
        "",
        "http://127.0.0.1:8765/x",  # only the test source may use it
        "https://127.0.0.1/x",
    ],
)
def test_not_allowed(url: str) -> None:
    with pytest.raises(ValueError):
        http.check(url, GITHUB)


def test_the_test_source_allows_http_to_127_0_0_1_only() -> None:
    http.check("http://127.0.0.1:8765/releases/latest", (), loopback_http=True)
    for url in ("http://localhost:8765/x", "http://127.0.0.2/x", "http://example.com/x"):
        with pytest.raises(ValueError):
            http.check(url, (), loopback_http=True)


# ---- redirects


def redirect(handler: Any, newurl: str) -> object:
    request = urllib.request.Request("https://github.com/a/b/releases/download/v1/x.exe")
    return handler.redirect_request(request, io.BytesIO(), 302, "Found", Message(), newurl)


def test_a_redirect_to_an_allowed_host_is_followed() -> None:
    handler = http._CheckedRedirects(GITHUB, False)
    new = redirect(handler, "https://release-assets.githubusercontent.com/asset?sig=1")
    assert isinstance(new, urllib.request.Request)
    assert new.full_url == "https://release-assets.githubusercontent.com/asset?sig=1"


@pytest.mark.parametrize(
    "newurl",
    [
        "https://evil.example/x.exe",
        "http://release-assets.githubusercontent.com/x",  # downgraded to http
        "https://raw.githubusercontent.com/x",
        "http://127.0.0.1:8765/x",
    ],
)
def test_a_redirect_elsewhere_ends_the_request(newurl: str) -> None:
    with pytest.raises(ValueError):
        redirect(http._CheckedRedirects(GITHUB, False), newurl)


def test_redirects_are_limited() -> None:
    assert http._CheckedRedirects.max_redirections == http.MAX_REDIRECTS == 5
    handler = http._CheckedRedirects(GITHUB, False)
    request = urllib.request.Request("https://github.com/x")
    # urllib counts the visits on the request; the sixth redirect raises.
    request.redirect_dict = {f"https://github.com/{i}": 1 for i in range(5)}  # type: ignore[attr-defined]
    headers = HTTPMessage()
    headers["Location"] = "https://github.com/next"
    with pytest.raises(urllib.error.HTTPError) as raised:
        handler.http_error_302(request, io.BytesIO(), 302, "Found", headers)
    assert "infinite loop" in str(raised.value)


# ---- downloading


class Answer(io.BytesIO):
    def __init__(self, body: bytes, length: int | None) -> None:
        super().__init__(body)
        self.headers = Message()
        if length is not None:
            self.headers["Content-Length"] = str(length)


def serve(monkeypatch: pytest.MonkeyPatch, answer: object) -> list[str]:
    asked: list[str] = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: float) -> object:
            asked.append(request.full_url)
            if isinstance(answer, Exception):
                raise answer
            return answer

    def build(*handlers: object) -> Opener:
        # Every request goes through the checked redirects, with the caller's hosts.
        assert any(isinstance(h, http._CheckedRedirects) for h in handlers)
        return Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build)
    return asked


def test_https_is_verified_by_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    # Bug (stage 5c, Windows Sandbox): no history thumbnails, CERTIFICATE_VERIFY_FAILED.
    # Python's own check only knows the roots already in the Windows store and never lets
    # Windows fetch a missing one, as browsers do. truststore asks Windows to verify.
    handlers: list[object] = []

    class Opener:
        def open(self, request: urllib.request.Request, timeout: float) -> object:
            return Answer(b"x", 1)

    def build(*given: object) -> Opener:
        handlers.extend(given)
        return Opener()

    monkeypatch.setattr(urllib.request, "build_opener", build)
    http.get("https://github.com/x", GITHUB, 10, 5)
    contexts = [h._context for h in handlers if isinstance(h, urllib.request.HTTPSHandler)]  # type: ignore[attr-defined]
    assert [type(c).__module__.split(".")[0] for c in contexts] == ["truststore"]


def fetch(dest: Path, max_bytes: int = 10_000, cancel_after: int | None = None) -> object:
    seen: list[int] = []

    def cancelled() -> bool:
        return cancel_after is not None and len(seen) > cancel_after

    return http.download(
        "https://github.com/x.exe", GITHUB, dest, max_bytes, 5,
        lambda got, total: seen.append(got), cancelled,
    )  # fmt: skip


def test_download_writes_the_file_and_returns_its_size_and_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    body = bytes(range(256)) * 600  # several chunks
    serve(monkeypatch, Answer(body, len(body)))
    dest = tmp_path / "x.part"
    assert fetch(dest, 1_000_000) == (len(body), hashlib.sha256(body).hexdigest())
    assert dest.read_bytes() == body


def test_download_refuses_an_address_before_asking(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    asked = serve(monkeypatch, Answer(b"x", 1))
    with pytest.raises(ValueError):
        http.download("http://github.com/x", GITHUB, tmp_path / "x", 10, 5,
                      lambda *a: None, lambda: False)  # fmt: skip
    assert asked == []


def test_download_stops_when_cancelled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = b"x" * 300_000
    serve(monkeypatch, Answer(body, len(body)))
    assert fetch(tmp_path / "x", 1_000_000, cancel_after=1) is None


@pytest.mark.parametrize("length", [20_000, None])
def test_download_refuses_a_too_large_answer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, length: int | None
) -> None:
    serve(monkeypatch, Answer(b"x" * 20_000, length))
    with pytest.raises(ValueError):
        fetch(tmp_path / "x", 10_000)


def test_download_cut_short_is_a_network_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve(monkeypatch, Answer(b"x" * 100, 5_000))  # says 5,000 bytes, sends 100
    with pytest.raises(ConnectionError) as raised:
        fetch(tmp_path / "x")
    assert http.is_network_error(raised.value)


def test_get_reads_small_answers_through_the_same_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = serve(monkeypatch, Answer(b'{"tag_name": "v1.0.0"}', None))
    assert http.get("https://api.github.com/x", ("api.github.com",), 100, 5) == (
        b'{"tag_name": "v1.0.0"}'
    )
    assert asked == ["https://api.github.com/x"]
    serve(monkeypatch, Answer(b"x" * 101, None))
    with pytest.raises(ValueError):
        http.get("https://api.github.com/x", ("api.github.com",), 100, 5)


@pytest.mark.parametrize(
    ("error", "network"),
    [
        (urllib.error.URLError("no route"), True),
        (TimeoutError("timed out"), True),
        (ConnectionResetError("reset"), True),
        (IncompleteRead(b"x", 10), True),
        (urllib.error.HTTPError("https://x", 404, "Not Found", Message(), None), False),
        (ValueError("not allowed"), False),
        (OSError(28, "No space left on device"), False),
    ],
)
def test_which_errors_are_network_errors(error: BaseException, network: bool) -> None:
    assert http.is_network_error(error) is network
