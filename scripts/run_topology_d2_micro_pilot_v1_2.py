from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from jbspan.fresh_screen_funnel import panel_decision as frozen_panel_decision

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import run_topology_d2_micro_pilot_v1_1 as extraction  # noqa: E402

runner = extraction.runner
JsonObject = dict[str, Any]
AMENDMENT_RELATIVE_PATH = Path(
    "configs/natural_language_localization/topology_d2_panel_bridge_v1_2_amendment.json"
)


def validate_panel_amendment(root: Path) -> JsonObject:
    amendment_path = root / AMENDMENT_RELATIVE_PATH
    amendment = runner.load_object(amendment_path)
    if (
        amendment.get("schema_version")
        != "jbspan-topology-d2-panel-bridge-amendment-v1-2"
        or amendment.get("status")
        != "FROZEN_AFTER_BOTH_EVALUATOR_AXES_BEFORE_ANY_D2_PANEL_OUTPUT"
        or amendment.get("frozen") is not True
    ):
        raise ValueError("D2 panel bridge amendment is not frozen at the supported boundary")
    for key, spec_value in amendment["dependencies"].items():
        spec = runner.required_mapping(spec_value, where=f"dependencies.{key}")
        target = root / str(spec["path"])
        if runner.file_sha256(target) != spec["sha256"]:
            raise ValueError(f"D2 panel bridge dependency mismatch: {key}")
    return amendment


def ensure_bridge_audit(root: Path, amendment: JsonObject) -> JsonObject:
    recording = runner.required_mapping(amendment["recording"], where="recording")
    audit_path = root / str(recording["bridge_audit_path"])
    if audit_path.is_file():
        existing = runner.load_object(audit_path)
        if (
            existing.get("status") != "D2_PANEL_BRIDGE_APPLIED"
            or existing.get("amendment_sha256")
            != runner.file_sha256(root / AMENDMENT_RELATIVE_PATH)
        ):
            raise ValueError("existing D2 panel bridge audit is invalid")
        return existing

    snapshot = runner.required_mapping(
        amendment["pre_panel_snapshot"], where="pre_panel_snapshot"
    )
    for key in ("generation", "qwen_axis", "jailmeter_axis"):
        spec = runner.required_mapping(snapshot[key], where=f"pre_panel_snapshot.{key}")
        target = root / str(spec["path"])
        if (
            runner.file_sha256(target) != spec["sha256"]
            or len(runner.load_jsonl(target)) != int(spec["record_count"])
        ):
            raise ValueError(f"D2 pre-panel snapshot mismatch: {key}")

    config_path = root / str(amendment["base_contract_path"])
    config = runner.load_object(config_path)
    output = runner.paths(root, config)
    if output["panel"].exists() or output["panel_summary"].exists():
        raise ValueError("D2 panel output existed before the bridge audit was frozen")

    result: JsonObject = {
        "schema_version": "jbspan-topology-d2-panel-bridge-audit-v1-2",
        "status": "D2_PANEL_BRIDGE_APPLIED",
        "amendment_sha256": runner.file_sha256(root / AMENDMENT_RELATIVE_PATH),
        "bridge": "IMPORT_FROZEN_PANEL_DECISION_FROM_JBSPAN_FRESH_SCREEN_FUNNEL",
        "scientific_decision_rule_changed": False,
        "model_inference_performed": False,
        "panel_output_observed_before_bridge": False,
        "raw_response_content_observed": False,
        "raw_text_written_to_safe_artifact": False,
    }
    result["result_identity_sha256"] = runner.canonical_sha256(result)
    runner.screen.safe_write(audit_path, result)
    return result


def patch_panel_bridge() -> None:
    runner.screen.panel_decision = frozen_panel_decision


def main() -> int:
    root = Path(".").resolve()
    config_path = (
        root
        / "configs/natural_language_localization/topology_d2_micro_pilot_v1.json"
    )
    extraction.validate_amendment(root)
    p3 = extraction.patch_extractor(root)
    extraction.repair_existing_failed_records(root, config_path, p3)
    amendment = validate_panel_amendment(root)
    ensure_bridge_audit(root, amendment)
    patch_panel_bridge()
    return runner.main()


if __name__ == "__main__":
    raise SystemExit(main())
