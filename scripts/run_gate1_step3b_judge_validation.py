from __future__ import annotations

import argparse
import json
from pathlib import Path

from jbspan.gate1.jbb_judge_validation import validate_judges, write_report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = validate_judges(
        args.root.resolve(),
        args.source_csv.resolve(),
        args.output_dir.resolve(),
    )
    write_report(result, args.report.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
