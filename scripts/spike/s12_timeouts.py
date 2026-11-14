"""Stage 3b: how long the engine's arguments take to report a dead network, and whether a
very long title downloads once trimmed.

A "black hole" is the slow kind of outage: connections open but nothing ever answers, so
every attempt runs into the socket timeout. (A refused connection fails at once.)
"""

import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from common import LONG, ZH, ZOO, fresh  # noqa: E402
from s04_errors import Proxy  # noqa: E402

from app.domain.engine import DownloadRequest  # noqa: E402
from app.domain.media import Format  # noqa: E402
from app.infrastructure.engines.ytdlp import args  # noqa: E402
from app.infrastructure.engines.ytdlp.errors import classify  # noqa: E402
from app.infrastructure.engines.ytdlp.parse import DownloadOutput  # noqa: E402

NO_WINDOW = subprocess.CREATE_NO_WINDOW


class FreezableProxy(Proxy):
    """Like Proxy, but freeze() makes it a black hole instead of closing connections."""

    frozen = False

    def tunnel(self, client: socket.socket) -> None:
        if self.frozen:
            time.sleep(600)
            return
        super().tunnel(client)

    @staticmethod
    def pump(source: socket.socket, target: socket.socket) -> None:
        try:
            while data := source.recv(65536):
                while FreezableProxy.frozen:
                    time.sleep(1)
                target.sendall(data)
        except OSError:
            pass


def with_proxy(command: list[str], port: int) -> list[str]:
    return [*command[: len(args.base())], "--proxy", f"http://127.0.0.1:{port}", *command[len(args.base()) :]]


def lookup_black_hole() -> None:
    proxy = FreezableProxy()
    FreezableProxy.frozen = True
    start = time.perf_counter()
    out = subprocess.run(with_proxy(args.info(ZH), proxy.port), capture_output=True, encoding="utf-8",
                         errors="replace", creationflags=NO_WINDOW)  # fmt: skip
    print(f"\n## lookup into a black hole {args.LOOKUP_NETWORK}: exit={out.returncode} "
          f"after {time.perf_counter() - start:.1f}s -> {classify(out.stderr).code}")  # fmt: skip
    print("  ", out.stderr.strip().splitlines()[-1][:200])
    FreezableProxy.frozen = False


def download_black_hole(refuse: bool = False) -> None:
    proxy = FreezableProxy()
    folder = fresh(f"timeouts-{refuse}")
    command = args.download(DownloadRequest("t", LONG, Format.MP4, 2160, str(folder)), folder / "task")
    process = subprocess.Popen(with_proxy(command, proxy.port), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding="utf-8", errors="replace", creationflags=NO_WINDOW)  # fmt: skip
    assert process.stdout
    output = DownloadOutput()
    frozen_at = None
    kind = "refused connections" if refuse else "a black hole"
    print(f"\n## download, then {kind} {args.DOWNLOAD_NETWORK}")
    for line in process.stdout:
        event = output.feed(line)
        if frozen_at is None and '"downloaded_bytes": 2' in line:
            if refuse:
                proxy.cut()
            else:
                FreezableProxy.frozen = True
            frozen_at = time.perf_counter()
        elif frozen_at and event and type(event).__name__ == "ConnectionLost":
            print(f"   +{time.perf_counter() - frozen_at:5.1f}s {event}")
    code = process.wait()
    print(f"  exit={code} {time.perf_counter() - (frozen_at or 0):.1f}s after the freeze -> "
          f"{classify(output.other_text).code}")  # fmt: skip
    FreezableProxy.frozen = False


def long_title() -> None:
    folder = fresh("longtitle")
    command = args.download(DownloadRequest("t", ZOO, Format.MP3, 128, str(folder)), folder / "task")
    command[-2:-2] = ["--replace-in-metadata", "title", "^.*$", "長" * 300]
    out = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    made = [p.name for p in (folder / "task").iterdir()]
    print(f"\n## 300-character title with --trim-filenames {args.TRIM}: exit={out.returncode}, "
          f"file name is {len(made[0]) if made else 0} characters: {made[0][:12] if made else out.stderr[-300:]}...")  # fmt: skip


if __name__ == "__main__":
    threading.excepthook = lambda _args: None  # proxy threads die noisily when sockets close
    long_title()
    lookup_black_hole()
    download_black_hole(refuse=True)
    download_black_hole()
