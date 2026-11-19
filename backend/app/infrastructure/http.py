"""The only way this app fetches anything from the network itself (yt-dlp does its own).

Every address, also every address a redirect leads to, must be https on the default port
and a host on the caller's allow list (or a subdomain of one). The one exception is the
test build's update source on 127.0.0.1 (releases.py, docs/decisions/0019).
"""

import hashlib
import http.client
import ssl
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import IO
from urllib.parse import urlsplit

import truststore

MAX_REDIRECTS = 5
# Windows verifies the certificates, as browsers do: Python's own check only knows the roots
# already in the Windows store, so a clean Windows that lacks one fails (docs/decisions/0020).
_TLS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
_CHUNK = 64 * 1024
LOOPBACK = "127.0.0.1"


def check(url: str, allowed_hosts: Sequence[str], loopback_http: bool = False) -> None:
    """Raises ValueError for an address this app may not fetch. loopback_http also allows
    plain http to 127.0.0.1 (any port): only the test build's update source asks for it."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
        scheme = parts.scheme
    except ValueError:
        scheme, host, port = "", "", None
    if loopback_http and scheme == "http" and host == LOOPBACK:
        return
    if (
        scheme != "https"
        or port not in (None, 443)
        or not any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)
    ):
        raise ValueError("not an address this app may fetch")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def __init__(self, allowed_hosts: Sequence[str], loopback_http: bool) -> None:
        self._allowed = allowed_hosts
        self._loopback = loopback_http

    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:
        check(newurl, self._allowed, self._loopback)  # ValueError ends the request
        return super().redirect_request(req, fp, code, msg, headers, newurl)  # type: ignore[arg-type]


def _open(
    url: str,
    allowed_hosts: Sequence[str],
    timeout: float,
    headers: Mapping[str, str] | None,
    loopback_http: bool,
) -> IO[bytes]:
    check(url, allowed_hosts, loopback_http)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_TLS), _CheckedRedirects(allowed_hosts, loopback_http)
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "media-downloader", **(headers or {})}
    )
    response: IO[bytes] = opener.open(request, timeout=timeout)
    return response


def get(
    url: str,
    allowed_hosts: Sequence[str],
    max_bytes: int,
    timeout: float,
    headers: Mapping[str, str] | None = None,
    loopback_http: bool = False,
) -> bytes:
    """Raises ValueError for an address that is not allowed (also one a redirect leads to)
    or an answer that is too large, OSError when the request fails."""
    with _open(url, allowed_hosts, timeout, headers, loopback_http) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"the answer is larger than {max_bytes} bytes")
    return data


def download(
    url: str,
    allowed_hosts: Sequence[str],
    dest: Path,
    max_bytes: int,
    timeout: float,
    on_progress: Callable[[int, int | None], None],
    cancelled: Callable[[], bool],
    loopback_http: bool = False,
) -> tuple[int, str] | None:
    """Writes the answer to dest as it arrives and returns (size, SHA-256 hex), or None
    when cancelled. timeout applies to each read, not to the whole download. Raises like
    get(); an answer cut short raises OSError (or http.client.IncompleteRead). dest is
    left for the caller to delete when anything goes wrong."""
    digest = hashlib.sha256()
    received = 0
    with _open(url, allowed_hosts, timeout, None, loopback_http) as response:
        length = response.headers.get("Content-Length")  # type: ignore[attr-defined]
        total = int(length) if length and length.isdigit() else None
        if total is not None and total > max_bytes:
            raise ValueError(f"the answer is larger than {max_bytes} bytes")
        with dest.open("wb") as file:
            on_progress(0, total)
            while chunk := response.read(_CHUNK):
                if cancelled():
                    return None
                received += len(chunk)
                if received > max_bytes:
                    raise ValueError(f"the answer is larger than {max_bytes} bytes")
                digest.update(chunk)
                file.write(chunk)
                on_progress(received, total)
    if total is not None and received != total:
        raise ConnectionError(f"the answer ended after {received} of {total} bytes")
    return received, digest.hexdigest()


def is_network_error(error: BaseException) -> bool:
    """The connection failed, timed out or was cut short. Not an HTTP error status (the
    server answered), an address that is not allowed, or a full disk."""
    if isinstance(error, urllib.error.HTTPError):
        return False
    return isinstance(
        error, urllib.error.URLError | TimeoutError | ConnectionError | http.client.HTTPException
    )
