"""The only way this app fetches anything from the network itself (yt-dlp does its own)."""

import urllib.request
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None  # the redirect then fails as an HTTPError: an allowed host cannot send us on


_opener = urllib.request.build_opener(_NoRedirect)


def get(
    url: str,
    allowed_hosts: Sequence[str],
    max_bytes: int,
    timeout: float,
    headers: Mapping[str, str] | None = None,
) -> bytes:
    """Raises ValueError for an address that is not allowed or an answer that is too large,
    OSError when the request fails. Only https, only the default port, only a host that is
    one of allowed_hosts or a subdomain of one; redirects are not followed."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
        scheme = parts.scheme
    except ValueError:
        scheme, host, port = "", "", None
    if (
        scheme != "https"
        or port not in (None, 443)
        or not any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)
    ):
        raise ValueError("not an address this app may fetch")
    request = urllib.request.Request(
        url, headers={"User-Agent": "media-downloader", **(headers or {})}
    )
    with _opener.open(request, timeout=timeout) as response:
        data: bytes = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"the answer is larger than {max_bytes} bytes")
    return data
