from __future__ import annotations

from typing import Any

import msgspec

from deadlink.core.contract import MissionContract, canonical_contract_hash


INITIAL_EVENT_TYPES = (
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


class EventValidationError(ValueError):
    """Raised when an event violates the closed Story 1.1 event registry."""


class MissionEvent(msgspec.Struct, forbid_unknown_fields=True):
    seq: int
    tick: int
    run_id: str
    mission_id: str
    event_type: str
    source: str
    payload: dict[str, Any]
    agent_id: str | None = None
    task_id: str | None = None
    zone_id: str | None = None
    authority_epoch: int | None = None
    causal_event_id: str | None = None


class EventBuilder:
    def __init__(self, *, run_id: str, mission_id: str) -> None:
        self._run_id = run_id
        self._mission_id = mission_id
        self._next_seq = 0

    def mission_created(self, *, contract: MissionContract) -> MissionEvent:
        if contract.mission_id != self._mission_id:
            raise EventValidationError(
                f"contract mission id {contract.mission_id} does not match builder mission id {self._mission_id}"
            )
        return self.emit(
            event_type="mission.created",
            tick=0,
            source="driver",
            payload={
                "seed": contract.seed,
                "contract_hash": canonical_contract_hash(contract),
            },
        )

    def emit(
        self,
        *,
        event_type: str,
        tick: int,
        source: str,
        payload: dict[str, Any],
        agent_id: str | None = None,
        task_id: str | None = None,
        zone_id: str | None = None,
        authority_epoch: int | None = None,
        causal_event_id: str | None = None,
    ) -> MissionEvent:
        validate_event_type(event_type)
        if tick < 0:
            raise EventValidationError(f"invalid negative tick: {tick}")
        event = MissionEvent(
            seq=self._next_seq,
            tick=tick,
            run_id=self._run_id,
            mission_id=self._mission_id,
            event_type=event_type,
            source=source,
            payload=payload,
            agent_id=agent_id,
            task_id=task_id,
            zone_id=zone_id,
            authority_epoch=authority_epoch,
            causal_event_id=causal_event_id,
        )
        self._next_seq += 1
        return event


def create_mission_created(*, builder: EventBuilder, contract: MissionContract) -> MissionEvent:
    return builder.mission_created(contract=contract)


def validate_event_type(event_type: str) -> None:
    if event_type not in INITIAL_EVENT_TYPES:
        raise EventValidationError(f"unregistered event type: {event_type}")


def event_reference(event: MissionEvent) -> str:
    return f"{event.run_id}:{event.seq}"
