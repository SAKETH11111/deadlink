from __future__ import annotations

from pathlib import Path

from deadlink.contracts import load_mission_contract
from deadlink.drivers.runner import run_mission
from deadlink.recorder.jsonl import write_jsonl


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_same_inputs_produce_byte_identical_logs(tmp_path: Path) -> None:
    contract = load_mission_contract(MISSION)

    first = run_mission(contract, max_ticks=10, run_id="fixed-run")
    second = run_mission(contract, max_ticks=10, run_id="fixed-run")
    first_log = tmp_path / "first.jsonl"
    second_log = tmp_path / "second.jsonl"
    write_jsonl(first_log, first.events)
    write_jsonl(second_log, second.events)

    assert first.final_state == second.final_state
    assert first_log.read_bytes() == second_log.read_bytes()
    assert bytes(str(first_log), "utf-8") not in first_log.read_bytes()
    assert bytes(str(second_log), "utf-8") not in second_log.read_bytes()
