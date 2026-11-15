"""Stand-ins for the ports of app/services/ports.py. Nothing here touches a real folder of
the user, the network or Windows."""

from dataclasses import dataclass, field

from app.domain.engine import OnDuplicate
from app.domain.media import Format
from app.services.ports import FinishedDownload

JPEG = b"\xff\xd8\xff small picture"


@dataclass
class InMemorySettings:
    download_dir: str
    max_concurrent: int = 3
    on_duplicate: OnDuplicate = OnDuplicate.RENAME
    last_format: tuple[Format, int] | None = None

    def remember_format(self, format: Format, quality: int) -> None:
        self.last_format = (format, quality)

    def dirs_to_clean(self) -> list[str]:
        return [self.download_dir]


@dataclass
class InMemoryHistory:
    records: list[FinishedDownload] = field(default_factory=list)

    def record(self, download: FinishedDownload) -> None:
        self.records.append(download)


class MemoryFile:
    """A KeyValueFile."""

    def __init__(self, data: dict[str, object] | None = None) -> None:
        self.data = data
        self.fail = False

    def load(self) -> dict[str, object] | None:
        return self.data

    def save(self, data: dict[str, object]) -> None:
        if self.fail:
            raise OSError("disk full")
        self.data = data


class FakeThumbnails:
    def __init__(self, image: bytes | None = JPEG) -> None:
        self.image = image
        self.asked: list[str] = []

    def make(self, url: str) -> bytes | None:
        self.asked.append(url)
        return self.image


class FakeShell:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.refuse: set[str] = set()

    def select_file(self, path: str) -> None:
        self._call("select_file", path)

    def open_path(self, path: str) -> None:
        self._call("open_path", path)

    def open_url(self, url: str) -> None:
        self._call("open_url", url)

    def _call(self, name: str, target: str) -> None:
        if name in self.refuse:
            raise OSError("Windows said no")
        self.calls.append((name, target))
