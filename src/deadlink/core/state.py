from __future__ import annotations

from typing import Literal

import msgspec

from deadlink.core.contract import GridSpec, MissionContract, Point
from deadlink.core.coverage import cell_at_position
from deadlink.core.events import MissionEvent


class AgentState(msgspec.Struct, forbid_unknown_fields=True):
    agent_id: str
    display_name: str
    position: Point
    current_task_id: str | None
    current_zone_id: str | None
    authority_epoch: int
    link_status: Literal["unknown", "healthy", "lost"]
    last_seen_tick: int | None
    battery_pct: float | None


class ZoneState(msgspec.Struct, forbid_unknown_fields=True):
    zone_id: str
    display_name: str
    origin: Point
    cell_size: float
    grid: GridSpec
    cells: tuple[str, ...]
    owner_agent_id: str | None
    status: Literal["incomplete", "in_progress", "complete"]
    visited_cells: tuple[str, ...]


class TaskState(msgspec.Struct, forbid_unknown_fields=True):
    task_id: str
    zone_id: str
    owner_agent_id: str | None
    status: Literal["queued", "assigned", "in_progress", "complete", "unfinished"]
    visited_count: int
    total_cells: int


class MissionState(msgspec.Struct, forbid_unknown_fields=True):
    mission_id: str
    mission_status: Literal["initialized", "started", "complete", "aborted"]
    agents: dict[str, AgentState]
    zones: dict[str, ZoneState]
    tasks: dict[str, TaskState]
    completed_tick: int | None = None


class ProgressDelta(msgspec.Struct, forbid_unknown_fields=True):
    agent_id: str
    task_id: str
    zone_id: str
    authority_epoch: int
    visited_cell_id: str
    visited_count: int
    total_cells: int


def initial_state(contract: MissionContract) -> MissionState:
    assignments_by_agent = {assignment.agent_id: assignment for assignment in contract.initial_assignments}
    assignments_by_task = {assignment.task_id: assignment for assignment in contract.initial_assignments}
    zones_by_task = {task.id: task.zone_id for task in contract.tasks}

    agents: dict[str, AgentState] = {}
    for agent in contract.agents:
        assignment = assignments_by_agent.get(agent.id)
        task_id = assignment.task_id if assignment else None
        zone_id = zones_by_task[task_id] if task_id else None
        agents[agent.id] = AgentState(
            agent_id=agent.id,
            display_name=agent.display_name,
            position=agent.start,
            current_task_id=task_id,
            current_zone_id=zone_id,
            authority_epoch=0,
            link_status="unknown",
            last_seen_tick=None,
            battery_pct=None,
        )

    zones: dict[str, ZoneState] = {}
    for zone in contract.zones:
        owner_agent_id = None
        for task in contract.tasks:
            if task.zone_id == zone.id and task.id in assignments_by_task:
                owner_agent_id = assignments_by_task[task.id].agent_id
                break
        zones[zone.id] = ZoneState(
            zone_id=zone.id,
            display_name=zone.display_name,
            origin=zone.origin,
            cell_size=zone.cell_size,
            grid=zone.grid,
            cells=tuple(zone.cells),
            owner_agent_id=owner_agent_id,
            status="incomplete",
            visited_cells=(),
        )

    tasks: dict[str, TaskState] = {}
    for task in contract.tasks:
        owner_agent_id = assignments_by_task.get(task.id).agent_id if task.id in assignments_by_task else None
        zone = zones[task.zone_id]
        tasks[task.id] = TaskState(
            task_id=task.id,
            zone_id=task.zone_id,
            owner_agent_id=owner_agent_id,
            status="assigned" if owner_agent_id else "queued",
            visited_count=0,
            total_cells=len(zone.cells),
        )

    return MissionState(
        mission_id=contract.mission_id,
        mission_status="initialized",
        agents=agents,
        zones=zones,
        tasks=tasks,
    )


def reduce(state: MissionState, event: MissionEvent) -> MissionState:
    if event.event_type == "mission.started":
        return msgspec.structs.replace(state, mission_status="started")
    if event.event_type == "agent.registered":
        return state
    if event.event_type == "link.health.updated" and event.agent_id:
        return _reduce_link_health(state, event)
    if event.event_type == "task.assigned" and event.agent_id and event.task_id and event.zone_id:
        return _reduce_task_assigned(state, event)
    if event.event_type == "agent.telemetry.updated" and event.agent_id:
        return _reduce_telemetry(state, event)
    if event.event_type == "mission.completed":
        return msgspec.structs.replace(state, mission_status="complete", completed_tick=event.tick)
    if event.event_type == "mission.aborted":
        return msgspec.structs.replace(state, mission_status="aborted", completed_tick=event.tick)
    return state


def progress_delta(before: MissionState, after: MissionState, agent_id: str) -> ProgressDelta | None:
    agent = after.agents[agent_id]
    if agent.current_task_id is None or agent.current_zone_id is None:
        return None

    before_zone = before.zones[agent.current_zone_id]
    after_zone = after.zones[agent.current_zone_id]
    if len(after_zone.visited_cells) <= len(before_zone.visited_cells):
        return None

    return ProgressDelta(
        agent_id=agent_id,
        task_id=agent.current_task_id,
        zone_id=agent.current_zone_id,
        authority_epoch=agent.authority_epoch,
        visited_cell_id=after_zone.visited_cells[-1],
        visited_count=len(after_zone.visited_cells),
        total_cells=len(after_zone.cells),
    )


def all_zones_complete(state: MissionState) -> bool:
    return all(zone.status == "complete" for zone in state.zones.values())


def _reduce_link_health(state: MissionState, event: MissionEvent) -> MissionState:
    agent = state.agents[event.agent_id or ""]
    updated = msgspec.structs.replace(
        agent,
        link_status=event.payload.get("status", agent.link_status),
    )
    agents = dict(state.agents)
    agents[agent.agent_id] = updated
    return msgspec.structs.replace(state, agents=agents)


def _reduce_task_assigned(state: MissionState, event: MissionEvent) -> MissionState:
    agent = state.agents[event.agent_id or ""]
    task = state.tasks[event.task_id or ""]
    zone = state.zones[event.zone_id or ""]

    agents = dict(state.agents)
    agents[agent.agent_id] = msgspec.structs.replace(
        agent,
        current_task_id=task.task_id,
        current_zone_id=zone.zone_id,
        authority_epoch=event.authority_epoch if event.authority_epoch is not None else agent.authority_epoch,
    )

    tasks = dict(state.tasks)
    tasks[task.task_id] = msgspec.structs.replace(task, owner_agent_id=agent.agent_id, status="assigned")

    zones = dict(state.zones)
    zones[zone.zone_id] = msgspec.structs.replace(zone, owner_agent_id=agent.agent_id)

    return msgspec.structs.replace(state, agents=agents, zones=zones, tasks=tasks)


def _reduce_telemetry(state: MissionState, event: MissionEvent) -> MissionState:
    agent = state.agents[event.agent_id or ""]
    position_raw = event.payload["position"]
    position = Point(x=float(position_raw["x"]), y=float(position_raw["y"]))
    updated_agent = msgspec.structs.replace(
        agent,
        position=position,
        last_seen_tick=event.tick,
        link_status="healthy",
        battery_pct=float(event.payload["battery_pct"]) if "battery_pct" in event.payload else agent.battery_pct,
    )

    agents = dict(state.agents)
    agents[agent.agent_id] = updated_agent
    next_state = msgspec.structs.replace(state, agents=agents)

    if agent.current_task_id is None or agent.current_zone_id is None:
        return next_state
    if event.authority_epoch is None or event.authority_epoch != agent.authority_epoch:
        return next_state

    zone = next_state.zones[agent.current_zone_id]
    cell_id = cell_at_position(zone, position)
    if cell_id is None or cell_id in zone.visited_cells:
        return next_state

    visited_cells = zone.visited_cells + (cell_id,)
    zone_status = "complete" if len(visited_cells) == len(zone.cells) else "in_progress"
    zones = dict(next_state.zones)
    zones[zone.zone_id] = msgspec.structs.replace(zone, status=zone_status, visited_cells=visited_cells)

    task = next_state.tasks[agent.current_task_id]
    tasks = dict(next_state.tasks)
    tasks[task.task_id] = msgspec.structs.replace(
        task,
        status="complete" if zone_status == "complete" else "in_progress",
        visited_count=len(visited_cells),
    )

    return msgspec.structs.replace(next_state, zones=zones, tasks=tasks)
