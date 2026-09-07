from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jbspan.evaluator_output_integrity import output_limit_integrity_summary
from jbspan.gate1.util import canonical_json_sha256

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--amendment",
        type=Path,
        default=Path("configs/evaluator_panel/e0g4_output_limit_integrity_amendment_v1_1.json"),
    )
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value: object = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def required_mapping(value: object, *, where: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"expected object at {where}")
    return value


def safe_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def verify_implementation(root: Path, amendment: Mapping[str, Any]) -> None:
    implementation = required_mapping(amendment["implementation"], where="implementation")
    for name in ("parent_contract", "parent_runner", "integrity_module", "finalizer"):
        item = required_mapping(implementation[name], where=f"implementation.{name}")
        path = root / str(item["path"])
        if file_sha256(path) != str(item["sha256"]):
            raise ValueError(f"implementation identity mismatch: {name}")


def ensure_parent_result(root: Path, amendment: Mapping[str, Any]) -> tuple[Path, JsonObject]:
    implementation = required_mapping(amendment["implementation"], where="implementation")
    parent_runner = root / str(
        required_mapping(implementation["parent_runner"], where="parent_runner")["path"]
    )
    parent_result_path = root / str(
        required_mapping(amendment["recording"], where="recording")["parent_result_path"]
    )
    if not parent_result_path.exists():
        subprocess.run(
            [sys.executable, str(parent_runner), "finalize", "--root", str(root)],
            cwd=root,
            check=True,
        )
    return parent_result_path, load_object(parent_result_path)


def build_authoritative_result(root: Path, amendment_path: Path) -> JsonObject:
    amendment = load_object(amendment_path)
    if amendment.get("status") != "FROZEN_BEFORE_FULL_AXIS_OUTCOME":
        raise ValueError("integrity amendment is not frozen")
    verify_implementation(root, amendment)
    recording = required_mapping(amendment["recording"], where="recording")
    authoritative_path = root / str(recording["authoritative_result_path"])
    amendment_sha = file_sha256(amendment_path)
    if authoritative_path.exists():
        existing = load_object(authoritative_path)
        if existing.get("integrity_amendment_sha256") != amendment_sha:
            raise ValueError("existing authoritative result belongs to another amendment")
        return existing

    parent_result_path, parent_result = ensure_parent_result(root, amendment)
    implementation = required_mapping(amendment["implementation"], where="implementation")
    parent_contract = required_mapping(implementation["parent_contract"], where="parent_contract")
    if parent_result.get("contract_sha256") != str(parent_contract["sha256"]):
        raise ValueError("parent result contract identity mismatch")

    parent_config = load_object(root / str(parent_contract["path"]))
    parent_recording = required_mapping(parent_config["recording"], where="parent recording")
    expected_records = int(
        required_mapping(parent_config["development_pool"], where="development_pool")["records"]
    )
    qwen_rows = load_jsonl(root / str(parent_recording["qwen_axis_path"]))
    jailmeter_rows = load_jsonl(root / str(parent_recording["jailmeter_axis_path"]))
    if len(qwen_rows) != expected_records or len(jailmeter_rows) != expected_records:
        raise ValueError("both parent axes must be complete")

    rule = required_mapping(amendment["effective_limit_stop_rule"], where="limit rule")
    qwen_integrity = output_limit_integrity_summary(
        qwen_rows, maximum_output_tokens=int(rule["qwen_maximum_output_tokens"])
    )
    jailmeter_integrity = output_limit_integrity_summary(
        jailmeter_rows, maximum_output_tokens=int(rule["jailmeter_maximum_output_tokens"])
    )
    if int(qwen_integrity["missing_output_token_count"]) != 0:
        raise ValueError("Qwen axis has missing output-token metadata")
    if int(jailmeter_integrity["missing_output_token_count"]) != 0:
        raise ValueError("JailMeter axis has missing output-token metadata")

    observation = required_mapping(
        amendment["preoutcome_observation"], where="preoutcome_observation"
    )
    observed_ids_value = observation["derived_only_record_ids_at_freeze"]
    if not isinstance(observed_ids_value, list) or not all(
        isinstance(value, str) for value in observed_ids_value
    ):
        raise ValueError("preoutcome observed record IDs must be a string list")
    observed_ids = set(observed_ids_value)
    final_derived_ids = set(str(value) for value in jailmeter_integrity["derived_only_record_ids"])
    if not observed_ids.issubset(final_derived_ids):
        raise ValueError("preoutcome output-limit observation is not reproduced by final axis")
    if observation.get("panel_metrics_computed_before_freeze") is not False:
        raise ValueError("amendment must be frozen before panel metrics are computed")
    if observation.get("raw_text_inspected") is not False:
        raise ValueError("amendment must remain metadata-only")

    gate_thresholds = required_mapping(parent_config["qualification_gate"], where="gate")
    checks = dict(required_mapping(parent_result["gate"], where="parent gate")["checks"])
    checks["qwen_output_limit_stops"] = float(qwen_integrity["effective_fraction"]) <= float(
        gate_thresholds["output_limit_stop_fraction_max"]
    )
    checks["jailmeter_output_limit_stops"] = float(
        jailmeter_integrity["effective_fraction"]
    ) <= float(gate_thresholds["output_limit_stop_fraction_max"])
    passed = all(bool(value) for value in checks.values())

    overlay: JsonObject = {
        "schema_version": "jbspan-e0g4-output-limit-integrity-overlay-v1",
        "status": "E0G4_OUTPUT_LIMIT_INTEGRITY_OVERLAY_COMPLETE",
        "integrity_amendment_sha256": amendment_sha,
        "parent_contract_sha256": str(parent_contract["sha256"]),
        "parent_result_path": parent_result_path.relative_to(root).as_posix(),
        "parent_result_sha256": file_sha256(parent_result_path),
        "parent_result_identity_sha256": parent_result["result_identity_sha256"],
        "axis_file_sha256s": {
            "qwen3guard": file_sha256(root / str(parent_recording["qwen_axis_path"])),
            "jailmeter": file_sha256(root / str(parent_recording["jailmeter_axis_path"])),
        },
        "qwen3guard": qwen_integrity,
        "jailmeter": jailmeter_integrity,
        "scientific_rule_changed": False,
        "threshold_changed": False,
        "model_rerun": False,
        "raw_text_read": False,
    }
    overlay["overlay_identity_sha256"] = canonical_json_sha256(overlay)
    overlay_path = root / str(recording["integrity_overlay_path"])
    safe_write(overlay_path, overlay)

    result = copy.deepcopy(parent_result)
    result.pop("result_identity_sha256", None)
    result["schema_version"] = "jbspan-e0g4-full-development-result-v1.1-integrity-amended"
    result["status"] = (
        "E0G4_FULL_DEVELOPMENT_QUALIFICATION_PASS"
        if passed
        else "E0G4_FULL_DEVELOPMENT_QUALIFICATION_FAIL"
    )
    result["contract_sha256"] = amendment_sha
    result["parent_contract_sha256"] = str(parent_contract["sha256"])
    result["parent_result_sha256"] = file_sha256(parent_result_path)
    result["parent_result_identity_sha256"] = parent_result["result_identity_sha256"]
    result["integrity_amendment_sha256"] = amendment_sha
    result["integrity_overlay_path"] = overlay_path.relative_to(root).as_posix()
    result["integrity_overlay_sha256"] = file_sha256(overlay_path)
    result["integrity_overlay_identity_sha256"] = overlay["overlay_identity_sha256"]
    result["effective_output_limit_stops"] = {
        "qwen3guard": qwen_integrity,
        "jailmeter": jailmeter_integrity,
    }
    result["gate"] = {"checks": checks, "passes_all": passed}
    result["interpretation"] = (
        gate_thresholds["interpretation_on_pass"]
        if passed
        else gate_thresholds["interpretation_on_fail"]
    )
    result["panel_qualified_for_heldout_candidate"] = passed
    result["next_operation"] = (
        parent_config["next_operation_on_pass"]
        if passed
        else parent_config["next_operation_on_fail"]
    )
    result["parent_v1_result_authoritative"] = False
    result["authoritative_result"] = True
    result["integrity_repair_scope"] = (
        "metadata-only conservative output-limit derivation; no model rerun, label recovery, "
        "panel-rule change, threshold change, or raw-text inspection"
    )
    result["result_identity_sha256"] = canonical_json_sha256(result)
    safe_write(authoritative_path, result)
    return result


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    amendment_path = (root / args.amendment).resolve()
    result = build_authoritative_result(root, amendment_path)
    print(
        json.dumps(
            {
                "status": result["status"],
                "identity": result["result_identity_sha256"],
                "authoritative_result": result["authoritative_result"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
