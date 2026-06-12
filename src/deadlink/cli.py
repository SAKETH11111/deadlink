from __future__ import annotations

import argparse
import sys
from pathlib import Path

from deadlink.contracts import load_mission_contract
from deadlink.core.contract import ContractValidationError, canonical_contract_hash
from deadlink.drivers.runner import run_mission
from deadlink.recorder.jsonl import JsonlWriter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deadlink")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a mission contract")
    validate_parser.add_argument("mission")

    run_parser = subparsers.add_parser("run", help="Run a deterministic mission")
    run_parser.add_argument("mission")
    run_parser.add_argument("--max-ticks", type=int, required=True)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--run-id")

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args.mission)
    if args.command == "run":
        return _run(args.mission, max_ticks=args.max_ticks, out=args.out, run_id=args.run_id)

    parser.error(f"unsupported command: {args.command}")
    return 2


def _validate(path: str) -> int:
    try:
        contract = load_mission_contract(path)
    except (ContractValidationError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        " ".join(
            [
                f"mission_id={contract.mission_id}",
                f"agents={len(contract.agents)}",
                f"zones={len(contract.zones)}",
                f"assignments={len(contract.initial_assignments)}",
                f"seed={contract.seed}",
                f"contract_hash={canonical_contract_hash(contract)}",
            ]
        )
    )
    return 0


def _run(path: str, *, max_ticks: int, out: str, run_id: str | None) -> int:
    if max_ticks < 1:
        print("invalid max_ticks: must be >= 1", file=sys.stderr)
        return 1

    try:
        contract = load_mission_contract(path)
    except (ContractValidationError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out_path = Path(out)
    tmp_path = out_path.with_name(f".{out_path.name}.tmp")
    try:
        if tmp_path.exists():
            tmp_path.unlink()
        with JsonlWriter(tmp_path) as writer:
            result = run_mission(
                contract,
                max_ticks=max_ticks,
                run_id=run_id or contract.mission_id,
                sink=writer.append,
            )
        tmp_path.replace(out_path)
    except (OSError, ValueError) as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        print(str(exc), file=sys.stderr)
        return 1

    zones_complete = sum(1 for zone in result.final_state.zones.values() if zone.status == "complete")
    print(
        " ".join(
            [
                f"events={len(result.events)}",
                f"final_tick={result.final_tick}",
                f"zones_complete={zones_complete}/{len(result.final_state.zones)}",
                f"log_path={out_path}",
            ]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
