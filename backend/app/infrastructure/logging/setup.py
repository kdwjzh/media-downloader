"""The log file. Everything the layers log with the standard `logging` module ends up here,
with personal paths masked."""

import logging
import re
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_BYTES = 1_000_000
BACKUPS = 3  # app.log plus three older files: about 4 MB at most

_SEP = r"[\\/]+"  # also matches the doubled backslashes of a repr()
# A URL with a long query string is a signed media URL: it carries the user's IP address.
# The URL of a video or a playlist has a short one and is kept whole.
_LONG_QUERY = re.compile(r"""(https?://[^\s"'<>?]+)\?[^\s"'<>]{100,}""")


def masker(*homes: str) -> "re.Pattern[str]":
    """Each of homes is the same folder spelled another way (the long and the 8.3 name)."""
    spellings = []
    for home in homes:
        parts = [re.escape(part) for part in re.split(_SEP, home.rstrip("\\/")) if part]
        whole = _SEP.join(parts)
        # The last two parts alone ("Users\name") catch the same folder written another way,
        # like /c/Users/name.
        spellings += [whole, _SEP.join(parts[-2:]) if len(parts) > 2 else whole]
    # Not followed by more of a name: "name2" is somebody else. Masking too much ("name.old")
    # is the safe side.
    return re.compile(rf"(?:{'|'.join(spellings)})(?![\w\-])", re.IGNORECASE)


def short_path(path: str) -> str:
    """The 8.3 form Windows gives some paths (TEMP often uses it), or path itself when the
    volume has no 8.3 names or this isn't Windows."""
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(1024)
        size = ctypes.windll.kernel32.GetShortPathNameW(path, buffer, len(buffer))
    except (ImportError, AttributeError, OSError):
        return path
    return buffer.value if 0 < size < len(buffer) else path


def mask(text: str, home: "re.Pattern[str]") -> str:
    return _LONG_QUERY.sub(r"\1?...", home.sub("%USERPROFILE%", text))


class _MaskingFormatter(logging.Formatter):
    def __init__(self, homes: tuple[str, ...]) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")
        self._home = masker(*homes)

    def format(self, record: logging.LogRecord) -> str:
        return mask(super().format(record), self._home)  # the traceback is part of it


def file_handler(log_file: Path, *homes: str, max_bytes: int = MAX_BYTES) -> RotatingFileHandler:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(_MaskingFormatter(homes))
    return handler


def setup(log_dir: Path) -> Path:
    """Call once when the app starts. Returns the log file."""
    log_file = log_dir / "app.log"
    root = logging.getLogger()
    home = str(Path.home())
    root.addHandler(file_handler(log_file, home, short_path(home)))
    root.setLevel(logging.INFO)
    # Whatever nobody caught is what a bug report needs most.
    sys.excepthook = lambda *exc: root.critical("uncaught exception", exc_info=exc)
    threading.excepthook = lambda args: root.critical(
        "uncaught exception in thread %s",
        args.thread.name if args.thread else "?",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),  # type: ignore[arg-type]
    )
    return log_file
