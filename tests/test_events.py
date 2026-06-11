from __future__ import annotations

from pathlib import Path

import pytest

from deadlink.contracts import load_mission_contract
from deadlink.core.contract import canonical_contract_hash
from deadlink.core.events import (
    INITIAL_EVENT_TYPES,
    EventBuilder,
    EventValidationError,
    create_mission_created,
    validate_event_type,
)


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_initial_event_registry_is_closed_for_story_1_1() -> None:
    assert INITIAL_EVENT_TYPES == (
        "mission.created",
        "mission.started",
        "agent.registered",
        "agent.telemetry.updated",
        "task.assigned",
        "task.progress.updated",
        "link.health.updated",
        "command.kill.requested",
        "deadlink.detected",
        "authority.revoked",
        "task.unfinished.marked",
        "task.reassigned",
        "mission.completed",
        "mission.aborted",
    )

    with pytest.raises(EventValidationError, match="unregistered event type"):
        validate_event_type("coverage.resumed")


def test_mission_created_is_seq_zero_tick_zero_and_self_contained() -> None:
    contract = load_mission_contract(MISSION)

    builder = EventBuilder(run_id="run-001", mission_id=contract.mission_id)

    event = create_mission_created(builder=builder, contract=contract)

    assert event.seq == 0
    assert event.tick == 0
    assert event.run_id == "run-001"
    assert event.mission_id == "indoor_search_001"
    assert event.event_type == "mission.created"
    assert event.source == "driver"
    assert event.payload["seed"] == 424242
    assert event.payload["contract_hash"] == canonical_contract_hash(contract)


def test_event_builder_assigns_gapless_monotonic_sequences_from_mission_created() -> None:
    contract = load_mission_contract(MISSION)
    builder = EventBuilder(run_id="run-001", mission_id=contract.mission_id)

    created = builder.mission_created(contract=contract)
    first = builder.emit(
        event_type="mission.started",
        tick=0,
        source="driver",
        payload={},
    )
    second = builder.emit(
        event_type="agent.registered",
        tick=0,
        source="driver",
        agent_id="scout-1",
        payload={"display_name": "Scout-1"},
    )

    assert [created.seq, first.seq, second.seq] == [0, 1, 2]
    assert [created.tick, first.tick, second.tick] == [0, 0, 0]


def test_event_builder_rejects_negative_ticks() -> None:
    builder = EventBuilder(run_id="run-001", mission_id="indoor_search_001")

    with pytest.raises(EventValidationError, match="negative tick"):
        builder.emit(
            event_type="mission.started",
            tick=-1,
            source="driver",
            payload={},
        )
