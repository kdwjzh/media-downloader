"""MediaInfoService: looks a pasted URL up, and remembers titles for the queue."""

import re
import threading
from collections import OrderedDict
from concurrent.futures import Future

from app.domain.engine import MediaEngine
from app.domain.media import MediaInfo, PlaylistInfo

# One entry is a URL, a title and a thumbnail URL (about 300 bytes), so this is under 2 MB.
# A playlist of 1,700 entries was seen in stage 1; three of those still fit.
CACHE_LIMIT = 5000

# "youtu.be/abc", "www.youtube.com/watch?v=abc": a host with a dot, then nothing or a path.
_BARE_URL = re.compile(r"[\w-]+(\.[\w-]+)+([/?#:].*)?")


def normalize(text: str) -> str:
    """Tidies what the user pasted: no surrounding whitespace, and https:// in front of
    something that looks like a URL without a scheme. Anything else is returned as it is,
    for the engine to refuse."""
    url = text.strip()
    if "://" not in url and not any(c.isspace() for c in url) and _BARE_URL.fullmatch(url):
        url = "https://" + url
    return url


class MediaInfoService:
    def __init__(self, engine: MediaEngine) -> None:
        self._engine = engine
        self._lock = threading.Lock()
        self._known: OrderedDict[str, tuple[str, str | None]] = OrderedDict()
        self._pending: dict[str, Future[MediaInfo | PlaylistInfo]] = {}

    def lookup(self, text: str) -> MediaInfo | PlaylistInfo:
        """Blocks for a few seconds. Raises EngineError."""
        url = normalize(text)
        with self._lock:
            pending = self._pending.get(url)
            if pending is None:
                mine: Future[MediaInfo | PlaylistInfo] = Future()
                self._pending[url] = mine
        if pending is not None:
            return pending.result()  # someone is already looking this URL up: share the answer
        try:
            info = self._engine.fetch_info(url)
        except BaseException as error:
            with self._lock:
                del self._pending[url]
            mine.set_exception(error)
            raise
        with self._lock:
            del self._pending[url]
            if isinstance(info, MediaInfo):
                self._remember(url, info.title, info.thumb)
            else:
                for entry in info.entries:
                    if entry.title is not None:
                        self._remember(entry.url, entry.title, entry.thumb)
        mine.set_result(info)
        return info

    def known(self, url: str) -> tuple[str, str | None] | None:
        """(title, thumbnail URL) of a URL that was looked up before, or None."""
        with self._lock:
            return self._known.get(url)

    def remember(self, url: str, title: str, thumb: str | None = None) -> None:
        with self._lock:
            self._remember(url, title, thumb)

    def _remember(self, url: str, title: str, thumb: str | None) -> None:
        self._known[url] = (title, thumb)
        self._known.move_to_end(url)
        while len(self._known) > CACHE_LIMIT:
            self._known.popitem(last=False)
