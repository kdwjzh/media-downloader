"""Where this app keeps its own files, and the user's Downloads folder.

The folders are asked from Windows: they can be moved, so they are never assumed.
"""

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

_DOWNLOADS = "{374DE290-123F-4565-9164-39C4925E467B}"
_ROAMING = "{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}"
_LOCAL = "{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}"

# A development run never touches the settings and history of the installed app.
_FOLDER = "media-downloader" if getattr(sys, "frozen", False) else "media-downloader-dev"

_shell32 = ctypes.WinDLL("shell32")
_ole32 = ctypes.WinDLL("ole32")
_ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
_shell32.SHGetKnownFolderPath.argtypes = [
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_void_p),
]
_ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
_ole32.CoTaskMemFree.restype = None


def _known_folder(folder_id: str) -> Path:
    guid = (ctypes.c_byte * 16)()
    found = ctypes.c_void_p()
    try:
        if _ole32.CLSIDFromString(folder_id, guid) != 0 or (
            _shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(found)) != 0
        ):
            raise OSError(f"Windows did not give the folder {folder_id}")
        assert found.value
        return Path(ctypes.wstring_at(found.value))
    finally:
        _ole32.CoTaskMemFree(found)


def downloads_dir() -> str:
    return str(_known_folder(_DOWNLOADS))


def data_dir() -> Path:
    """Settings and history (%APPDATA%)."""
    return _known_folder(_ROAMING) / _FOLDER


def local_dir() -> Path:
    """Log files and caches: things that only mean something on this computer
    (%LOCALAPPDATA%)."""
    return _known_folder(_LOCAL) / _FOLDER
