"""Run frozen D3 capability controls with resilient safe-artifact persistence.

The imported scientific runner, selected control denominator, prompts, model,
decoding, capability predicate, and final gates remain unchanged. This wrapper
only retries transient Windows destination locks while writing safe artifacts.
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
    value.add_argument("--root", type=Path, default=ROOT)
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/natural_language_localization/d3_exact_topology_v1.json"),
    )
    return value


def run(root: Path, config_path: Path) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    d3.install_engine_patches()
    d3.d3_screen.patch_extractor(root)
    config_path, config, _verified = d3.load_config(root, config_path)
    output = d3.extra_paths(root, config)
    before_path = (
        output["controls"]
        if output["controls"].is_file()
        else output["control_progress"]
    )
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
    result = d3.run_controls(root, config_path)
    if not output["controls"].is_file() or not output["control_summary"].is_file():
        raise RuntimeError("D3 controls returned without finalized artifacts")
    rows = d3.engine.load_jsonl(output["controls"])
    selected = d3.engine.load_jsonl(output["selected_controls"])
    return {
        "status": "D3_CAPABILITY_CONTROLS_OPERATIONALLY_COMPLETE",
        "records_before": records_before,
        "records_after": len(rows),
        "new_records_committed": len(rows) - records_before,
        "selected_control_records": len(selected),
        "provisional_candidate_subsets": result.get(
            "provisional_recovered_subset_count"
        ),
        "capability_pass_count": result.get("capability_pass_count"),
        "capability_fail_count": result.get("capability_fail_count"),
        "replace_retries": replace_retries,
        "data_sha256": d3.engine.file_sha256(output["controls"]),
        "runner_result_status": result.get("status"),
        "model_output_opened_by_launcher": False,
        "scientific_rule_changed": False,
    }


def main() -> int:
    args = parser().parse_args()
    print(json.dumps(run(args.root, args.config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
