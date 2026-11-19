"""Build the installer from a clean state, print its SHA-256 and scan it with Windows Defender.

Steps: delete build/ and packaging/output/ -> npm ci + npm run build -> fetch the pinned
external programs into build/bin -> PyInstaller into build/dist -> check nothing is missing
-> Inno Setup into packaging/output/ -> SHA-256 file -> Defender scan.

Needs Node, uv (with the build group) and Inno Setup 7 (ISCC.exe). Run from anywhere:
    python scripts/build_installer.py

--test-update-source builds a test version that asks 127.0.0.1 for updates instead of
GitHub (scripts/manual/serve_update.py; docs/decisions/0019). Its installer is named
...-TEST.exe and must never be uploaded. Without the option the build fails if the marker
somehow ended up in the app.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
OUTPUT = ROOT / "packaging" / "output"
APP = BUILD / "dist" / "MediaDownloader"
# Files whose absence gives an app that starts but is broken.
REQUIRED = [
    "MediaDownloader.exe",
    "_internal/frontend/dist/index.html",
    "_internal/webview/lib/Microsoft.Web.WebView2.Core.dll",
    "_internal/webview/lib/Microsoft.Web.WebView2.WinForms.dll",
]
ISCC = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 7" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 7" / "ISCC.exe",
]
DEFENDER = Path(os.environ.get("ProgramFiles", "")) / "Windows Defender" / "MpCmdRun.exe"
# Must match TEST_MARKER in packaging/media-downloader.spec and backend/app/infrastructure/releases.py.
TEST_MARKER = "update-source-test"


def version() -> str:
    text = (ROOT / "backend" / "app" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'^__version__ = "([^"]+)"', text, re.MULTILINE)
    if not found:
        sys.exit("__version__ not found in backend/app/__init__.py")
    return found[1]


def run(args: list[str], cwd: Path = ROOT) -> None:
    print(f"\n> {' '.join(args)}", flush=True)
    # shell=True only so that npm.cmd is found; every argument is a constant.
    subprocess.run(args, cwd=cwd, check=True, shell=args[0] == "npm")


def missing_files() -> list[str]:
    gone = [name for name in REQUIRED if not (APP / name).is_file()]
    if not list((APP / "_internal" / "frontend" / "dist" / "assets").glob("*.woff2")):
        gone.append("_internal/frontend/dist/assets/*.woff2 (the fonts)")
    return gone


def installer_name(app_version: str, test: bool) -> str:
    return f"MediaDownloader-Setup-{app_version}{'-TEST' if test else ''}.exe"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-update-source", action="store_true",
                        help="a test build that updates from 127.0.0.1 (never upload it)")
    test = parser.parse_args().test_update_source
    app_version = version()
    numbers = app_version.split("-")[0]  # Windows file versions are numbers only
    iscc = next((path for path in ISCC if path.is_file()), None)
    if iscc is None:
        sys.exit("ISCC.exe not found: install Inno Setup 7")

    for folder in (BUILD, OUTPUT):
        shutil.rmtree(folder, ignore_errors=True)
    if test:
        BUILD.mkdir()
        (BUILD / TEST_MARKER).write_text("updates come from 127.0.0.1\n", encoding="utf-8")
    run(["npm", "ci"], ROOT / "frontend")
    run(["npm", "run", "build"], ROOT / "frontend")
    run([sys.executable, "scripts/fetch_binaries.py", "--dest", "build/bin", "--no-ffprobe"])
    run(
        [
            "uv", "run", "--directory", "backend", "--group", "build", "pyinstaller",
            "../packaging/media-downloader.spec", "--noconfirm",
            "--distpath", "../build/dist", "--workpath", "../build/pyinstaller",
        ]
    )
    if gone := missing_files():
        sys.exit("missing from the packaged app:\n  " + "\n  ".join(gone))
    if (APP / "_internal" / TEST_MARKER).is_file() != test:
        sys.exit(f"the test update source is {'missing from' if test else 'in'} the app")
    run(
        [
            str(iscc), f"/DAppVersion={app_version}", f"/DVersionNumbers={numbers}",
            *(["/DTestBuild"] if test else []), str(ROOT / "packaging" / "installer.iss"),
        ]
    )

    installer = OUTPUT / installer_name(app_version, test)
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    (OUTPUT / f"{installer.name}.sha256").write_text(f"{digest}  {installer.name}\n")
    print(f"\n{installer}\n  {installer.stat().st_size:,} bytes\n  SHA-256 {digest}")

    if DEFENDER.is_file():
        run([str(DEFENDER), "-Scan", "-ScanType", "3", "-File", str(installer),
             "-DisableRemediation"])
    else:
        print("Windows Defender not found: scan the installer yourself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
