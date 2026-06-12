from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_same_inputs_produce_byte_identical_logs(tmp_path: Path) -> None:
    first_log = tmp_path / "first.jsonl"
    second_log = tmp_path / "second.jsonl"

    for log_path in (first_log, second_log):
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
                "fixed-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr

    assert first_log.read_bytes() == second_log.read_bytes()
    assert bytes(str(first_log), "utf-8") not in first_log.read_bytes()
    assert bytes(str(second_log), "utf-8") not in second_log.read_bytes()
