from __future__ import annotations

from pathlib import Path

from deadlink.contracts import load_mission_contract
from deadlink.drivers.runner import run_mission


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_nominal_run_emits_no_failure_or_recovery_events() -> None:
    contract = load_mission_contract(MISSION)

    result = run_mission(contract, max_ticks=10, run_id=contract.mission_id)
    event_types = {event.event_type for event in result.events}

    assert event_types.isdisjoint(
        {
            "deadlink.detected",
            "authority.revoked",
            "task.unfinished.marked",
            "task.reassigned",
            "coverage.resumed",
        }
    )


def test_progress_counts_are_monotonic_and_never_exceed_total() -> None:
    contract = load_mission_contract(MISSION)

    result = run_mission(contract, max_ticks=10, run_id=contract.mission_id)
    by_task: dict[str, list[tuple[int, int]]] = {}
    for event in result.events:
        if event.event_type == "task.progress.updated":
            by_task.setdefault(event.task_id or "", []).append(
                (event.payload["visited_count"], event.payload["total_cells"])
            )

    for counts in by_task.values():
        visited = [count for count, _total in counts]
        totals = {total for _count, total in counts}
        assert visited == sorted(visited)
        assert len(totals) == 1
        assert visited[-1] <= next(iter(totals))
