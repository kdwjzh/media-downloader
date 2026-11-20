"""Pieces of scripts/build_installer.py that run without building anything."""

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "build_installer", ROOT / "scripts" / "build_installer.py"
)
assert _spec and _spec.loader
build_installer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_installer)


def test_the_checksum_file_ends_lines_with_lf(tmp_path: Path) -> None:
    # GNU sha256sum -c before coreutils 9.0 rejects a CRLF line ("no properly formatted lines").
    installer = tmp_path / "MediaDownloader-Setup-1.0.0.exe"
    installer.write_bytes(b"installer")

    digest = build_installer.write_checksum(installer)

    expected = hashlib.sha256(b"installer").hexdigest()
    assert digest == expected
    data = (tmp_path / f"{installer.name}.sha256").read_bytes()
    assert data == f"{expected}  {installer.name}\n".encode()
