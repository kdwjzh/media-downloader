"""Pieces of scripts/build_installer.py that run without building anything."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

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


def _dist(site: Path, name: str, requires: list[str], license_text: str | None) -> None:
    info = site / f"{name}-1.0.dist-info"
    info.mkdir(parents=True)
    lines = [f"Name: {name}", "Version: 1.0", *[f"Requires-Dist: {r}" for r in requires]]
    (info / "METADATA").write_text("\n".join(lines) + "\n", encoding="utf-8")
    record = [f"{info.name}/METADATA,,"]
    if license_text is not None:
        (info / "licenses").mkdir()
        (info / "licenses" / "LICENSE").write_text(license_text, encoding="utf-8")
        record.append(f"{info.name}/licenses/LICENSE,,")
    (info / "RECORD").write_text("\n".join(record) + "\n", encoding="utf-8")


def test_the_python_licenses_follow_the_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "pyproject.toml").write_text(
        '[project]\ndependencies = ["Web_View>=1"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(build_installer, "ROOT", tmp_path)
    site = tmp_path / "site"
    _dist(
        site,
        "web-view",
        ["helper", "mac-only; sys_platform == 'darwin'", "docs; extra == 'x'"],
        "web-view text",
    )
    _dist(site, "helper", [], "helper text")
    _dist(site, "docs", [], None)  # installed, but only an extra asks for it
    _dist(site, "unrelated", [], "dev tool text")

    text, missing = build_installer.python_licenses(site, set())

    assert "web-view text" in text and "helper text" in text
    assert "dev tool text" not in text and "docs" not in text
    assert missing == []


def test_a_package_without_a_license_fails_unless_kept_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "pyproject.toml").write_text(
        '[project]\ndependencies = ["bare"]\n', encoding="utf-8"
    )
    monkeypatch.setattr(build_installer, "ROOT", tmp_path)
    _dist(tmp_path / "site", "bare", [], None)

    assert build_installer.python_licenses(tmp_path / "site", set())[1] == ["bare"]
    text, missing = build_installer.python_licenses(tmp_path / "site", {"bare"})
    assert missing == [] and "see its own file" in text


def test_the_installer_ships_the_generated_and_the_kept_licenses() -> None:
    iss = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8-sig")
    assert 'Source: "..\\build\\licenses\\*"; DestDir: "{app}\\licenses"' in iss
    for name in build_installer.SEPARATE_LICENSES.values():
        assert (ROOT / "packaging" / "licenses" / name).is_file()
    vite = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert "third-party-licenses.md" in vite
