"""Item 7: exit code and stderr for each failure case.

"Network down" is simulated without touching the network adapter: an unreachable
proxy for "offline from the start", and a local CONNECT proxy that is shut down
mid-download for "connection lost while downloading".
"""

import socket
import threading
import time

from common import LONG, PROGRESS, fresh, popen, run

CASES = [
    ("not a URL", "not a url"),
    ("empty-ish URL", "https://"),
    ("unsupported site", "https://example.com/"),
    ("YouTube URL without id", "https://www.youtube.com/watch?v="),
    ("video does not exist", "https://www.youtube.com/watch?v=aaaaaaaaaaa"),
    ("private video", "https://www.youtube.com/watch?v=yZIXLfi8CZQ"),
    ("age-restricted, needs sign-in", "https://www.youtube.com/watch?v=Tq92D6wQ1mg"),
    ("age-restricted, but works without sign-in", "https://www.youtube.com/watch?v=HtVdAasjOgU"),
    ("removed by YouTube", "https://www.youtube.com/watch?v=Cr381pDsSsA"),
    ("geo-restricted (JP only)", "https://www.youtube.com/watch?v=sJL6WA-aGkQ"),
    ("playlist does not exist", "https://www.youtube.com/playlist?list=PLaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
]


def report(label: str, code: int, stderr: str, took: float) -> None:
    print(f"\n## {label}  exit={code}  {took:.1f}s")
    for line in stderr.strip().splitlines()[-6:]:
        print("  " + line[:420])


class Proxy:
    """Minimal HTTP CONNECT tunnel on 127.0.0.1 that can be cut off."""

    def __init__(self) -> None:
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.sockets: list[socket.socket] = []
        self.alive = True
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self) -> None:
        while self.alive:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            threading.Thread(target=self.tunnel, args=(client,), daemon=True).start()

    def tunnel(self, client: socket.socket) -> None:
        try:
            request = client.recv(65536).decode("latin-1")
            host, port = request.split()[1].rsplit(":", 1)
            upstream = socket.create_connection((host, int(port)), timeout=20)
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            self.sockets += [client, upstream]
            threading.Thread(target=self.pump, args=(upstream, client), daemon=True).start()
            self.pump(client, upstream)
        except (OSError, ValueError, IndexError):
            client.close()

    @staticmethod
    def pump(source: socket.socket, target: socket.socket) -> None:
        try:
            while data := source.recv(65536):
                target.sendall(data)
        except OSError:
            pass

    def cut(self) -> None:
        self.alive = False
        self.server.close()
        for sock in self.sockets:
            sock.close()


def lost_mid_download(extra: list[str], label: str) -> None:
    proxy = Proxy()
    folder = fresh("netdrop")
    start = time.perf_counter()
    process = popen(["--proxy", f"http://127.0.0.1:{proxy.port}", "-S", "res:2160", *extra,
                     *PROGRESS, "-P", str(folder), "--no-playlist", LONG])  # fmt: skip
    assert process.stdout
    tail: list[str] = []
    cut_at = None
    for line in process.stdout:
        if cut_at is None and '"downloaded_bytes": 2' in line:
            proxy.cut()
            cut_at = time.perf_counter()
        elif cut_at is not None and " DL " not in line:
            tail.append(line.rstrip())
        if cut_at and time.perf_counter() - cut_at > 240:
            tail.append("(gave up waiting after 240 s; killing)")
            import subprocess

            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            break
    code = process.wait()
    since = time.perf_counter() - (cut_at or start)
    print(f"\n## connection lost mid-download ({label})  exit={code}  ended {since:.1f}s after the cut")
    for line in tail[:4] + (["  ..."] if len(tail) > 10 else []) + tail[-6:]:
        print("  " + line[:420])
    for path in sorted(folder.rglob("*")):
        print(f"    {path.stat().st_size:>13,}  {path.name}")


if __name__ == "__main__":
    for label, url in CASES:
        start = time.perf_counter()
        result = run(["-J", "--no-playlist", url])
        report(f"{label}: {url}", result.returncode, result.stderr, time.perf_counter() - start)

    start = time.perf_counter()
    result = run(["--proxy", "http://127.0.0.1:9", "-J", "--no-playlist", LONG])
    report("offline from the start (unreachable proxy), defaults", result.returncode, result.stderr, time.perf_counter() - start)

    start = time.perf_counter()
    result = run(["--proxy", "http://127.0.0.1:9", "--socket-timeout", "10", "--extractor-retries", "1",
                  "-J", "--no-playlist", LONG])  # fmt: skip
    report("offline from the start, --extractor-retries 1", result.returncode, result.stderr, time.perf_counter() - start)

    lost_mid_download([], "defaults")
    lost_mid_download(["--retries", "2", "--socket-timeout", "10"], "--retries 2 --socket-timeout 10")
