from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import deadlink.core.state as state_module
import deadlink.recorder.jsonl as jsonl_module
from deadlink.contracts import load_mission_contract
from deadlink.core.state import initial_state, reduce
from deadlink.recorder.jsonl import read_jsonl


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_reducer_fold_reconstructs_progress_without_driver_imports(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "deadlink",
            "run",
            str(MISSION),
            "--max-ticks",
            "10",
            "--out",
            str(log_path),
            "--run-id",
            "fold-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    contract = load_mission_contract(MISSION)
    state = initial_state(contract)
    for event in read_jsonl(log_path):
        state = reduce(state, event)

    assert "deadlink.drivers" not in Path(state_module.__file__).read_text()
    assert "deadlink.drivers" not in Path(jsonl_module.__file__).read_text()
    assert state.mission_status == "complete"
    assert {zone_id: zone.status for zone_id, zone in state.zones.items()} == {
        "zone-a": "complete",
        "zone-b": "complete",
        "zone-c": "complete",
    }
    assert {task_id: task.visited_count for task_id, task in state.tasks.items()} == {
        "task-zone-a": 3,
        "task-zone-b": 3,
        "task-zone-c": 3,
    }
