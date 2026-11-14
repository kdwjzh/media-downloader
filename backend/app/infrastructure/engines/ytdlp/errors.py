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
    # shortcut: no real sample of a members-only video yet; add one and adjust this needle.
    ("members-only", ErrorCode.MEMBERS_ONLY),
    ("not made this video available in your country", ErrorCode.GEO_BLOCKED),
    ("The playlist does not exist", ErrorCode.PLAYLIST_NOT_FOUND),
    ("This video is unavailable", ErrorCode.NOT_FOUND),
    ("Video unavailable", ErrorCode.NOT_FOUND),
    ("has been removed", ErrorCode.NOT_FOUND),
    ("This live stream recording is not available", ErrorCode.NOT_FOUND),
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


def classify(stderr: str) -> EngineError:
    # Warnings come first and can mention things that did not fail. The text after "ERROR:"
    # may be on the following line, so everything from the first error on is searched.
    start = stderr.find("ERROR:")
    text = stderr[start:] if start >= 0 else stderr
    for needle, code in RULES:
        if needle in text:
            return EngineError(code, stderr.strip())
    return EngineError(ErrorCode.UNKNOWN, stderr.strip())
