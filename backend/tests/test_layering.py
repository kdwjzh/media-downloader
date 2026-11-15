"""The dependency rules of CLAUDE.md section 4, checked on the source so CI stops a violation."""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
ENGINE = "infrastructure/engines/ytdlp/"
# Options and output markers that only the yt-dlp engine may know.
YT_DLP_ONLY = (
    "--ignore-config",
    "--js-runtimes",
    "--ffmpeg-location",
    "--no-quiet",
    "--merge-output-format",
    "--ppa",
    "[download]",
    "ERROR:",
)


def sources() -> list[tuple[str, str]]:
    return [
        (path.relative_to(APP).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(APP.rglob("*.py"))
    ]


def imports(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def offenders(folder: str, forbidden: tuple[str, ...], allowed: tuple[str, ...] = ()) -> list[str]:
    """Imports in app/<folder> of a forbidden module (or anything below it)."""
    return [
        f"{name} imports {module}"
        for name, source in sources()
        if name.startswith(folder) and name not in allowed
        for module in sorted(imports(source))
        if any(module == f or module.startswith(f + ".") for f in forbidden)
    ]


def test_the_check_itself_sees_imports() -> None:
    assert offenders("services/", ("app.services.ports",))  # or every test below proves nothing
    assert len(sources()) > 30


@pytest.mark.parametrize(
    ("folder", "forbidden"),
    [
        # Rule 1 and 3: the domain knows no other layer and touches no file, network or process.
        ("domain/", ("app.services", "app.infrastructure", "app.bridge", "app.composition")),
        ("domain/", ("subprocess", "socket", "urllib.request", "http", "sqlite3", "shutil",
                     "os", "pathlib", "tempfile", "ctypes")),  # fmt: skip
        # Rule 12: services reach the outside only through services/ports.py.
        ("services/", ("app.infrastructure", "app.bridge", "app.composition")),
        ("services/", ("subprocess", "socket", "urllib.request", "sqlite3", "ctypes")),
        ("infrastructure/", ("app.services", "app.bridge", "app.composition")),
        ("bridge/", ("app.infrastructure",)),
    ],
)
def test_a_layer_does_not_import_what_it_must_not(folder: str, forbidden: tuple[str, ...]) -> None:
    assert offenders(folder, forbidden) == []


def test_external_programs_and_the_network_have_one_way_in() -> None:
    assert offenders("", ("subprocess",), allowed=("infrastructure/process.py",)) == []
    assert offenders("", ("urllib.request", "http.client", "socket"),
                     allowed=("infrastructure/http.py",)) == []  # fmt: skip


def test_only_the_yt_dlp_engine_knows_yt_dlp() -> None:
    found = [
        f"{name} contains {needle!r}"
        for name, source in sources()
        if not name.startswith(ENGINE)
        for needle in YT_DLP_ONLY
        if needle in source
    ]
    assert found == []
    assert offenders("", ("yt_dlp",)) == []  # ADR 0003: the program is run, never imported
    callers = [name for name, source in sources() if "yt_dlp()" in source]
    assert all(name.startswith((ENGINE, "infrastructure/binaries/")) for name in callers)
