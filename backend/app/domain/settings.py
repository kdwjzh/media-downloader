from collections.abc import Callable, Container, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum

from app.domain.engine import OnDuplicate
from app.domain.media import QUALITIES, Format


class Language(StrEnum):
    SYSTEM = "system"
    ZH_TW = "zh-TW"
    EN = "en"


# Mirrored in frontend/src/types.ts and docs/介面與後端的約定.md section 5.3; change all three.
# 4 and 5 were measured on 2026-11-15 (docs/技術驗證.md item 12).
MAX_CONCURRENT = range(1, 6)


@dataclass(frozen=True)
class Settings:
    """Section 2.10 of the contract. format, mp3_bitrate and mp4_height are both the
    defaults and "what was used last"."""

    download_dir: str
    max_concurrent: int = 3
    on_duplicate: OnDuplicate = OnDuplicate.RENAME
    format: Format = Format.MP3
    mp3_bitrate: int = 320
    mp4_height: int = 1080
    language: Language = Language.SYSTEM


def _one_of(allowed: Container[int]) -> Callable[[object], object]:
    def parse(value: object) -> object:
        if type(value) is not int or value not in allowed:  # type(): True is not a number here
            raise ValueError(f"{value!r} is not allowed")
        return value

    return parse


def _enum(kind: type[StrEnum]) -> Callable[[object], object]:
    def parse(value: object) -> object:
        if not isinstance(value, str):
            raise ValueError(f"{value!r} is not allowed")
        return kind(value)

    return parse


# Every field update_settings may change. download_dir is not one of them: it only changes
# through the folder dialog.
EDITABLE: dict[str, Callable[[object], object]] = {
    "max_concurrent": _one_of(MAX_CONCURRENT),
    "on_duplicate": _enum(OnDuplicate),
    "format": _enum(Format),
    "mp3_bitrate": _one_of(QUALITIES[Format.MP3]),
    "mp4_height": _one_of(QUALITIES[Format.MP4]),
    "language": _enum(Language),
}


def apply(settings: Settings, changes: Mapping[str, object]) -> Settings:
    """The settings with these fields changed. Raises ValueError for a field that is not
    editable or a value out of range; nothing is changed then."""
    parsed = {}
    for name, value in changes.items():
        if name not in EDITABLE:
            raise ValueError(f"{name!r} is not a setting that can be changed")
        parsed[name] = EDITABLE[name](value)
    return replace(settings, **parsed)  # type: ignore[arg-type]
