"""Produce a safe static audit of D3 code reuse for Step 5N.

No imported research runner is executed.  Source files are read as text, hashed, and
parsed with ``ast`` only.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Audit Step 5N runner reuse statically")
    value.add_argument("--root", type=Path, default=Path.cwd())
    value.add_argument(
        "--config",
        type=Path,
        default=Path(
            "configs/natural_language_localization/step5n_runner_reuse_audit_v1.json"
        ),
    )
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def validated_existing_result(path: Path, *, config_sha256: str) -> JsonObject | None:
    if not path.exists():
        return None
    existing = load_object(path)
    identity = existing.get("result_identity_sha256")
    body = dict(existing)
    body.pop("result_identity_sha256", None)
    if (
        existing.get("schema_version")
        != "jbspan-step5n-runner-reuse-audit-result-v1"
        or existing.get("config_sha256") != config_sha256
        or not isinstance(identity, str)
        or canonical_sha256(body) != identity
    ):
        raise RuntimeError("existing Step 5N runner-reuse audit identity is invalid")
    return existing


def top_level_functions(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def audit_source(root: Path, specification: Mapping[str, Any]) -> JsonObject:
    path = resolve(root, str(specification["path"]))
    exists = path.is_file()
    source = path.read_text(encoding="utf-8") if exists else ""
    observed_hash = file_sha256(path) if exists else None
    functions = top_level_functions(source) if exists else set()
    missing_functions = sorted(set(specification["required_functions"]) - functions)
    missing_fragments = [
        fragment
        for fragment in specification["required_fragments"]
        if fragment not in source
    ]
    checks = {
        "exists": exists,
        "sha256_matches": observed_hash == specification["sha256"],
        "required_functions_present": not missing_functions,
        "required_fragments_present": not missing_fragments,
    }
    return {
        "path": display(root, path),
        "expected_sha256": specification["sha256"],
        "observed_sha256": observed_hash,
        "missing_functions": missing_functions,
        "missing_fragment_count": len(missing_fragments),
        "checks": checks,
        "passed": all(checks.values()),
    }


def validate_contract_boundary(config: Mapping[str, Any]) -> JsonObject:
    boundary = config["authorization_boundary"]
    invariants = config["required_invariants"]
    classification = config["reuse_classification"]
    checks = {
        "contract_is_frozen_static_audit": config.get("frozen") is True
        and config.get("status") == "FROZEN_STATIC_CODE_REUSE_AUDIT",
        "frozen_d3_modification_forbidden": boundary["may_modify_frozen_d3_files"]
        is False,
        "model_download_forbidden": boundary["may_download_models"] is False,
        "inference_forbidden": boundary["may_run_target_or_evaluator_inference"]
        is False,
        "output_opening_forbidden": boundary["may_open_confirmatory_output"] is False,
        "target_identity_required": invariants[
            "target_id_present_in_every_scientific_record_identity"
        ]
        is True,
        "target_scoped_paths_required": invariants["target_scoped_phase_paths"] is True,
        "cross_target_response_sharing_forbidden": invariants[
            "direct_response_shared_across_target_models"
        ]
        is False,
        "same_target_empty_reuse_only": invariants[
            "empty_baseline_reused_only_within_same_target_payload_seed"
        ]
        is True,
        "all_c1n_pairs_flow_to_c2n": invariants["all_eligible_c1n_pairs_enter_c2n"]
        is True,
        "topology_cap_forbidden": invariants["no_topology_outcome_cap"] is True,
        "reuse_layers_declared": all(classification[key] for key in classification),
        "new_layers_declared": len(config["required_new_versioned_layers_after_authorization"])
        >= 6,
    }
    return checks


def run(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = resolve(root, config_path)
    config = load_object(config_path)
    config_sha256 = file_sha256(config_path)
    output_path = resolve(root, config["recording"]["output_path"])
    if not output_path.is_relative_to(root):
        raise ValueError("runner-reuse audit output escapes repository root")
    existing = validated_existing_result(output_path, config_sha256=config_sha256)
    source_audits = {
        name: audit_source(root, specification)
        for name, specification in config["sources"].items()
    }
    boundary_checks = validate_contract_boundary(config)

    support_specification = config["gemma_static_support_dependency"]
    support_path = resolve(root, support_specification["path"])
    support_exists = support_path.is_file()
    support_hash = file_sha256(support_path) if support_exists else None
    support = load_object(support_path) if support_exists else {}
    support_checks = {
        "support_receipt_exists": support_exists,
        "support_receipt_hash_matches": support_hash == support_specification["sha256"],
        "support_receipt_status_matches": support.get("status")
        == support_specification["required_status"],
        "runtime_static_support_passed": support.get("runtime_static_support", {}).get(
            "passed"
        )
        is support_specification["required_runtime_static_support_pass"],
        "gemma_actual_qualification_not_claimed": support.get(
            "runtime_static_support", {}
        ).get("checks", {}).get("actual_gemma_load_not_misrepresented")
        is True,
        "support_opened_no_scientific_output": support.get(
            "confirmatory_target_output_opened"
        )
        is False
        and support.get("confirmatory_evaluator_output_opened") is False
        and support.get("confirmatory_topology_opened") is False,
    }
    passed = (
        all(item["passed"] for item in source_audits.values())
        and all(boundary_checks.values())
        and all(support_checks.values())
    )
    conclusion = config["expected_conclusion"] if passed else "STATIC_REUSE_AUDIT_FAIL"
    result: JsonObject = {
        "schema_version": "jbspan-step5n-runner-reuse-audit-result-v1",
        "status": (
            "STEP5N_RUNNER_REUSE_STATIC_AUDIT_PASS"
            if passed
            else "STEP5N_RUNNER_REUSE_STATIC_AUDIT_FAIL"
        ),
        "captured_at": (
            existing["captured_at"]
            if existing is not None
            else datetime.now().astimezone().isoformat(timespec="seconds")
        ),
        "config_sha256": config_sha256,
        "source_audits": source_audits,
        "boundary_checks": boundary_checks,
        "gemma_static_support": {
            "path": display(root, support_path),
            "expected_sha256": support_specification["sha256"],
            "observed_sha256": support_hash,
            "checks": support_checks,
            "passed": all(support_checks.values()),
            "interpretation": "STATIC_SUPPORT_ONLY_ACTUAL_HARMLESS_ADMISSION_STILL_REQUIRED",
        },
        "reuse_classification": config["reuse_classification"],
        "reasons_drop_in_reuse_is_invalid": config[
            "reasons_drop_in_reuse_is_invalid"
        ],
        "required_new_versioned_layers_after_authorization": config[
            "required_new_versioned_layers_after_authorization"
        ],
        "required_invariants": config["required_invariants"],
        "conclusion": conclusion,
        "audit_pass": passed,
        "model_download_performed": False,
        "target_or_evaluator_inference_performed": False,
        "confirmatory_output_opened": False,
        "frozen_d3_file_modified": False,
        "raw_prompt_payload_or_response_recorded": False,
        "paper_validity": False,
        "next_operation": (
            "AFTER_EXPLICIT_AUTHOR_DECISION_CREATE_NEW_TARGET_SCOPED_RUNNERS_"
            "WITHOUT_MODIFYING_D3_EVIDENCE"
        ),
    }
    result["result_identity_sha256"] = canonical_sha256(result)
    if existing is not None:
        if existing != result:
            raise RuntimeError(
                "refusing to overwrite a nonidentical Step 5N runner-reuse audit result"
            )
    else:
        write_json_atomic(output_path, result)
    return result


def main() -> int:
    arguments = parser().parse_args()
    result = run(arguments.root, arguments.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "conclusion": result["conclusion"],
                "result_identity_sha256": result["result_identity_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["audit_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
