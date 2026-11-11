import sys
from pathlib import Path

import webview

from app.bridge.api import BridgeApi

DEV_URL = "http://localhost:5173"
DIST_INDEX = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html"


def main() -> None:
    dev = "--dev" in sys.argv[1:]
    if not dev and not DIST_INDEX.is_file():
        sys.exit("frontend/dist not found: run `npm run build` in frontend/, or start with --dev")
    webview.create_window(
        "Media Downloader", DEV_URL if dev else str(DIST_INDEX), js_api=BridgeApi()
    )
    webview.start(debug=dev)


if __name__ == "__main__":
    main()
