"""Apply the frozen D3 panel namespace bridge and finalize one phase.

The frozen D3 runner addresses ``panel_decision`` through its imported base
execution module, which does not re-export that already frozen function.  This
launcher binds the exact canonical function into that namespace immediately
before finalization.  It changes no target/evaluator record, label rule,
threshold, denominator, adaptive rule, or scientific gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jbspan.fresh_screen_funnel import panel_decision as frozen_panel_decision

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_d3_exact_topology as d3  # noqa: E402
from resume_d3_generation_operational_v1 import retrying_atomic_write  # noqa: E402

JsonObject = dict[str, Any]
JsonRows = Sequence[Mapping[str, Any]]
DEFAULT_CONFIG = Path(
    "configs/natural_language_localization/d3_exact_topology_v1.json"
)
DEFAULT_AMENDMENT = Path(
    "configs/natural_language_localization/d3_panel_bridge_v1_1_amendment.json"
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, default=ROOT)
    value.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    value.add_argument("--amendment", type=Path, default=DEFAULT_AMENDMENT)
    value.add_argument("--seed", type=int, choices=d3.SEEDS, required=True)
    return value


def resolved_under(root: Path, path: Path, *, where: str) -> Path:
    value = path if path.is_absolute() else root / path
    value = value.resolve()
    if not value.is_relative_to(root):
        raise ValueError(f"{where} escapes repository root")
    return value


def load_amendment(root: Path, amendment_path: Path) -> JsonObject:
    amendment_path = resolved_under(root, amendment_path, where="amendment")
    amendment = d3.engine.load_object(amendment_path)
    if (
        amendment.get("schema_version")
        != "jbspan-d3-panel-bridge-amendment-v1-1"
        or amendment.get("status")
        != "FROZEN_AFTER_SEED_11_EVALUATOR_AXES_BEFORE_ANY_D3_PANEL_OUTPUT"
        or amendment.get("frozen") is not True
        or amendment.get("scientific_rule_changed") is not False
    ):
        raise ValueError("D3 panel bridge amendment is not frozen at this boundary")
    dependencies = d3.engine.required_mapping(
        amendment.get("dependencies"), where="dependencies"
    )
    for name, raw_spec in dependencies.items():
        spec = d3.engine.required_mapping(raw_spec, where=f"dependencies.{name}")
        target = resolved_under(root, Path(str(spec["path"])), where=str(name))
        if d3.engine.file_sha256(target) != spec["sha256"]:
            raise ValueError(f"D3 panel bridge dependency mismatch: {name}")
    return amendment


def install_operational_patches() -> dict[str, int]:
    d3.install_engine_patches()
    d3.engine.panel_decision = frozen_panel_decision
    state = {"replace_retries": 0}

    def safe_write(path: Path, value: Mapping[str, Any]) -> None:
        payload = (
            json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        attempts = retrying_atomic_write(path, payload)
        state["replace_retries"] += attempts - 1

    def safe_write_jsonl(path: Path, rows: JsonRows) -> None:
        attempts = retrying_atomic_write(path, d3.engine.encode_jsonl(rows))
        state["replace_retries"] += attempts - 1

    d3.engine.safe_write = safe_write
    d3.engine.safe_write_jsonl = safe_write_jsonl
    return state


def phase_audit_path(root: Path, config: Mapping[str, Any], seed: int) -> Path:
    return d3.engine.output_directory(root, config) / (
        f"phase_{seed}_panel_bridge_v1_1.safe.json"
    )


def validate_phase_inputs(
    phase: Mapping[str, Path], *, expected_count: int
) -> JsonObject:
    keys = ("plan", "generation", "qwen_axis", "jailmeter_axis")
    rows_by_key: dict[str, list[JsonObject]] = {}
    for key in keys:
        path = phase[key]
        if not path.is_file():
            raise ValueError(f"D3 phase input is missing before panel bridge: {key}")
        rows = d3.engine.load_jsonl(path)
        if len(rows) != expected_count:
            raise ValueError(f"D3 phase input count differs before bridge: {key}")
        rows_by_key[key] = rows
    plans = rows_by_key["plan"]
    plan_ids = [str(row["record_id"]) for row in plans]
    if len(set(plan_ids)) != expected_count:
        raise ValueError("D3 phase plan IDs are not unique before panel bridge")
    for key in keys[1:]:
        rows = rows_by_key[key]
        if [str(row["record_id"]) for row in rows] != plan_ids:
            raise ValueError(f"D3 {key} order differs from the phase plan")
        if any(int(row["execution_order"]) != index for index, row in enumerate(rows)):
            raise ValueError(f"D3 {key} execution order differs before bridge")
    return {
        key: {
            "path": phase[key].relative_to(phase["plan"].parents[3]).as_posix(),
            "record_count": len(rows_by_key[key]),
            "sha256": d3.engine.file_sha256(phase[key]),
        }
        for key in keys
    }


def ensure_bridge_audit(
    root: Path,
    config: Mapping[str, Any],
    amendment_path: Path,
    amendment: Mapping[str, Any],
    seed: int,
) -> JsonObject:
    phase = d3.engine.phase_paths(root, config, seed)
    audit_path = phase_audit_path(root, config, seed)
    amendment_sha = d3.engine.file_sha256(amendment_path)
    if audit_path.is_file():
        existing = d3.engine.load_object(audit_path)
        if (
            existing.get("status") != "D3_PANEL_NAMESPACE_BRIDGE_APPLIED"
            or existing.get("phase_seed") != seed
            or existing.get("amendment_sha256") != amendment_sha
        ):
            raise ValueError("existing D3 panel bridge audit is invalid")
        return existing
    if phase["decisions"].exists() or phase["result"].exists():
        raise ValueError("D3 panel output existed before the bridge audit")
    plans = d3.engine.load_jsonl(phase["plan"])
    artifacts = validate_phase_inputs(phase, expected_count=len(plans))
    if seed == d3.SEEDS[0]:
        snapshot = d3.engine.required_mapping(
            amendment.get("pre_panel_snapshot"), where="pre_panel_snapshot"
        )
        for key in ("plan", "generation", "qwen_axis", "jailmeter_axis"):
            expected = d3.engine.required_mapping(snapshot[key], where=f"snapshot.{key}")
            observed = artifacts[key]
            if (
                observed["record_count"] != expected["record_count"]
                or observed["sha256"] != expected["sha256"]
            ):
                raise ValueError(f"D3 seed-11 pre-panel snapshot mismatch: {key}")
    result: JsonObject = {
        "schema_version": "jbspan-d3-panel-bridge-audit-v1-1",
        "status": "D3_PANEL_NAMESPACE_BRIDGE_APPLIED",
        "phase_seed": seed,
        "amendment_sha256": amendment_sha,
        "artifacts": artifacts,
        "bridge": "IMPORT_FROZEN_JBSPAN_FRESH_SCREEN_FUNNEL_PANEL_DECISION",
        "scientific_decision_rule_changed": False,
        "model_inference_performed": False,
        "panel_output_observed_before_bridge": False,
        "raw_response_content_observed": False,
        "raw_text_written": False,
    }
    result["result_identity_sha256"] = d3.engine.canonical_sha256(result)
    d3.engine.safe_write(audit_path, result)
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    state = install_operational_patches()
    amendment_path = resolved_under(root, args.amendment, where="amendment")
    amendment = load_amendment(root, amendment_path)
    config_path = resolved_under(root, args.config, where="config")
    config_path, config, _verified = d3.load_config(root, config_path)
    audit = ensure_bridge_audit(
        root, config, amendment_path, amendment, int(args.seed)
    )
    result = d3.finalize_phase(root, config_path, int(args.seed))
    visible = {
        "status": "D3_PHASE_OPERATIONALLY_FINALIZED",
        "phase_seed": args.seed,
        "panel_counts": result.get("panel_counts"),
        "measurement_eligible_count": result.get("measurement_eligible_count"),
        "new_harmful_short_circuit_witness_count": result.get(
            "new_harmful_short_circuit_witness_count"
        ),
        "next_operation": result.get("next_operation"),
        "bridge_audit_identity_sha256": audit.get("result_identity_sha256"),
        "replace_retries": state["replace_retries"],
        "scientific_rule_changed": False,
    }
    print(json.dumps(visible, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
