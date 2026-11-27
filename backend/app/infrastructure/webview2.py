"""Whether the WebView2 Runtime can start, asked of WebView2's own loader: the same lookup the
window makes, so a registry entry naming a version that is not on disk fails here too, and
WEBVIEW2_BROWSER_EXECUTABLE_FOLDER is honoured. See docs/decisions/0023."""

import ctypes
import logging
from ctypes import wintypes
from pathlib import Path

log = logging.getLogger(__name__)


def problem(loader: Path) -> int | None:
    """The HRESULT the loader gives when no usable runtime is found; None when one is, or when
    the loader itself can't be used (then the window is tried as before rather than stopping
    an app that may work)."""
    try:
        dll = ctypes.WinDLL(str(loader))
        available = dll.GetAvailableCoreWebView2BrowserVersionString
    except (OSError, AttributeError):
        log.warning("could not ask WebView2Loader whether the runtime is there", exc_info=True)
        return None
    available.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p)]
    available.restype = ctypes.c_long
    version = ctypes.c_void_p()
    result = available(None, ctypes.byref(version)) & 0xFFFFFFFF
    if version:
        ctypes.windll.ole32.CoTaskMemFree(version)
    # The loader can succeed and still give no version: no runtime either.
    return result or (None if version else 0x80070002)
