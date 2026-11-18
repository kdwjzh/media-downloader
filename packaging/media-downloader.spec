# PyInstaller settings: one folder (MediaDownloader.exe + _internal), no console window.
# Run through scripts/build_installer.py, which builds frontend/dist first.
# The external programs are not in here: the installer puts them in
# %LOCALAPPDATA%\media-downloader\bin (docs/decisions/0018).

from pathlib import Path

ROOT = Path(SPECPATH).parent  # noqa: F821 - SPECPATH is set by PyInstaller

a = Analysis(  # noqa: F821
    [str(ROOT / "backend" / "app" / "main.py")],
    pathex=[str(ROOT / "backend")],
    # main.py finds the page at <_MEIPASS>/frontend/dist when packaged. The fonts are in it.
    datas=[(str(ROOT / "frontend" / "dist"), "frontend/dist")],
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
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MediaDownloader", upx=False)  # noqa: F821
