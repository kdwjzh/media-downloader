"""Download yt-dlp, FFmpeg (ffmpeg + ffprobe) and Deno into bin/ (git-ignored).

Every download is checked against the SHA-256 published next to it before it is
used. Existing files are kept; delete bin/ to fetch again.

Run from anywhere:  python scripts/fetch_binaries.py
Packaging uses:     python scripts/fetch_binaries.py --dest build/bin --no-ffprobe
(the installer does not ship ffprobe: MP3 covers and MP4 merging do not need it)
"""

import argparse
import hashlib
import re
import sys
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "bin"
TIMEOUT = 60
# GitHub serves release assets through redirects to these hosts.
ALLOWED_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}

YTDLP = "https://github.com/yt-dlp/yt-dlp/releases/download/2026.10.26"
DENO = "https://github.com/denoland/deno/releases/download/v2.9.8"
# A month-end build: FFmpeg-Builds deletes its daily builds after about two weeks but has
# kept every month-end one. Its source is listed in packaging/licenses/FFmpeg-SOURCE.txt;
# change both together.
FFMPEG = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/autobuild-2026-10-31-18-18"
FFMPEG_NAME = "ffmpeg-N-128251-g6d1bfd7609-win64-gpl"
FFPROBE = f"{FFMPEG_NAME}/bin/ffprobe.exe"

# (asset URL, checksum URL, {member inside the zip, or "" for a plain file: target name})
ASSETS: list[tuple[str, str, dict[str, str]]] = [
    (f"{YTDLP}/yt-dlp.exe", f"{YTDLP}/SHA2-256SUMS", {"": "yt-dlp.exe"}),
    (
        f"{DENO}/deno-x86_64-pc-windows-msvc.zip",
        f"{DENO}/deno-x86_64-pc-windows-msvc.zip.sha256sum",
        {"deno.exe": "deno.exe"},
    ),
    (
        f"{FFMPEG}/{FFMPEG_NAME}.zip",
        f"{FFMPEG}/checksums.sha256",
        {f"{FFMPEG_NAME}/bin/ffmpeg.exe": "ffmpeg.exe", FFPROBE: "ffprobe.exe"},
    ),
]


def open_url(url: str):  # type: ignore[no-untyped-def]
    response = urllib.request.urlopen(url, timeout=TIMEOUT)  # noqa: S310 - constant https URLs
    host = urlparse(response.url).hostname
    if host not in ALLOWED_HOSTS:
        response.close()
        raise RuntimeError(f"unexpected host after redirect: {host}")
    return response


def find_hash(checksums: str, name: str) -> str:
    """Return the SHA-256 published for `name`.

    sha256sum files have it on the line that mentions the name; Deno publishes
    PowerShell Get-FileHash output, where the only hash sits on its own line.
    """
    pattern = r"\b[0-9a-fA-F]{64}\b"
    for line in checksums.splitlines():
        if name in line and (match := re.search(pattern, line)):
            return match.group().lower()
    hashes = re.findall(pattern, checksums)
    if name in checksums and len(hashes) == 1:
        return str(hashes[0]).lower()
    raise RuntimeError(f"no SHA-256 for {name} in the checksum file")


def download(url: str, target: Path) -> str:
    digest = hashlib.sha256()
    with open_url(url) as response, target.open("wb") as out:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    return digest.hexdigest()


def fetch(dest: Path, url: str, checksum_url: str, members: dict[str, str]) -> None:
    name = url.rsplit("/", 1)[1]
    if all((dest / target).exists() for target in members.values()):
        print(f"skip  {name} (already in {dest})")
        return
    with open_url(checksum_url) as response:
        expected = find_hash(response.read().decode("utf-8-sig", "replace"), name)
    tmp = dest / (name + ".download")
    try:
        print(f"fetch {name}", flush=True)
        actual = download(url, tmp)
        if actual != expected:
            raise RuntimeError(
                f"{name}: SHA-256 mismatch\n  expected {expected}\n  actual   {actual}"
            )
        print(f"  sha256 ok {actual}")
        if "" in members:
            tmp.replace(dest / members[""])
            return
        with zipfile.ZipFile(tmp) as archive:
            for member, target in members.items():
                (dest / target).write_bytes(archive.read(member))
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=DEST)
    parser.add_argument("--no-ffprobe", action="store_true")
    options = parser.parse_args()
    dest: Path = options.dest
    assert find_hash(f"{'a' * 64}  other\n{'B' * 64} *x.exe\n", "x.exe") == "b" * 64
    assert find_hash(f"Hash : {'C' * 64}\r\nPath : C:\\a\\x.zip\r\n", "x.zip") == "c" * 64
    dest.mkdir(parents=True, exist_ok=True)
    for url, checksum_url, members in ASSETS:
        if options.no_ffprobe:
            members = {k: v for k, v in members.items() if k != FFPROBE}
        fetch(dest, url, checksum_url, members)
    for exe in sorted(dest.glob("*.exe")):
        print(f"{exe.stat().st_size:>12,}  {exe.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
