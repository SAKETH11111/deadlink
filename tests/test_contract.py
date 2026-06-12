from __future__ import annotations

import json
from pathlib import Path

import pytest

from deadlink.contracts import load_mission_contract
from deadlink.core.contract import (
    DERIVED_CONTRACT_FIELDS,
    HASHED_CONTRACT_FIELDS,
    ContractValidationError,
    MissionContract,
    canonical_contract_hash,
)


ROOT = Path(__file__).resolve().parents[1]
MISSION = ROOT / "missions" / "indoor_search_001.json"


def test_loads_canonical_mission_with_explicit_state_shapes() -> None:
    contract = load_mission_contract(MISSION)

    assert contract.mission_id == "indoor_search_001"
    assert contract.seed == 424242
    assert [agent.id for agent in contract.agents] == ["scout-1", "scout-2", "scout-3"]
    assert [zone.id for zone in contract.zones] == ["zone-a", "zone-b", "zone-c"]
    assert contract.initial_zone_state["zone-b"].owner_agent_id == "scout-2"
    assert contract.initial_zone_state["zone-b"].status == "assigned"
    assert contract.initial_task_state["task-zone-b"].status == "assigned"
    assert contract.zones[0].origin.x == 0
    assert contract.zones[0].origin.y == 0
    assert contract.zones[0].cell_size == 1.0
    assert contract.zones[0].grid.cols == 3
    assert contract.zones[0].grid.rows == 1


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("duplicate_agent_ids.json", "duplicate agent id"),
        ("unknown_assignment_agent.json", "unknown agent id"),
        ("unknown_assignment_task.json", "unknown task id"),
        ("unknown_task_zone.json", "unknown zone id"),
        ("missing_required_field.json", "missing required field"),
        ("invalid_policy_value.json", "invalid failure_policy.reassignment"),
        ("malformed.json", "malformed JSON"),
        ("grid_cell_mismatch.json", "cells length must match grid"),
        ("invalid_cell_size.json", "invalid zone zone-a cell_size"),
    ],
)
def test_invalid_contracts_fail_with_named_violations(fixture: str, expected: str) -> None:
    path = ROOT / "missions" / "invalid" / fixture

    with pytest.raises(ContractValidationError, match=expected):
        load_mission_contract(path)


def test_contract_hash_uses_canonical_parsed_representation(tmp_path: Path) -> None:
    raw = json.loads(MISSION.read_text())
    reformatted = tmp_path / "same_mission_reformatted.json"
    reformatted.write_text(json.dumps(raw, indent=4, sort_keys=False))

    first = load_mission_contract(MISSION)
    second = load_mission_contract(reformatted)

    assert canonical_contract_hash(first) == canonical_contract_hash(second)


def test_empty_mission_sections_are_rejected(tmp_path: Path) -> None:
    raw = json.loads(MISSION.read_text())
    raw["agents"] = []
    raw["zones"] = []
    raw["tasks"] = []
    raw["initial_assignments"] = []
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps(raw))

    with pytest.raises(ContractValidationError, match="at least one agent"):
        load_mission_contract(empty)


def test_authored_derived_initial_state_is_rejected(tmp_path: Path) -> None:
    raw = json.loads(MISSION.read_text())
    raw["initial_zone_state"] = {}
    with_state = tmp_path / "with_state.json"
    with_state.write_text(json.dumps(raw))

    with pytest.raises(ContractValidationError, match="derived field is not accepted"):
        load_mission_contract(with_state)


def test_hash_field_set_is_pinned() -> None:
    assert HASHED_CONTRACT_FIELDS == (
        "mission_id",
        "schema_version",
        "tick_rate_hz",
        "seed",
        "failure_policy",
        "agents",
        "zones",
        "tasks",
        "initial_assignments",
    )
    assert set(MissionContract.__struct_fields__) == set(HASHED_CONTRACT_FIELDS) | set(DERIVED_CONTRACT_FIELDS)


def test_zone_geometry_participates_in_canonical_hash(tmp_path: Path) -> None:
    raw = json.loads(MISSION.read_text())
    changed = tmp_path / "geometry_changed.json"
    raw["zones"][0]["cell_size"] = 2.0
    changed.write_text(json.dumps(raw))

    assert canonical_contract_hash(load_mission_contract(MISSION)) != canonical_contract_hash(
        load_mission_contract(changed)
    )
