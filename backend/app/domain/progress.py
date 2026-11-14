from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Progress:
    done_bytes: int = 0
    percent: int | None = 0
    total_bytes: int | None = None
    speed_bps: float | None = None
    eta_sec: int | None = None


class ProgressTracker:
    """Turns per-file byte counts into one progress for the whole task.

    An MP4 is two downloads (video, then audio) whose byte counts each start from zero;
    the user must see a single bar that runs from 0 to 100 once.
    """

    def __init__(self) -> None:
        self._sizes: list[int | None] = []
        self._done: list[int] = []
        self._percent = 0

    def expect(self, sizes: Sequence[int | None]) -> None:
        """File sizes known before the download starts (from the media info)."""
        self._grow(len(sizes))
        for i, size in enumerate(sizes):
            if size:
                self._sizes[i] = size

    def update(
        self,
        file_index: int,
        file_count: int,
        downloaded_bytes: int,
        total_bytes: int | None = None,
        speed_bps: float | None = None,
    ) -> Progress:
        if not 0 <= file_index < file_count:
            raise ValueError(f"file_index {file_index} is outside 0..{file_count - 1}")
        self._grow(file_count)
        if total_bytes:
            self._sizes[file_index] = total_bytes
        self._done[file_index] = downloaded_bytes
        # A later file only starts once the earlier ones are complete.
        for i in range(file_index):
            self._done[i] = self._sizes[i] or self._done[i]

        done = sum(self._done)
        known = [s for s in self._sizes if s]
        total = sum(known) if len(known) == len(self._sizes) else None
        current = self._sizes[file_index]

        fraction: float | None
        if total:
            fraction = done / total
        elif current:
            # Some size is unknown: give every file an equal share of the bar.
            fraction = (file_index + min(downloaded_bytes / current, 1)) / len(self._sizes)
        else:
            fraction = None

        percent: int | None = None
        if fraction is not None:
            self._percent = max(self._percent, min(int(fraction * 100), 100))
            percent = self._percent

        eta: int | None = None
        if total and speed_bps and speed_bps > 0:
            eta = max(0, round((total - done) / speed_bps))

        return Progress(done, percent, total, speed_bps, eta)

    def _grow(self, count: int) -> None:
        missing = count - len(self._sizes)
        self._sizes += [None] * missing
        self._done += [0] * missing
