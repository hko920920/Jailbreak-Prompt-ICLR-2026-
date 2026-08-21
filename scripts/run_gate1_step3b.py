from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.gate1.step3b import freeze_step3b_source


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--root", type=Path, default=Path("."))
    freeze.add_argument("--source-csv", type=Path, required=True)
    freeze.add_argument("--safe-output-dir", type=Path, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "freeze":
        result = freeze_step3b_source(
            args.root.resolve(),
            source_csv=args.source_csv.resolve(),
            safe_output_dir=args.safe_output_dir.resolve(),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
