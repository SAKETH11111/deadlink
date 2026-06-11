from __future__ import annotations

import argparse
import sys

from deadlink.contracts import load_mission_contract
from deadlink.core.contract import ContractValidationError, canonical_contract_hash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="deadlink")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate a mission contract")
    validate_parser.add_argument("mission")

    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args.mission)

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


if __name__ == "__main__":
    raise SystemExit(main())
