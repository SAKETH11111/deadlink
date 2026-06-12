from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import msgspec

from deadlink.core.events import MissionEvent, validate_event_type


class JsonlWriter:
    def __init__(self, path: str | Path) -> None:
        self._file = Path(path).open("wb")

    def append(self, event: MissionEvent) -> None:
        self._file.write(msgspec.json.encode(event))
        self._file.write(b"\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> JsonlWriter:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()


def write_jsonl(path: str | Path, events: Iterable[MissionEvent]) -> None:
    with JsonlWriter(path) as writer:
        for event in events:
            writer.append(event)


def read_jsonl(path: str | Path) -> Iterator[MissionEvent]:
    with Path(path).open("rb") as file:
        for line in file:
            if not line.strip():
                continue
            event = msgspec.json.decode(line, type=MissionEvent)
            validate_event_type(event.event_type)
            yield event
