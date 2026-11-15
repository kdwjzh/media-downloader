"""Opens things with Windows: a folder, a file, a web page.

Nothing here builds a command line, so a path with commas, spaces or any other character
cannot be split or read as an option (`explorer /select,<path>` can).
"""

import ctypes
import os
from ctypes import wintypes

_shell32 = ctypes.WinDLL("shell32")
_ole32 = ctypes.WinDLL("ole32")
_shell32.SHParseDisplayName.argtypes = [
    wintypes.LPCWSTR,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_void_p),
    wintypes.ULONG,
    ctypes.c_void_p,
]
_shell32.SHParseDisplayName.restype = ctypes.HRESULT  # a failure is raised as OSError
_shell32.SHOpenFolderAndSelectItems.argtypes = [
    ctypes.c_void_p,
    wintypes.UINT,
    ctypes.c_void_p,
    wintypes.DWORD,
]
_shell32.SHOpenFolderAndSelectItems.restype = ctypes.HRESULT
_ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
_ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
_ole32.CoTaskMemFree.restype = None

_APARTMENT_THREADED = 0x2


class WindowsShell:
    """Every method raises OSError when Windows refuses."""

    def select_file(self, path: str) -> None:
        """Opens the file's folder in File Explorer with the file selected."""
        # The caller is a worker thread that may never have used COM. 0 and 1 mean it is
        # initialised now and has to be released; anything else: it already was, differently.
        initialised = _ole32.CoInitializeEx(None, _APARTMENT_THREADED) in (0, 1)
        item = ctypes.c_void_p()
        try:
            _shell32.SHParseDisplayName(os.path.abspath(path), None, ctypes.byref(item), 0, None)
            _shell32.SHOpenFolderAndSelectItems(item, 0, None, 0)
        finally:
            _ole32.CoTaskMemFree(item)
            if initialised:
                _ole32.CoUninitialize()

    def open_path(self, path: str) -> None:
        """A folder opens in File Explorer, a file in the program Windows uses for it."""
        os.startfile(os.path.abspath(path))

    def open_url(self, url: str) -> None:
        os.startfile(url)
