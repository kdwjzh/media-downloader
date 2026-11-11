"""Start the dev environment: Vite dev server plus the pywebview window.

Run from anywhere:  python scripts/dev.py
Closing the window stops the dev server.
"""

import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 5173  # must match DEV_URL in backend/app/main.py


def which(name: str) -> str:
    exe = shutil.which(name)  # npm is npm.cmd on Windows
    if exe is None:
        sys.exit(f"{name} not found on PATH")
    return exe


def wait_for_port(vite: subprocess.Popen[bytes], timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if vite.poll() is not None:
            sys.exit("Vite dev server exited early (is port 5173 already in use?)")
        try:
            socket.create_connection(("localhost", PORT), timeout=1).close()
            return
        except OSError:
            time.sleep(0.2)
    sys.exit("Vite dev server did not start in time")


def main() -> int:
    vite = subprocess.Popen(
        [which("npm"), "run", "dev", "--", "--strictPort", "--port", str(PORT)],
        cwd=ROOT / "frontend",
    )
    try:
        wait_for_port(vite)
        return subprocess.run(
            [which("uv"), "run", "python", "-m", "app.main", "--dev"], cwd=ROOT / "backend"
        ).returncode
    finally:
        if sys.platform == "win32":
            # npm.cmd spawns node as a child; terminate() would leave it running.
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(vite.pid)], capture_output=True
            )
        else:
            vite.terminate()


if __name__ == "__main__":
    sys.exit(main())
