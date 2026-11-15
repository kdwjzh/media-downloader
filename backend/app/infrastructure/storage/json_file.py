"""A small JSON file that is either the old content or the new one, never half of it."""

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)


def set_aside(path: Path) -> None:
    """Renames a file nobody can read to <name>.broken-<time><ext>, so the app can start
    over while the user can still get at it."""
    kept = path.with_name(f"{path.stem}.broken-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
    try:
        os.replace(path, kept)
    except OSError:
        log.exception("could not set %s aside", path.name)


class JsonFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, object] | None:
        """None when there is no file, or when it could not be read (it is set aside then)."""
        try:
            data = json.loads(self._path.read_text("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("not a JSON object")
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as error:  # ValueError: bad JSON or bad UTF-8
            log.error("%s is unusable and was set aside: %s", self._path.name, error)
            set_aside(self._path)
            return None
        return data

    def save(self, data: dict[str, object]) -> None:
        """Raises OSError. A crash or power cut leaves the previous file in place."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        new = self._path.with_name(self._path.name + ".tmp")
        with open(new, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(new, self._path)
