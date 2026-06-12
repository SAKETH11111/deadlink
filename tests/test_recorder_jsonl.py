from __future__ import annotations

import json

import pytest

from deadlink.core.events import EventValidationError
from deadlink.recorder.jsonl import read_jsonl


def test_read_jsonl_rejects_unregistered_event_types(tmp_path) -> None:
    log_path = tmp_path / "bad.jsonl"
    log_path.write_text(
        json.dumps(
            {
                "seq": 0,
                "tick": 0,
                "run_id": "run-1",
                "mission_id": "mission-1",
                "event_type": "coverage.resumed",
                "source": "test",
                "payload": {},
            }
        )
        + "\n"
    )

    with pytest.raises(EventValidationError, match="unregistered event type"):
        list(read_jsonl(log_path))
