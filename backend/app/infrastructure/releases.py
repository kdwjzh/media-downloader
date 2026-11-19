"""Where this app's releases come from: which is the latest, and the addresses of its
installer and checksum file. Every address is built here from a checked version number;
nothing the network answers becomes part of an address except that number.

A test build (scripts/build_installer.py --test-update-source) asks a server on 127.0.0.1
instead of GitHub (docs/decisions/0019). An official build must never carry the marker.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from app import REPOSITORY
from app.domain import version
from app.infrastructure import http

TIMEOUT = 5
# The file a test build has next to its data files (PyInstaller's _internal folder).
TEST_MARKER = "update-source-test"
TEST_PORT = 8765


@dataclass(frozen=True)
class Source:
    latest: str  # answers {"tag_name": "v1.2.3", ...} like GitHub's releases/latest
    download: str  # + "/v<version>/<file name>"
    api_hosts: tuple[str, ...]
    # github.com redirects the download to one of the others. Exact names: all of
    # githubusercontent.com would also let in raw.githubusercontent.com, anyone's files.
    download_hosts: tuple[str, ...]
    loopback_http: bool = False


GITHUB = Source(
    f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
    f"https://github.com/{REPOSITORY}/releases/download",
    ("api.github.com",),
    ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"),
)
TEST = Source(
    f"http://{http.LOOPBACK}:{TEST_PORT}/releases/latest",
    f"http://{http.LOOPBACK}:{TEST_PORT}/releases/download",
    (),
    (),
    loopback_http=True,
)


def source() -> Source:
    if getattr(sys, "frozen", False) and (Path(sys._MEIPASS) / TEST_MARKER).is_file():  # type: ignore[attr-defined]
        return TEST
    return GITHUB


def installer_name(found: str) -> str:
    """MediaDownloader-Setup-1.2.3.exe: the name scripts/build_installer.py gives it."""
    plain = version.plain(found)
    if plain is None:
        raise ValueError("not a version number")
    return f"MediaDownloader-Setup-{plain}.exe"


def installer_url(found: str, source: Source) -> str:
    return f"{source.download}/v{version.plain(found)}/{installer_name(found)}"


def latest_tag() -> str:
    """The tag of the latest release that is neither a draft nor a pre-release. Raises
    OSError or ValueError: no network, no release yet, a private repository (404), GitHub's
    hourly limit."""
    where = source()
    body = http.get(
        where.latest,
        where.api_hosts,
        1_000_000,
        TIMEOUT,
        {"Accept": "application/vnd.github+json"},
        where.loopback_http,
    )
    data = json.loads(body)
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not isinstance(tag, str):
        raise ValueError("the answer has no tag_name")
    return tag
