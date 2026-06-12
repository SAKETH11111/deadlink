from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from deadlink.recorder.jsonl import read_jsonl


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "deadlink", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_run_command_writes_log_and_prints_summary(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"

    result = run_cli("run", "missions/indoor_search_001.json", "--max-ticks", "10", "--out", str(log_path))

    assert result.returncode == 0, result.stderr
    assert log_path.exists()
    assert "events=" in result.stdout
    assert "final_tick=" in result.stdout
    assert "zones_complete=3/3" in result.stdout
    assert f"log_path={log_path}" in result.stdout
    assert bytes(str(log_path), "utf-8") not in log_path.read_bytes()

    events = list(read_jsonl(log_path))
    assert [event.event_type for event in events[:3]] == [
        "mission.created",
        "mission.started",
        "agent.registered",
    ]


def test_run_rejects_zero_max_ticks_and_leaves_no_log(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"

    result = run_cli("run", "missions/indoor_search_001.json", "--max-ticks", "0", "--out", str(log_path))

    assert result.returncode != 0
    assert "invalid max_ticks" in result.stderr
    assert not log_path.exists()


def test_run_rejects_invalid_contract_and_leaves_no_log(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"

    result = run_cli("run", "missions/invalid/duplicate_agent_ids.json", "--max-ticks", "10", "--out", str(log_path))

    assert result.returncode != 0
    assert "duplicate agent id" in result.stderr
    assert not log_path.exists()
