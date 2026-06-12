from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from deadlink.contracts import load_mission_contract
from deadlink.core.coverage import cell_center
from deadlink.core.events import EventBuilder
from deadlink.core.state import initial_state, reduce
from deadlink.drivers.runner import run_mission


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_full_canonical_run_completes_all_zones_before_horizon() -> None:
    contract = load_mission_contract(MISSION)

    result = run_mission(contract, max_ticks=10, run_id=contract.mission_id)

    assert result.final_state.mission_status == "complete"
    assert result.final_tick <= 10
    assert {zone_id: zone.status for zone_id, zone in result.final_state.zones.items()} == {
        "zone-a": "complete",
        "zone-b": "complete",
        "zone-c": "complete",
    }
    assert [event.event_type for event in result.events].count("mission.completed") == 1


def test_telemetry_emits_each_tick_for_each_linked_agent_and_battery_decays() -> None:
    contract = load_mission_contract(MISSION)

    result = run_mission(contract, max_ticks=10, run_id=contract.mission_id)
    telemetry = [event for event in result.events if event.event_type == "agent.telemetry.updated"]

    by_tick: dict[int, list[str]] = defaultdict(list)
    by_agent_battery: dict[str, list[float]] = defaultdict(list)
    for event in telemetry:
        by_tick[event.tick].append(event.agent_id or "")
        by_agent_battery[event.agent_id or ""].append(event.payload["battery_pct"])

    assert sorted(by_tick) == list(range(1, result.final_tick + 1))
    for agent_ids in by_tick.values():
        assert agent_ids == ["scout-1", "scout-2", "scout-3"]

    for readings in by_agent_battery.values():
        assert readings == sorted(readings, reverse=True)


def test_initial_task_assignments_are_deterministic_and_self_describing() -> None:
    contract = load_mission_contract(MISSION)

    result = run_mission(contract, max_ticks=10, run_id=contract.mission_id)
    assignments = [event for event in result.events if event.event_type == "task.assigned"]

    assert [
        (event.agent_id, event.zone_id, event.task_id, event.tick, event.authority_epoch)
        for event in assignments
    ] == [
        ("scout-1", "zone-a", "task-zone-a", 0, 0),
        ("scout-2", "zone-b", "task-zone-b", 0, 0),
        ("scout-3", "zone-c", "task-zone-c", 0, 0),
    ]
    assert all(event.causal_event_id for event in assignments)


def test_telemetry_without_authority_epoch_updates_link_but_does_not_progress() -> None:
    contract = load_mission_contract(MISSION)
    state = initial_state(contract)
    zone = contract.zones[0]
    position = cell_center(zone, zone.cells[0])
    event = EventBuilder(run_id="epoch-test", mission_id=contract.mission_id).emit(
        event_type="agent.telemetry.updated",
        tick=1,
        source="driver",
        agent_id="scout-1",
        task_id="task-zone-a",
        zone_id="zone-a",
        payload={
            "position": {"x": position.x, "y": position.y},
            "battery_pct": 99.0,
        },
    )

    reduced = reduce(state, event)

    assert reduced.agents["scout-1"].last_seen_tick == 1
    assert reduced.tasks["task-zone-a"].visited_count == 0
    assert reduced.zones["zone-a"].visited_cells == ()
