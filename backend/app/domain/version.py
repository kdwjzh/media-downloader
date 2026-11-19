"""Version numbers as Semantic Versioning 2.0.0 orders them (https://semver.org, rules 9-11):
1.0.0-rc.1 < 1.0.0-rc.2 < 1.0.0-rc.10 < 1.0.0 < 1.0.1. A "v" in front is allowed, build
metadata (+...) is accepted and ignored."""

import re

_NUMBER = r"0|[1-9]\d*"
_PART = r"0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*"
_SEMVER = re.compile(
    rf"v?({_NUMBER})\.({_NUMBER})\.({_NUMBER})"
    rf"(?:-((?:{_PART})(?:\.(?:{_PART}))*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)

# (major, minor, patch, 1 for a release / 0 for a pre-release, pre-release parts)
VersionKey = tuple[int, int, int, int, tuple[tuple[int, int | str], ...]]


def parse(text: str) -> VersionKey | None:
    """A key that sorts like the versions do; None for anything that is not SemVer."""
    found = _SEMVER.fullmatch(text.strip())
    if not found:
        return None
    major, minor, patch, pre = found.groups()
    if pre is None:
        return int(major), int(minor), int(patch), 1, ()
    # Numbers sort as numbers and before words; a longer list of equal parts sorts later,
    # which is how tuples compare.
    parts = tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split("."))
    return int(major), int(minor), int(patch), 0, parts


def plain(text: str) -> str | None:
    """The version without the "v" and the build metadata, or None if it is not SemVer.
    Only these characters ever go into a file name or an address."""
    if parse(text) is None:
        return None
    return text.strip().removeprefix("v").split("+")[0]
