from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.gate1.step3b_calibration import (
    evaluate_calibration_harmbench,
    finalize_calibration,
    generate_calibration,
    prepare_calibration,
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--root", type=Path, default=Path("."))
    prepare.add_argument("--payload-source-csv", type=Path, required=True)
    prepare.add_argument("--attack-source-csv", type=Path, required=True)
    prepare.add_argument("--safe-output-dir", type=Path, required=True)
    prepare.add_argument("--private-output-dir", type=Path, required=True)

    target = commands.add_parser("target")
    target.add_argument("--root", type=Path, default=Path("."))
    target.add_argument("--private-output-dir", type=Path, required=True)
    target.add_argument("--server-url", required=True)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--root", type=Path, default=Path("."))
    evaluate.add_argument("--private-output-dir", type=Path, required=True)
    evaluate.add_argument("--server-url", required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--root", type=Path, default=Path("."))
    finalize.add_argument("--private-output-dir", type=Path, required=True)
    finalize.add_argument("--safe-output-dir", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    if args.command == "prepare":
        result = prepare_calibration(
            root,
            payload_source_csv=args.payload_source_csv.resolve(),
            attack_source_csv=args.attack_source_csv.resolve(),
            safe_output_dir=args.safe_output_dir.resolve(),
            private_output_dir=args.private_output_dir.resolve(),
        )
    elif args.command == "target":
        result = generate_calibration(
            root,
            private_output_dir=args.private_output_dir.resolve(),
            server_url=args.server_url,
        )
    elif args.command == "evaluate":
        result = evaluate_calibration_harmbench(
            root,
            private_output_dir=args.private_output_dir.resolve(),
            server_url=args.server_url,
        )
    elif args.command == "finalize":
        result = finalize_calibration(
            root,
            private_output_dir=args.private_output_dir.resolve(),
            safe_output_dir=args.safe_output_dir.resolve(),
        )
    else:
        raise RuntimeError("unsupported command")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
