from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "deadlink", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_validate_prints_summary_without_running_mission() -> None:
    result = run_cli("validate", "missions/indoor_search_001.json")

    assert result.returncode == 0
    assert "mission_id=indoor_search_001" in result.stdout
    assert "agents=3" in result.stdout
    assert "zones=3" in result.stdout
    assert "assignments=3" in result.stdout
    assert "seed=424242" in result.stdout
    assert "contract_hash=" in result.stdout
    assert "mission.started" not in result.stdout


def test_validate_rejects_invalid_fixture_with_nonzero_exit() -> None:
    result = run_cli("validate", "missions/invalid/duplicate_agent_ids.json")

    assert result.returncode != 0
    assert "duplicate agent id" in result.stderr
