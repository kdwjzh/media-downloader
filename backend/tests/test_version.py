"""One version number: __version__ is the source; pyproject.toml and uv.lock must match it,
and the installer gets it from scripts/build_installer.py (which reads __version__ and, for a
release, checks it against the tag)."""

import re
import tomllib
from pathlib import Path

from app import __version__

BACKEND = Path(__file__).resolve().parents[1]


def test_pyproject_matches_the_app_version() -> None:
    with (BACKEND / "pyproject.toml").open("rb") as file:
        assert tomllib.load(file)["project"]["version"] == __version__


def test_the_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+(-rc\.\d+)?", __version__)


def test_uv_lock_matches_the_app_version() -> None:
    # uv.lock stores the PEP 440 form: 1.0.0-rc.1 is written 1.0.0rc1.
    with (BACKEND / "uv.lock").open("rb") as file:
        packages = tomllib.load(file)["package"]
    locked = next(p["version"] for p in packages if p["name"] == "media-downloader")
    assert locked == re.sub(r"-rc\.(\d+)$", r"rc\1", __version__)
