from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.natural_language_calibration import (
    generate_calibration_responses,
    package_blinded_calibration_packet,
    prepare_calibration_inputs,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--root", type=Path, default=Path("."))
    prepare.add_argument("--contract", type=Path, required=True)
    prepare.add_argument("--plan", type=Path, required=True)
    prepare.add_argument("--payload-source-csv", type=Path, required=True)
    prepare.add_argument("--attack-source-csv", type=Path, required=True)
    prepare.add_argument("--private-output-dir", type=Path, required=True)
    prepare.add_argument("--safe-output-dir", type=Path, required=True)

    target = commands.add_parser("target")
    target.add_argument("--contract", type=Path, required=True)
    target.add_argument("--private-output-dir", type=Path, required=True)
    target.add_argument("--server-url", required=True)

    package = commands.add_parser("package")
    package.add_argument("--contract", type=Path, required=True)
    package.add_argument("--plan", type=Path, required=True)
    package.add_argument("--private-output-dir", type=Path, required=True)
    package.add_argument("--safe-output-dir", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "prepare":
        root = args.root.resolve()
        result = prepare_calibration_inputs(
            root,
            contract_path=(root / args.contract).resolve(),
            plan_path=(root / args.plan).resolve(),
            payload_source_csv=args.payload_source_csv.resolve(),
            attack_source_csv=args.attack_source_csv.resolve(),
            private_output_dir=args.private_output_dir.resolve(),
            safe_output_dir=args.safe_output_dir.resolve(),
        )
    elif args.command == "target":
        result = generate_calibration_responses(
            contract_path=args.contract.resolve(),
            private_output_dir=args.private_output_dir.resolve(),
            server_url=args.server_url,
        )
    elif args.command == "package":
        result = package_blinded_calibration_packet(
            contract_path=args.contract.resolve(),
            plan_path=args.plan.resolve(),
            private_output_dir=args.private_output_dir.resolve(),
            safe_output_dir=args.safe_output_dir.resolve(),
        )
    else:
        raise RuntimeError("unsupported command")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
