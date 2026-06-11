from __future__ import annotations

import hashlib
import json
from typing import Literal

import msgspec


class ContractValidationError(ValueError):
    """Raised when a mission contract is structurally valid JSON but invalid."""


class Point(msgspec.Struct, forbid_unknown_fields=True):
    x: float
    y: float


class AgentSpec(msgspec.Struct, forbid_unknown_fields=True):
    id: str
    display_name: str
    start: Point


class ZoneSpec(msgspec.Struct, forbid_unknown_fields=True):
    id: str
    display_name: str
    cells: list[str]


class TaskSpec(msgspec.Struct, forbid_unknown_fields=True):
    id: str
    zone_id: str


class AssignmentSpec(msgspec.Struct, forbid_unknown_fields=True):
    agent_id: str
    task_id: str


class FailurePolicy(msgspec.Struct, forbid_unknown_fields=True):
    missed_update_threshold_ticks: int
    reassignment: Literal["greedy_nearest"]
    on_unrecoverable: Literal["hold", "abort"]


class ZoneInitialState(msgspec.Struct, forbid_unknown_fields=True):
    zone_id: str
    owner_agent_id: str | None
    status: Literal["unassigned", "assigned", "in_progress", "complete"]
    completed_cells: tuple[str, ...]


class TaskInitialState(msgspec.Struct, forbid_unknown_fields=True):
    task_id: str
    zone_id: str
    owner_agent_id: str | None
    status: Literal["unassigned", "assigned", "queued", "complete", "unfinished"]


class MissionContract(msgspec.Struct, forbid_unknown_fields=True):
    mission_id: str
    schema_version: int
    tick_rate_hz: int
    seed: int
    failure_policy: FailurePolicy
    agents: list[AgentSpec]
    zones: list[ZoneSpec]
    tasks: list[TaskSpec]
    initial_assignments: list[AssignmentSpec]
    initial_zone_state: dict[str, ZoneInitialState] = {}
    initial_task_state: dict[str, TaskInitialState] = {}


def parse_mission_contract_json(raw: bytes) -> MissionContract:
    try:
        contract = msgspec.json.decode(raw, type=MissionContract)
    except msgspec.ValidationError as exc:
        raise ContractValidationError(_normalize_msgspec_error(str(exc))) from exc

    _validate_contract(contract)
    return _with_initial_state(contract)


def canonical_contract_hash(contract: MissionContract) -> str:
    plain = msgspec.to_builtins(
        MissionContract(
            mission_id=contract.mission_id,
            schema_version=contract.schema_version,
            tick_rate_hz=contract.tick_rate_hz,
            seed=contract.seed,
            failure_policy=contract.failure_policy,
            agents=contract.agents,
            zones=contract.zones,
            tasks=contract.tasks,
            initial_assignments=contract.initial_assignments,
        )
    )
    canonical = json.dumps(plain, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _validate_contract(contract: MissionContract) -> None:
    _require(contract.mission_id, "missing required field: mission_id")
    _require(contract.schema_version == 1, "invalid schema_version")
    _require(contract.tick_rate_hz > 0, "invalid tick_rate_hz")
    _require(contract.seed >= 0, "invalid seed")
    _require(
        contract.failure_policy.missed_update_threshold_ticks > 0,
        "invalid failure_policy.missed_update_threshold_ticks",
    )

    agent_ids = _unique_ids((agent.id for agent in contract.agents), "agent")
    zone_ids = _unique_ids((zone.id for zone in contract.zones), "zone")
    task_ids = _unique_ids((task.id for task in contract.tasks), "task")

    for zone in contract.zones:
        _require(zone.cells, f"zone {zone.id} must contain at least one cell")
        _unique_ids(iter(zone.cells), f"cell in zone {zone.id}")

    for task in contract.tasks:
        _require(task.zone_id in zone_ids, f"unknown zone id in task {task.id}: {task.zone_id}")

    for assignment in contract.initial_assignments:
        _require(assignment.agent_id in agent_ids, f"unknown agent id in assignment: {assignment.agent_id}")
        _require(assignment.task_id in task_ids, f"unknown task id in assignment: {assignment.task_id}")

    _unique_ids((assignment.agent_id for assignment in contract.initial_assignments), "assigned agent")
    _unique_ids((assignment.task_id for assignment in contract.initial_assignments), "assigned task")


def _with_initial_state(contract: MissionContract) -> MissionContract:
    tasks_by_id = {task.id: task for task in contract.tasks}
    assignments_by_task = {assignment.task_id: assignment for assignment in contract.initial_assignments}
    assignments_by_zone: dict[str, AssignmentSpec] = {}
    for task_id, assignment in assignments_by_task.items():
        assignments_by_zone[tasks_by_id[task_id].zone_id] = assignment

    zone_state = {
        zone.id: ZoneInitialState(
            zone_id=zone.id,
            owner_agent_id=assignments_by_zone.get(zone.id).agent_id if zone.id in assignments_by_zone else None,
            status="assigned" if zone.id in assignments_by_zone else "unassigned",
            completed_cells=(),
        )
        for zone in contract.zones
    }
    task_state = {
        task.id: TaskInitialState(
            task_id=task.id,
            zone_id=task.zone_id,
            owner_agent_id=assignments_by_task.get(task.id).agent_id if task.id in assignments_by_task else None,
            status="assigned" if task.id in assignments_by_task else "unassigned",
        )
        for task in contract.tasks
    }

    return MissionContract(
        mission_id=contract.mission_id,
        schema_version=contract.schema_version,
        tick_rate_hz=contract.tick_rate_hz,
        seed=contract.seed,
        failure_policy=contract.failure_policy,
        agents=contract.agents,
        zones=contract.zones,
        tasks=contract.tasks,
        initial_assignments=contract.initial_assignments,
        initial_zone_state=zone_state,
        initial_task_state=task_state,
    )


def _unique_ids(values: object, label: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or value == "":
            raise ContractValidationError(f"invalid {label} id")
        if value in seen:
            raise ContractValidationError(f"duplicate {label} id: {value}")
        seen.add(value)
    return seen


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ContractValidationError(message)


def _normalize_msgspec_error(message: str) -> str:
    if "$.failure_policy.reassignment" in message:
        return f"invalid failure_policy.reassignment: {message}"
    if "$.failure_policy.on_unrecoverable" in message:
        return f"invalid failure_policy.on_unrecoverable: {message}"
    if "missing required field" in message.lower() or "object missing required field" in message.lower():
        return f"missing required field: {message}"
    return f"invalid contract schema: {message}"
