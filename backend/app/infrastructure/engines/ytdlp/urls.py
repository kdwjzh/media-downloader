"""Which URLs this engine accepts. Checked before any process is started."""

from urllib.parse import parse_qs, urlsplit

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode

PLATFORM = "youtube"

# A host is accepted when it is one of these or a subdomain of one.
ALLOWED_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")


def check(url: str) -> None:
    """Raises EngineError unless url is an http(s) URL on an allowed host."""
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError as error:
        raise EngineError(ErrorCode.INVALID_URL, str(error)) from error
    if parts.scheme not in ("http", "https") or not host or any(c.isspace() for c in url):
        raise EngineError(ErrorCode.INVALID_URL, url)
    if not any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS):
        raise EngineError(ErrorCode.UNSUPPORTED_SITE, url)
    # yt-dlp answers a watch URL without an id with an empty "recommended" playlist and exit 0.
    if parts.path.rstrip("/") == "/watch" and not parse_qs(parts.query).get("v"):
        raise EngineError(ErrorCode.INVALID_URL, url)
