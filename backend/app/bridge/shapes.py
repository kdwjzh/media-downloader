"""Turns what the services return into the JSON of docs/介面與後端的約定.md (sections 2-4).

The rules (section 1.2 and the stage 4 hand-over, 3.2): camelCase names; a field without a
value is left out, never null; a queue item's progress is flattened onto the item; skipped
only appears when true; every event carries its type.
"""

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

from app.domain.media import MediaInfo, PlaylistInfo
from app.domain.progress import Progress
from app.services.history import HistoryAdded
from app.services.queue import QueueItem, TaskProgress, TasksChanged, TasksRemoved
from app.services.settings import SettingsChanged

Json = dict[str, object]


@dataclass(frozen=True)
class CloseRequested:
    """The window's close button was pressed while tasks are still running."""


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(word.capitalize() for word in rest)


def to_json(value: object) -> object:
    if isinstance(value, QueueItem):
        return queue_item(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            camel(f.name): to_json(v)
            for f in fields(value)
            if (v := getattr(value, f.name)) is not None
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list | tuple):
        return [to_json(v) for v in value]
    return value


def progress(value: Progress | None) -> Json:
    if value is None:
        return {}
    flat = to_json(value)
    assert isinstance(flat, dict)
    if value.speed_bps is not None:
        flat["speedBps"] = round(value.speed_bps)  # the contract says a number; bytes are whole
    return flat


def queue_item(item: QueueItem) -> Json:
    flat: Json = {}
    for f in fields(item):
        value = getattr(item, f.name)
        if f.name == "progress":
            flat.update(progress(value))
        elif f.name == "skipped":
            if value:
                flat["skipped"] = True
        elif value is not None:
            flat[camel(f.name)] = to_json(value)
    return flat


def lookup(result: MediaInfo | PlaylistInfo) -> Json:
    if isinstance(result, PlaylistInfo):
        return {"kind": "playlist", "playlist": to_json(result)}
    return {"kind": "video", "info": to_json(result)}


Event = TasksChanged | TasksRemoved | TaskProgress | HistoryAdded | SettingsChanged | CloseRequested


def event(value: Event) -> Json:
    match value:
        case TasksChanged():
            return {"type": "tasksChanged", "tasks": to_json(value.tasks)}
        case TasksRemoved():
            return {"type": "tasksRemoved", "ids": list(value.ids)}
        case TaskProgress():
            flat = {"id": value.id, **progress(value.progress)}
            return {"type": "taskProgress", "progress": flat}
        case HistoryAdded():
            return {"type": "historyAdded", "entry": to_json(value.entry)}
        case SettingsChanged():
            return {"type": "settingsChanged", "settings": to_json(value.settings)}
        case CloseRequested():
            return {"type": "closeRequested"}
    raise TypeError(f"not an event: {value!r}")
