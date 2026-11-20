"""Build the installer from a clean state, print its SHA-256 and scan it with Windows Defender.

Steps: delete build/ and packaging/output/ -> npm ci + npm run build -> fetch the pinned
external programs into build/bin -> PyInstaller into build/dist -> check nothing is missing
-> third-party licenses into build/licenses -> Inno Setup into packaging/output/ -> SHA-256
file -> Defender scan.

Needs Node, uv (with the build group) and Inno Setup 7 (ISCC.exe). Run from anywhere:
    python scripts/build_installer.py

--test-update-source builds a test version that asks 127.0.0.1 for updates instead of
GitHub (scripts/manual/serve_update.py; docs/decisions/0019). Its installer is named
...-TEST.exe and must never be uploaded. Without the option the build fails if the marker
somehow ended up in the app.

Without it the build also checks it is fit for upload: packaging/output/ holds only the
installer and its .sha256, and the installer's file list (build/installer-manifest.txt) has
no marker. The release workflow adds --release-tag v<version>, which must match __version__.
"""

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
from importlib import metadata
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
LICENSE_FILE = re.compile(r"(?i)^(licen[cs]e|copying|notice)")
# Packages that ship no license file, with the one kept in packaging/licenses instead.
SEPARATE_LICENSES = {"proxy-tools": "proxy_tools-LICENSE.txt"}


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


def check_release_output(app_version: str, manifest: str, files: list[str]) -> list[str]:
    """What is wrong with a build meant for upload (empty when nothing is)."""
    name = installer_name(app_version, test=False)
    problems = []
    if not re.fullmatch(r"MediaDownloader-Setup-\d+\.\d+\.\d+(-rc\.\d+)?\.exe", name):
        problems.append(f"unexpected installer name {name}")
    if sorted(files) != sorted([name, f"{name}.sha256"]):
        problems.append(f"output should be {name} and its .sha256, found {sorted(files)}")
    if TEST_MARKER in manifest:
        problems.append(f"the installer contains {TEST_MARKER}")
    if not manifest.strip():
        problems.append("the installer manifest is empty")
    return problems


def write_checksum(installer: Path) -> str:
    """Write <installer>.sha256 next to it in sha256sum's format and return the digest."""
    digest = hashlib.sha256(installer.read_bytes()).hexdigest()
    # LF even on Windows: GNU sha256sum -c before coreutils 9.0 rejects CRLF.
    installer.with_name(f"{installer.name}.sha256").write_text(
        f"{digest}  {installer.name}\n", encoding="ascii", newline="\n"
    )
    return digest


def _key(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _names(requirements: list[str]) -> list[str]:
    """Package names of requirement strings, leaving out the ones only an extra asks for."""
    return [re.match(r"[A-Za-z0-9._-]+", r)[0] for r in requirements if "extra ==" not in r]  # type: ignore[index]


def python_licenses(site: Path, separate: set[str]) -> tuple[str, list[str]]:
    """The license files of backend/pyproject.toml's dependencies and what they need, as
    installed in site, in one text; and the packages that have none. Requirements that are
    not installed are skipped: their platform markers (macOS, Linux) did not match."""
    installed = {_key(d.metadata["Name"]): d for d in metadata.distributions(path=[str(site)])}
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    todo, seen, parts, missing = _names(project["project"]["dependencies"]), set(), [], []
    while todo:
        key = _key(todo.pop())
        if key in seen or key not in installed:
            continue
        seen.add(key)
        dist = installed[key]
        todo += _names(dist.requires or [])
        files = [f for f in dist.files or [] if ".dist-info" in str(f) and LICENSE_FILE.match(f.name)]
        texts = [Path(str(dist.locate_file(f))).read_text(encoding="utf-8") for f in files]
        if not texts and key not in separate:
            missing.append(key)
        header = f"{dist.metadata['Name']} {dist.version}"
        note = "\n(see its own file in this folder)\n" if not texts else ""
        parts.append(f"{'=' * 72}\n{header}\n{'=' * 72}\n{note}" + "\n".join(texts))
    return "\n\n".join(sorted(parts, key=str.lower)), missing


def write_licenses() -> None:
    """build/licenses: the Python packages and Python itself, and the npm packages bundled
    into the page. The installer puts them in {app}\\licenses with packaging/licenses."""
    venv = ROOT / "backend" / ".venv"
    home = re.search(r"^home = (.+)$", (venv / "pyvenv.cfg").read_text(encoding="utf-8"), re.M)
    python = Path(home[1].strip()) / "LICENSE.txt" if home else Path()
    separate = {_key(n) for n in SEPARATE_LICENSES}
    text, missing = python_licenses(venv / "Lib" / "site-packages", separate)
    frontend = ROOT / "frontend" / "dist" / "third-party-licenses.md"
    if missing or not python.is_file() or not frontend.is_file():
        sys.exit(f"license text missing: {missing or ''} {python} {frontend}")
    for name in SEPARATE_LICENSES.values():
        if not (ROOT / "packaging" / "licenses" / name).is_file():
            sys.exit(f"packaging/licenses/{name} is missing")
    out = BUILD / "licenses"
    out.mkdir(parents=True, exist_ok=True)
    python_text = python.read_text(encoding="utf-8", errors="replace")
    (out / "ThirdParty-Python.txt").write_text(
        f"Python packages in Media Downloader\n\n{text}\n\n{'=' * 72}\nPython runtime\n"
        f"{'=' * 72}\n{python_text}",
        encoding="utf-8",
    )
    shutil.copyfile(frontend, out / "ThirdParty-Frontend.md")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-update-source", action="store_true",
                        help="a test build that updates from 127.0.0.1 (never upload it)")
    parser.add_argument("--release-tag", metavar="TAG",
                        help="fail unless TAG is v<__version__> (used by the release workflow)")
    args = parser.parse_args()
    test = args.test_update_source
    app_version = version()
    if args.release_tag is not None and (test or args.release_tag != f"v{app_version}"):
        sys.exit(f"tag {args.release_tag} must be v{app_version}, without --test-update-source")
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
    write_licenses()
    run(
        [
            str(iscc), f"/DAppVersion={app_version}", f"/DVersionNumbers={numbers}",
            *(["/DTestBuild"] if test else []), str(ROOT / "packaging" / "installer.iss"),
        ]
    )

    installer = OUTPUT / installer_name(app_version, test)
    digest = write_checksum(installer)
    print(f"\n{installer}\n  {installer.stat().st_size:,} bytes\n  SHA-256 {digest}")
    if not test:
        manifest = (BUILD / "installer-manifest.txt").read_text(encoding="utf-8", errors="replace")
        files = [path.name for path in OUTPUT.iterdir()]
        if problems := check_release_output(app_version, manifest, files):
            sys.exit("not fit for upload:\n  " + "\n  ".join(problems))

    if DEFENDER.is_file():
        run([str(DEFENDER), "-Scan", "-ScanType", "3", "-File", str(installer),
             "-DisableRemediation"])
    else:
        print("Windows Defender not found: scan the installer yourself")
    return 0


if __name__ == "__main__":
    sys.exit(main())
