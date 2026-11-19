"""A stand-in for GitHub's releases, on 127.0.0.1 only, for testing the app update with two
local builds (docs/decisions/0019). Only a test build (build_installer.py
--test-update-source) asks here.

    python scripts/manual/serve_update.py packaging/output/MediaDownloader-Setup-1.0.0-rc.2-TEST.exe

It answers like GitHub would for the version in the file name: releases/latest, the
installer under its release name (without -TEST) and its .sha256 file. Ctrl+C stops it,
also in the middle of a download (that is how to test a connection that drops).

  --rate MB      bytes per second, in MiB (default 2), so the progress can be watched
  --bad-checksum the .sha256 file names a different hash: the app must not install
"""

import argparse
import hashlib
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8765  # releases.TEST_PORT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("installer", type=Path)
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument("--bad-checksum", action="store_true")
    options = parser.parse_args()

    found = re.fullmatch(r"MediaDownloader-Setup-(.+?)(-TEST)?\.exe", options.installer.name)
    if not found or not options.installer.is_file():
        sys.exit("give the path of a MediaDownloader-Setup-<version>[-TEST].exe")
    version = found[1]
    name = f"MediaDownloader-Setup-{version}.exe"
    body = options.installer.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    if options.bad_checksum:
        digest = hashlib.sha256(b"not the installer").hexdigest()
    routes = {
        "/releases/latest": json.dumps({"tag_name": f"v{version}"}).encode(),
        f"/releases/download/v{version}/{name}.sha256": f"{digest}  {name}\n".encode(),
    }
    chunk = max(1, int(options.rate * 1024 * 1024 / 10))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == f"/releases/download/v{version}/{name}":
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                for start in range(0, len(body), chunk):
                    self.wfile.write(body[start : start + chunk])
                    time.sleep(0.1)  # about --rate MiB a second
                return
            data = routes.get(self.path)
            self.send_response(200 if data else 404)
            self.send_header("Content-Length", str(len(data or b"")))
            self.end_headers()
            self.wfile.write(data or b"")

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    server.daemon_threads = True
    print(f"Serving v{version} ({len(body):,} bytes, SHA-256 {digest}) on http://127.0.0.1:{PORT}")
    print("Ctrl+C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
