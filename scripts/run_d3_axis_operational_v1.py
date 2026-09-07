"""Run one frozen D3 evaluator axis with resilient safe-artifact persistence.

The imported scientific runner, evaluator inputs, model, prompts, parsing,
denominator, and time gates remain byte-for-byte unchanged.  This launcher only
replaces safe JSON/JSONL persistence in memory so transient Windows destination
locks are retried without losing completed evaluator records.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_d3_exact_topology as d3  # noqa: E402
from resume_d3_generation_operational_v1 import retrying_atomic_write  # noqa: E402

JsonRows = Sequence[Mapping[str, Any]]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("axis", choices=("qwen", "jailmeter"))
    value.add_argument("--root", type=Path, default=ROOT)
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/natural_language_localization/d3_exact_topology_v1.json"),
    )
    value.add_argument("--seed", type=int, choices=d3.SEEDS, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    config_path = args.config if args.config.is_absolute() else root / args.config
    d3.install_engine_patches()
    d3.d3_screen.patch_extractor(root)
    config_path, config, _verified = d3.load_config(root, config_path)
    phase = d3.engine.phase_paths(root, config, args.seed)
    plans = d3.engine.load_jsonl(phase["plan"])
    if not phase["generation"].is_file():
        raise RuntimeError("the frozen target-generation artifact must be complete first")

    progress_key = f"{args.axis}_progress"
    data_key = f"{args.axis}_axis"
    progress_path = phase[progress_key]
    data_path = phase[data_key]
    before_path = data_path if data_path.is_file() else progress_path
    records_before = (
        len(d3.engine.load_jsonl(before_path)) if before_path.is_file() else 0
    )
    replace_retries = 0

    def safe_write(path: Path, value: Mapping[str, Any]) -> None:
        nonlocal replace_retries
        payload = (
            json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        attempts = retrying_atomic_write(path, payload)
        replace_retries += attempts - 1

    def safe_write_jsonl(path: Path, rows: JsonRows) -> None:
        nonlocal replace_retries
        attempts = retrying_atomic_write(path, d3.engine.encode_jsonl(rows))
        replace_retries += attempts - 1

    d3.engine.safe_write = safe_write
    d3.engine.safe_write_jsonl = safe_write_jsonl
    operation = (
        d3.engine.run_qwen if args.axis == "qwen" else d3.engine.run_jailmeter
    )
    result = operation(root, config_path, args.seed)
    if not data_path.is_file():
        raise RuntimeError(f"{args.axis} returned without a finalized data artifact")
    rows = d3.engine.load_jsonl(data_path)
    visible = {
        "status": "D3_EVALUATOR_AXIS_OPERATIONALLY_COMPLETE",
        "axis": args.axis,
        "phase_seed": args.seed,
        "records_before": records_before,
        "records_after": len(rows),
        "new_records_committed": len(rows) - records_before,
        "expected_records": len(plans),
        "parse_count": result.get("parse_count"),
        "output_limit_stops": result.get("output_limit_stops"),
        "replace_retries": replace_retries,
        "data_sha256": d3.engine.file_sha256(data_path),
        "runner_result_status": result.get("status"),
        "model_output_opened_by_launcher": False,
    }
    print(json.dumps(visible, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
