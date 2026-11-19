"""An official build never asks anything but GitHub for updates (docs/decisions/0019).

The test update source on 127.0.0.1 is switched on by one marker file that only
`scripts/build_installer.py --test-update-source` makes. These read the build files as text:
the marker's name is the same in all three places, only the option writes it, the build
checks the app for it, and a test installer is named so that it cannot pass for a release.
"""

import ast
import importlib.util
import re
from pathlib import Path

from app.infrastructure import releases

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "build_installer", ROOT / "scripts" / "build_installer.py"
)
assert _spec and _spec.loader
build_installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_installer)
BUILD = (ROOT / "scripts" / "build_installer.py").read_text(encoding="utf-8")
SPEC = (ROOT / "packaging" / "media-downloader.spec").read_text(encoding="utf-8")
ISS = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8-sig")


def test_the_marker_has_one_name_everywhere() -> None:
    assert f'TEST_MARKER = "{releases.TEST_MARKER}"' in BUILD
    assert f'TEST_MARKER = ROOT / "build" / "{releases.TEST_MARKER}"' in SPEC


def test_only_the_option_writes_the_marker() -> None:
    tree = ast.parse(BUILD)
    writes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "write_text"
        and "TEST_MARKER" in ast.unparse(node)
    ]  # fmt: skip
    assert len(writes) == 1
    guard = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.If) and any(w in ast.walk(node) for w in writes)
    )  # fmt: skip
    assert ast.unparse(guard.test) == "test"
    assert "rmtree" in BUILD.split("if test:")[0]  # build/ is emptied before, every time


def test_the_build_fails_when_the_marker_does_not_match_the_option() -> None:
    assert 'if (APP / "_internal" / TEST_MARKER).is_file() != test:' in BUILD
    assert "sys.exit(" in BUILD.split("!= test:")[1].splitlines()[1]


def test_a_test_installer_cannot_pass_for_a_release() -> None:
    test_name = re.search(r"#ifdef TestBuild\s+.*?OutputBaseFilename=(\S+)", ISS, re.S)
    assert test_name and test_name[1].endswith("-TEST")
    assert '"/DTestBuild"] if test else' in BUILD
    # The app only ever downloads the release's own name, never ...-TEST.exe.
    assert releases.installer_name("1.0.0") == "MediaDownloader-Setup-1.0.0.exe"


def test_without_the_marker_the_source_is_github_over_https() -> None:
    assert releases.source() is releases.GITHUB
    assert releases.GITHUB.latest.startswith("https://api.github.com/")
    assert releases.GITHUB.download.startswith("https://github.com/")
    assert not releases.GITHUB.loopback_http
    assert "127.0.0.1" not in repr(releases.GITHUB)


def test_a_release_build_has_only_the_two_files_and_no_marker() -> None:
    check = build_installer.check_release_output
    name = "MediaDownloader-Setup-1.0.0-rc.2.exe"
    good = [name, f"{name}.sha256"]
    assert check("1.0.0-rc.2", "_internal/index.html", good) == []
    assert check("1.0.0-rc.2", f"_internal/{releases.TEST_MARKER}", good)
    assert check("1.0.0-rc.2", "", good)
    assert check("1.0.0-rc.2", "x", [*good, "extra.txt"])
    assert check("1.0.0-rc.2", "x", [name])
    assert check("1.0.0-beta", "x", ["MediaDownloader-Setup-1.0.0-beta.exe",
                                     "MediaDownloader-Setup-1.0.0-beta.exe.sha256"])


def test_the_workflows_never_build_a_test_installer() -> None:
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert "test-update-source" not in workflow.read_text(encoding="utf-8"), workflow.name
