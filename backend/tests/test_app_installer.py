"""The installer store and the release addresses. No network: http is replaced; no
installer is started: launch_detached is replaced."""

import hashlib
import sys
from pathlib import Path

import pytest

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode
from app.infrastructure import http, process, releases
from app.infrastructure.app_installer import INSTALLER_ARGS, AppInstaller


def test_addresses_are_built_from_the_version_alone() -> None:
    assert releases.installer_url("v1.0.0-rc.2", releases.GITHUB) == (
        "https://github.com/kdwjzh/media-downloader/releases/download/v1.0.0-rc.2/"
        "MediaDownloader-Setup-1.0.0-rc.2.exe"
    )
    assert releases.installer_name("1.2.3+build.1") == "MediaDownloader-Setup-1.2.3.exe"
    for bad in ("../../evil", "1.2.3/x", "1.2.3?x", "1.2.3 x", ""):
        with pytest.raises(ValueError):
            releases.installer_name(bad)


def test_the_official_source_is_github_over_https() -> None:
    source = releases.GITHUB
    assert not source.loopback_http
    for url in (source.latest, releases.installer_url("1.0.0", source)):
        http.check(url, (*source.api_hosts, *source.download_hosts))
    assert "githubusercontent.com" not in source.download_hosts


def test_only_a_build_with_the_marker_uses_the_test_source(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert releases.source() is releases.GITHUB  # development
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert releases.source() is releases.GITHUB  # an official build: no marker
    (tmp_path / releases.TEST_MARKER).write_text("")
    assert releases.source() is releases.TEST


class Net:
    def __init__(self, body: bytes = b"installer") -> None:
        self.body = body
        self.error: Exception | None = None
        self.asked: list[str] = []

    def get(self, url: str, hosts: object, max_bytes: int, timeout: float,
            headers: object = None, loopback_http: bool = False) -> bytes:  # fmt: skip
        self.asked.append(url)
        if self.error:
            raise self.error
        return b"abc  name\n"

    def download(self, url: str, hosts: object, dest: Path, max_bytes: int, timeout: float,
                 on_progress: object, cancelled: object,
                 loopback_http: bool = False) -> tuple[int, str] | None:  # fmt: skip
        self.asked.append(url)
        dest.write_bytes(self.body[:3])  # a partial file exists when it goes wrong
        if self.error:
            raise self.error
        dest.write_bytes(self.body)
        return len(self.body), hashlib.sha256(self.body).hexdigest()


@pytest.fixture
def net(monkeypatch: pytest.MonkeyPatch) -> Net:
    fake = Net()
    monkeypatch.setattr(http, "get", fake.get)  # the module app_installer fetches with
    monkeypatch.setattr(http, "download", fake.download)
    return fake


def test_download_accept_and_digest(net: Net, tmp_path: Path) -> None:
    store = AppInstaller(tmp_path / "updates")
    done = store.download("1.0.0", lambda *a: None, lambda: False)
    assert done == (9, hashlib.sha256(b"installer").hexdigest())
    assert net.asked == [releases.installer_url("1.0.0", releases.GITHUB)]
    assert [p.name for p in (tmp_path / "updates").iterdir()] == [
        "MediaDownloader-Setup-1.0.0.exe.part"
    ]
    store.accept("1.0.0")
    assert store.digest("1.0.0") == done
    assert store.checksum_text("1.0.0") == "abc  name\n"
    assert net.asked[-1].endswith("MediaDownloader-Setup-1.0.0.exe.sha256")


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ConnectionResetError("reset"), ErrorCode.NETWORK),
        (TimeoutError("slow"), ErrorCode.NETWORK),
        (ValueError("redirected to a host that is not allowed"), ErrorCode.UNKNOWN),
        (OSError(28, "disk full"), ErrorCode.UNKNOWN),
    ],
)
def test_a_failed_download_leaves_no_partial_file(
    net: Net, tmp_path: Path, error: Exception, code: ErrorCode
) -> None:
    net.error = error
    store = AppInstaller(tmp_path)
    with pytest.raises(EngineError) as raised:
        store.download("1.0.0", lambda *a: None, lambda: False)
    assert raised.value.code is code
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(EngineError) as raised:
        store.checksum_text("1.0.0")
    assert raised.value.code is code


def test_launch_starts_the_installer_detached_and_only_when_packaged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started: list[list[str]] = []
    monkeypatch.setattr(process, "launch_detached", started.append)
    store = AppInstaller(tmp_path)
    with pytest.raises(EngineError):
        store.launch("1.0.0")  # development
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    store.launch("1.0.0")
    assert started == [[str(tmp_path / "MediaDownloader-Setup-1.0.0.exe"), *INSTALLER_ARGS]]
    assert INSTALLER_ARGS == ["/SILENT", "/NORESTART", "/UPDATE=1"]


def test_discard_removes_the_folder(tmp_path: Path) -> None:
    (tmp_path / "updates").mkdir()
    (tmp_path / "updates" / "x.part").write_bytes(b"x")
    AppInstaller(tmp_path / "updates").discard()
    assert not (tmp_path / "updates").exists()
    AppInstaller(tmp_path / "missing").discard()  # nothing there: no error
