"""The two copies of the contract that code holds agree: what the bridge sends (backend) and
what frontend/src/types.ts and frontend/src/api/index.ts expect. Changing one side only
makes this fail (stage 4a, item 12).

Field names and whether each may be absent are compared. Types are not: a number is a number
on both sides, and the JSON itself is checked field by field in test_bridge_*.py.
"""

import re
from dataclasses import fields
from pathlib import Path

import pytest
from test_bridge_events import EVENTS

from app.bridge import shapes
from app.bridge.api import BridgeApi
from app.domain.history import HistoryEntry
from app.domain.media import FormatOption, MediaInfo, PlaylistEntry, PlaylistInfo
from app.domain.progress import Progress
from app.domain.settings import Settings
from app.services.queue import QueueItem
from app.services.updates import (
    AboutInfo,
    AppUpdateInfo,
    AppUpdateStatus,
    Component,
    EngineUpdateResult,
)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
TYPES = (FRONTEND / "types.ts").read_text(encoding="utf-8")
API = (FRONTEND / "api" / "index.ts").read_text(encoding="utf-8")

Fields = dict[str, bool]  # name -> may be absent


def interface(source: str, name: str) -> str:
    found = re.search(rf"^export interface {name} \{{\n(.*?)^\}}", source, re.M | re.S)
    assert found, f"interface {name} not found"
    return found.group(1)


def ts_fields(name: str) -> Fields:
    body = interface(TYPES, name)
    return {m[1]: m[2] == "?" for m in re.finditer(r"^  (\w+)(\??):", body, re.M)}


def py_fields(cls: type) -> Fields:
    # A field that can be None is left out when it is (contract 1.2).
    return {shapes.camel(f.name): "None" in str(f.type) for f in fields(cls)}


def queue_item_fields() -> Fields:
    flat = py_fields(QueueItem)
    del flat["progress"]  # flattened onto the item, every one of them may be absent
    flat.update({name: True for name in py_fields(Progress)})
    flat["skipped"] = True  # only sent when true
    return flat


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("FormatOption", lambda: py_fields(FormatOption)),
        ("MediaInfo", lambda: py_fields(MediaInfo)),
        ("PlaylistEntry", lambda: py_fields(PlaylistEntry)),
        ("PlaylistInfo", lambda: py_fields(PlaylistInfo)),
        ("QueueItem", queue_item_fields),
        ("TaskProgress", lambda: {"id": False, **py_fields(Progress)}),
        ("HistoryEntry", lambda: py_fields(HistoryEntry)),
        ("Settings", lambda: py_fields(Settings)),
        ("AppUpdateInfo", lambda: py_fields(AppUpdateInfo)),
        ("AppUpdateStatus", lambda: py_fields(AppUpdateStatus)),
        ("EngineUpdateResult", lambda: py_fields(EngineUpdateResult)),
        ("Component", lambda: py_fields(Component)),
        ("AboutInfo", lambda: py_fields(AboutInfo)),
        ("OpenResult", lambda: {"opened": False}),
    ],
)
def test_field_names_match(name: str, expected: object) -> None:
    assert callable(expected)
    assert ts_fields(name) == expected()


def test_event_types_match() -> None:
    sent = {shapes.event(event)["type"] for event, _ in EVENTS}
    union = TYPES.split("export type BackendEvent =")[1]
    expected = set(re.findall(r"\{ type: '(\w+)'", union))
    assert sent == expected


def test_command_names_match() -> None:
    names = set(re.findall(r"^  (\w+)\(", interface(API, "Commands"), re.M))
    commands = {name for name in dir(BridgeApi) if not name.startswith("_")}
    assert names == commands


def test_the_receiver_name_matches() -> None:
    from app.bridge.events import RECEIVER

    assert f"{RECEIVER}?:" in (FRONTEND / "api" / "bridge.ts").read_text(encoding="utf-8")


def test_quality_choices_match() -> None:
    from app.domain.media import QUALITIES, Format

    for name, fmt in (("MP3_BITRATES", Format.MP3), ("MP4_HEIGHTS", Format.MP4)):
        found = re.search(rf"export const {name} = \[([\d, ]+)\]", TYPES)
        assert found, f"{name} not found"
        assert sorted(int(n) for n in found.group(1).split(",")) == sorted(QUALITIES[fmt])


def test_the_check_itself_reads_the_files() -> None:
    assert len(ts_fields("QueueItem")) == 16  # or every comparison above proves nothing
