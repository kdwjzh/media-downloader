# PyInstaller settings: one folder (MediaDownloader.exe + _internal), no console window.
# Run through scripts/build_installer.py, which builds frontend/dist first.
# The external programs are not in here: the installer puts them in
# %LOCALAPPDATA%\media-downloader\bin (docs/decisions/0018).

import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is set by PyInstaller
VERSION = re.search(
    r'^__version__ = "([^"]+)"',
    (ROOT / "backend" / "app" / "__init__.py").read_text(encoding="utf-8"),
    re.MULTILINE,
)[1]
# The numeric version has four numbers only, so 1.0.0-rc.2 and 1.0.0 both show 1.0.0.0;
# the text fields carry the full version (docs/decisions/0020). Nothing compares the number.
NUMBERS = (*map(int, VERSION.split("-")[0].split(".")), 0)
VERSION_INFO = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMBERS, prodvers=NUMBERS),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("FileDescription", "Media Downloader"),
            StringStruct("FileVersion", VERSION),
            StringStruct("ProductName", "Media Downloader"),
            StringStruct("ProductVersion", VERSION),
            StringStruct("LegalCopyright", "Copyright (c) 2026 kdwjzh"),
            StringStruct("OriginalFilename", "MediaDownloader.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
    ],
)
# Only a test build (scripts/build_installer.py --test-update-source) has this file; it makes
# the app ask 127.0.0.1 for updates (backend/app/infrastructure/releases.py). build/ is
# deleted at the start of every build, so an official build never picks up an old one.
TEST_MARKER = ROOT / "build" / "update-source-test"

a = Analysis(  # noqa: F821
    [str(ROOT / "backend" / "app" / "main.py")],
    pathex=[str(ROOT / "backend")],
    # main.py finds the page at <_MEIPASS>/frontend/dist when packaged. The fonts are in it.
    datas=[(str(ROOT / "frontend" / "dist"), "frontend/dist")]
    + ([(str(TEST_MARKER), ".")] if TEST_MARKER.is_file() else []),
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MediaDownloader",
    console=False,  # old bug U2: no console window
    icon=str(ROOT / "brand" / "icons" / "app.ico"),
    version=VERSION_INFO,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MediaDownloader", upx=False)  # noqa: F821
