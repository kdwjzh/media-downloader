"""Maps yt-dlp's stderr to an ErrorCode. Every failure exits with code 1, so the text is all
there is. This is the only file to change when a new sample of an error turns up.

Only yt-dlp's own English wording is matched: the operating system's part of a message
follows the system language.
"""

from app.domain.engine import EngineError
from app.domain.errors import ErrorCode

# First match wins. Samples: backend/tests/fixtures/ytdlp/errors/.
RULES: tuple[tuple[str, ErrorCode], ...] = (
    ("Private video", ErrorCode.PRIVATE),
    ("Sign in to confirm your age", ErrorCode.AGE_RESTRICTED),
    ("members-only", ErrorCode.MEMBERS_ONLY),
    ("not made this video available in your country", ErrorCode.GEO_BLOCKED),
    ("The playlist does not exist", ErrorCode.PLAYLIST_NOT_FOUND),
    ("This video is unavailable", ErrorCode.NOT_FOUND),
    ("Video unavailable", ErrorCode.NOT_FOUND),
    ("has been removed", ErrorCode.NOT_FOUND),
    ("This live stream recording is not available", ErrorCode.NOT_FOUND),
    # A stream that has not started: yt-dlp fails here instead of reporting is_upcoming.
    ("This live event will begin in", ErrorCode.LIVE_NOT_SUPPORTED),
    ("is not a valid URL", ErrorCode.INVALID_URL),
    ("Invalid URL", ErrorCode.INVALID_URL),
    ("Unsupported URL", ErrorCode.UNSUPPORTED_SITE),
    ("Giving up after", ErrorCode.NETWORK),
    ("Unable to connect", ErrorCode.NETWORK),
    ("Failed to resolve", ErrorCode.NETWORK),
    ("getaddrinfo failed", ErrorCode.NETWORK),
    ("Failed to establish a new connection", ErrorCode.NETWORK),
    ("timed out", ErrorCode.NETWORK),
    ("Connection reset", ErrorCode.NETWORK),
    ("Connection aborted", ErrorCode.NETWORK),
)


def _error_part(stderr: str) -> str:
    # Warnings come first and can mention things that did not fail. The text after "ERROR:"
    # may be on the following line, so everything from the first error on is searched.
    start = stderr.find("ERROR:")
    return stderr[start:] if start >= 0 else stderr


def is_forbidden(stderr: str) -> bool:
    """YouTube refuses a download now and then when several start together (about 1 in 15
    with three or more); the same download works on the next try. The engine tries once
    more; a second one is classified like any other error (unknown)."""
    return "HTTP Error 403" in _error_part(stderr)


def classify(stderr: str) -> EngineError:
    text = _error_part(stderr)
    for needle, code in RULES:
        if needle in text:
            return EngineError(code, stderr.strip())
    return EngineError(ErrorCode.UNKNOWN, stderr.strip())
