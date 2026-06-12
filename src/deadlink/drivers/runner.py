from __future__ import annotations

from collections.abc import Callable

import msgspec

from deadlink.core.contract import MissionContract
from deadlink.core.events import EventBuilder, MissionEvent, event_reference
from deadlink.core.state import MissionState, all_zones_complete, initial_state, progress_delta, reduce
from deadlink.drivers.sim import telemetry_inputs


class RunResult(msgspec.Struct, forbid_unknown_fields=True):
    events: tuple[MissionEvent, ...]
    final_state: MissionState
    final_tick: int


EventSink = Callable[[MissionEvent], None]


def run_mission(
    contract: MissionContract,
    *,
    max_ticks: int,
    run_id: str | None = None,
    sink: EventSink | None = None,
) -> RunResult:
    if max_ticks < 1:
        raise ValueError("invalid max_ticks: must be >= 1")

    actual_run_id = run_id or contract.mission_id
    builder = EventBuilder(run_id=actual_run_id, mission_id=contract.mission_id)
    events: list[MissionEvent] = []
    state = initial_state(contract)
    final_tick = 0

    def record(event: MissionEvent) -> tuple[MissionState, MissionState]:
        nonlocal state
        before = state
        if sink is not None:
            sink(event)
        events.append(event)
        state = reduce(state, event)
        return before, state

    created = builder.mission_created(contract=contract)
    record(created)

    started = builder.emit(
        event_type="mission.started",
        tick=0,
        source="driver",
        payload={"tick_rate_hz": contract.tick_rate_hz},
        causal_event_id=event_reference(created),
    )
    record(started)

    for agent in sorted(contract.agents, key=lambda item: item.id):
        registered = builder.emit(
            event_type="agent.registered",
            tick=0,
            source="driver",
            agent_id=agent.id,
            payload={
                "display_name": agent.display_name,
                "start": msgspec.to_builtins(agent.start),
            },
            causal_event_id=event_reference(started),
        )
        record(registered)
        link_health = builder.emit(
            event_type="link.health.updated",
            tick=0,
            source="core",
            agent_id=agent.id,
            payload={"status": "healthy"},
            causal_event_id=event_reference(registered),
        )
        record(link_health)

    tasks_by_id = {task.id: task for task in contract.tasks}
    for assignment in sorted(contract.initial_assignments, key=lambda item: item.agent_id):
        task = tasks_by_id[assignment.task_id]
        assigned = builder.emit(
            event_type="task.assigned",
            tick=0,
            source="core",
            agent_id=assignment.agent_id,
            task_id=assignment.task_id,
            zone_id=task.zone_id,
            authority_epoch=0,
            payload={"status": "assigned"},
            causal_event_id=event_reference(started),
        )
        record(assigned)

    for tick in range(1, max_ticks + 1):
        final_tick = tick
        deltas = []
        for telemetry in telemetry_inputs(state, tick=tick):
            telemetry_event = builder.emit(
                event_type="agent.telemetry.updated",
                tick=tick,
                source="driver",
                agent_id=telemetry.agent_id,
                task_id=telemetry.task_id,
                zone_id=telemetry.zone_id,
                authority_epoch=telemetry.authority_epoch,
                payload={
                    "position": msgspec.to_builtins(telemetry.position),
                    "current_task_id": telemetry.task_id,
                    "current_zone_id": telemetry.zone_id,
                    "battery_pct": telemetry.battery_pct,
                },
            )
            before, after = record(telemetry_event)
            delta = progress_delta(before, after, telemetry.agent_id)
            if delta is not None:
                deltas.append((delta, telemetry_event))

        for delta, telemetry_event in deltas:
            progress = builder.emit(
                event_type="task.progress.updated",
                tick=tick,
                source="core",
                agent_id=delta.agent_id,
                task_id=delta.task_id,
                zone_id=delta.zone_id,
                authority_epoch=delta.authority_epoch,
                payload={
                    "visited_cell_id": delta.visited_cell_id,
                    "visited_count": delta.visited_count,
                    "total_cells": delta.total_cells,
                },
                causal_event_id=event_reference(telemetry_event),
            )
            record(progress)

        if all_zones_complete(state):
            completed = builder.emit(
                event_type="mission.completed",
                tick=tick,
                source="core",
                payload={
                    "zones_complete": len(state.zones),
                    "tasks_complete": len(state.tasks),
                },
                causal_event_id=event_reference(events[-1]),
            )
            record(completed)
            break

    return RunResult(events=tuple(events), final_state=state, final_tick=final_tick)
