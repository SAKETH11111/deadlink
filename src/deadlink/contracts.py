from __future__ import annotations

from pathlib import Path

from deadlink.core.contract import MissionContract, parse_mission_contract_json


def load_mission_contract(path: str | Path) -> MissionContract:
    return parse_mission_contract_json(Path(path).read_bytes())
