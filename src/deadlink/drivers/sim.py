from __future__ import annotations

from typing import NamedTuple

from deadlink.core.contract import Point
from deadlink.core.coverage import cell_center, cell_order
from deadlink.core.state import MissionState


class TelemetryInput(NamedTuple):
    agent_id: str
    position: Point
    battery_pct: float
    task_id: str
    zone_id: str
    authority_epoch: int


def telemetry_inputs(state: MissionState, *, tick: int) -> tuple[TelemetryInput, ...]:
    inputs: list[TelemetryInput] = []
    for agent_id in sorted(state.agents):
        agent = state.agents[agent_id]
        if agent.current_task_id is None or agent.current_zone_id is None:
            continue
        if agent.link_status == "lost":
            continue

        zone = state.zones[agent.current_zone_id]
        target_cell = _next_target_cell(state, agent_id)
        target = cell_center(zone, target_cell) if target_cell is not None else agent.position
        position = _advance(agent.position, target, step=zone.cell_size)
        inputs.append(
            TelemetryInput(
                agent_id=agent_id,
                position=position,
                battery_pct=max(0.0, 100.0 - tick),
                task_id=agent.current_task_id,
                zone_id=agent.current_zone_id,
                authority_epoch=agent.authority_epoch,
            )
        )
    return tuple(inputs)


def _next_target_cell(state: MissionState, agent_id: str) -> str | None:
    agent = state.agents[agent_id]
    if agent.current_zone_id is None:
        return None
    zone = state.zones[agent.current_zone_id]
    for cell_id in cell_order(zone):
        if cell_id not in zone.visited_cells:
            return cell_id
    return None


def _advance(current: Point, target: Point, *, step: float) -> Point:
    dx = target.x - current.x
    dy = target.y - current.y
    distance_squared = dx * dx + dy * dy
    if distance_squared <= step * step:
        return target

    distance = distance_squared**0.5
    scale = step / distance
    return Point(x=current.x + dx * scale, y=current.y + dy * scale)
