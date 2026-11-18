"""One version number: __version__ is the source; pyproject.toml must match it, and the
installer gets it from scripts/build_installer.py (which reads __version__)."""

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
