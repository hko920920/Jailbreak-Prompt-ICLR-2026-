from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import types
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]


def load_object(path: Path) -> JsonObject:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(JsonObject, value)


def load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise TypeError(f"expected JSONL object: {path}")
        rows.append(cast(JsonObject, value))
    return rows


def as_object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    framed = f"blob {len(payload)}\0".encode() + payload
    return hashlib.sha1(framed).hexdigest()  # noqa: S324 - Git identity.


def git_tree_sha(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD^{tree}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def load_v3_helper(root: Path) -> types.ModuleType:
    path = root / "scripts/run_evaluator_panel_e1c_prompt_source_freeze_v3.py"
    spec = importlib.util.spec_from_file_location("e1c_prompt_source_v3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def binary_metrics(labels: list[int], predictions: list[int]) -> JsonObject:
    if len(labels) != len(predictions) or not labels:
        raise ValueError("labels and predictions must be non-empty and aligned")
    if any(value not in (0, 1) for value in labels + predictions):
        raise ValueError("metrics require binary values")
    tp = sum(int(y == 1 and p == 1) for y, p in zip(labels, predictions, strict=True))
    tn = sum(int(y == 0 and p == 0) for y, p in zip(labels, predictions, strict=True))
    fp = sum(int(y == 0 and p == 1) for y, p in zip(labels, predictions, strict=True))
    fn = sum(int(y == 1 and p == 0) for y, p in zip(labels, predictions, strict=True))

    def safe_div(num: float, den: float) -> float:
        return num / den if den else 0.0

    accuracy = safe_div(tp + tn, len(labels))
    tpr = safe_div(tp, tp + fn)
    tnr = safe_div(tn, tn + fp)
    fpr = safe_div(fp, fp + tn)
    fnr = safe_div(fn, fn + tp)
    precision_pos = safe_div(tp, tp + fp)
    recall_pos = tpr
    f1_pos = safe_div(2 * precision_pos * recall_pos, precision_pos + recall_pos)
    precision_neg = safe_div(tn, tn + fn)
    recall_neg = tnr
    f1_neg = safe_div(2 * precision_neg * recall_neg, precision_neg + recall_neg)
    return {
        "count": len(labels),
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "accuracy": accuracy,
        "balanced_accuracy": (tpr + tnr) / 2,
        "macro_f1": (f1_pos + f1_neg) / 2,
        "false_positive_rate": fpr,
        "false_negative_rate": fnr,
    }


def derive_thresholds(reference: JsonObject, formula: JsonObject) -> JsonObject:
    macro_floor = float(formula["macro_f1_absolute_floor"])
    macro_margin = float(formula["macro_f1_noninferiority_margin"])
    bal_floor = float(formula["balanced_accuracy_absolute_floor"])
    bal_margin = float(formula["balanced_accuracy_noninferiority_margin"])
    fnr_ceiling = float(formula["false_negative_rate_absolute_ceiling"])
    fnr_margin = float(formula["false_negative_rate_noninferiority_margin"])
    fpr_ceiling = float(formula["false_positive_rate_absolute_ceiling"])
    fpr_margin = float(formula["false_positive_rate_noninferiority_margin"])
    return {
        "parse_coverage_min": float(formula["parse_coverage_min"]),
        "macro_f1_min": max(macro_floor, float(reference["macro_f1"]) - macro_margin),
        "balanced_accuracy_min": max(
            bal_floor,
            float(reference["balanced_accuracy"]) - bal_margin,
        ),
        "false_negative_rate_max": min(
            fnr_ceiling,
            float(reference["false_negative_rate"]) + fnr_margin,
        ),
        "false_positive_rate_max": min(
            fpr_ceiling,
            float(reference["false_positive_rate"]) + fpr_margin,
        ),
        "repeatability_subset_count": int(formula["repeatability_subset_count"]),
        "repeatability_mismatch_max": int(formula["repeatability_mismatch_max"]),
    }


def validation_rows_by_record_id(
    validation: JsonObject,
    helper: types.ModuleType,
    cached_field: str,
) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for behavior_id, raw_rows in sorted(validation.items()):
        if not isinstance(behavior_id, str) or not isinstance(raw_rows, list):
            raise TypeError("validation must map behavior IDs to arrays")
        for raw in raw_rows:
            if not isinstance(raw, dict):
                raise TypeError("validation rows must be objects")
            row = cast(JsonObject, raw)
            record_id = str(helper.private_record_id(behavior_id, row))
            label, unanimous = helper.human_label(row)
            cached = row.get(cached_field)
            if isinstance(cached, bool) or not isinstance(cached, int) or cached not in (0, 1):
                raise ValueError("selected validation row lacks binary cached prediction")
            if record_id in result:
                raise ValueError("duplicate canonical record ID")
            result[record_id] = {
                "record_id": record_id,
                "behavior_hash": helper.sha256_text(behavior_id),
                "label": int(label),
                "human_unanimous": bool(unanimous),
                "cached_prediction": cached,
            }
    return result


def verify_source(source_root: Path, source: JsonObject) -> tuple[list[JsonObject], bool]:
    files = as_object(source["files"], where="harmbench_source.files")
    rows: list[JsonObject] = []
    passed = True
    for relative, expected_blob in sorted(files.items()):
        path = source_root / relative
        exists = path.is_file()
        observed = git_blob_sha(path) if exists else None
        matches = observed == expected_blob
        passed = passed and matches
        rows.append(
            {
                "path": relative,
                "exists": exists,
                "expected_git_blob_sha": expected_blob,
                "observed_git_blob_sha": observed,
                "git_blob_match": matches,
                "sha256": sha256_file(path) if exists else None,
                "size_bytes": path.stat().st_size if exists else None,
            }
        )
    return rows, passed


def run(root: Path, source_root: Path, config_path: Path, safe_output: Path) -> JsonObject:
    contract = load_object(config_path)
    if contract.get("status") != (
        "FROZEN_BEFORE_E1C_HARMBENCH_LIVE_CONTRACT_MATERIALIZATION"
    ):
        raise ValueError("unexpected E1C live-contract status")
    if contract.get("frozen") is not True or contract.get("paper_validity") is not False:
        raise ValueError("live contract must be frozen and non-paper-valid")

    predecessor_contract = as_object(contract["predecessor"], where="predecessor")
    predecessor_path = root / str(predecessor_contract["result_path"])
    predecessor = load_object(predecessor_path)
    manifest_path = root / str(predecessor_contract["manifest_path"])
    manifest = load_jsonl(manifest_path)
    predecessor_checks = {
        "result_file_sha256_matches": (
            sha256_file(predecessor_path)
            == predecessor_contract["required_file_sha256"]
        ),
        "status_matches": predecessor.get("status") == predecessor_contract["required_status"],
        "operational_pass_matches": (
            predecessor.get("operational_pass")
            is predecessor_contract["required_operational_pass"]
        ),
        "next_operation_matches": (
            predecessor.get("next_authorized_operation")
            == predecessor_contract["required_next_operation"]
        ),
        "no_prior_inference": (
            predecessor.get("model_inference_performed")
            is predecessor_contract["required_model_inference"]
        ),
        "manifest_file_sha256_matches": (
            sha256_file(manifest_path)
            == predecessor_contract["required_manifest_file_sha256"]
        ),
        "manifest_record_count_matches": (
            len(manifest) == predecessor_contract["required_record_count"]
        ),
        "manifest_canonical_sha256_matches": (
            canonical_sha256(manifest)
            == predecessor_contract["required_manifest_canonical_sha256"]
        ),
    }

    source = as_object(contract["harmbench_source"], where="harmbench_source")
    source_files, source_files_pass = verify_source(source_root, source)
    observed_tree = git_tree_sha(source_root)

    selection_contract = as_object(contract["selection"], where="selection")
    selection_path = root / str(selection_contract["path"])
    selection = load_jsonl(selection_path)
    selection_checks = {
        "selection_file_sha256_matches": (
            sha256_file(selection_path) == selection_contract["required_file_sha256"]
        ),
        "selection_record_count_matches": (
            len(selection) == selection_contract["record_count"]
        ),
        "selection_record_ids_sha256_matches": (
            canonical_sha256([row.get("record_id") for row in selection])
            == selection_contract["required_record_ids_sha256"]
        ),
        "selection_safe_rows_sha256_matches": (
            canonical_sha256(selection) == selection_contract["required_safe_rows_sha256"]
        ),
    }

    helper = load_v3_helper(root)
    validation_contract = as_object(contract["validation"], where="validation")
    validation = load_object(source_root / str(validation_contract["path"]))
    indexed = validation_rows_by_record_id(
        validation,
        helper,
        str(validation_contract["cached_prediction_field"]),
    )
    labels: list[int] = []
    cached_predictions: list[int] = []
    resolved: list[JsonObject] = []
    for safe_row in selection:
        record_id = safe_row.get("record_id")
        if not isinstance(record_id, str) or record_id not in indexed:
            raise ValueError("selection row does not resolve in validation")
        private = indexed[record_id]
        if safe_row.get("behavior_hash") != private["behavior_hash"]:
            raise ValueError("selection behavior identity mismatch")
        if safe_row.get("label") != private["label"]:
            raise ValueError("selection label mismatch")
        labels.append(int(private["label"]))
        cached_predictions.append(int(private["cached_prediction"]))
        resolved.append(private)

    reference = binary_metrics(labels, cached_predictions)
    formula = as_object(
        contract["reference_and_gate_formula"], where="reference_and_gate_formula"
    )
    thresholds = derive_thresholds(reference, formula)
    repeatability_count = int(thresholds["repeatability_subset_count"])
    repeatability_ids = sorted(
        (str(row["record_id"]) for row in resolved),
        key=lambda value: sha256_bytes(value.encode()),
    )[:repeatability_count]

    modes = as_object(contract["evaluation_modes"], where="evaluation_modes")
    official_mode = as_object(
        modes["raw_official_template"], where="raw_official_template"
    )
    hardened_mode = as_object(
        modes["hardened_production_template"],
        where="hardened_production_template",
    )
    budget = as_object(contract["execution_budget"], where="execution_budget")
    canaries = as_object(contract["injection_canaries"], where="canaries")
    expected_requests = (
        int(budget["full_selection_requests"])
        + int(budget["repeatability_requests"])
        + int(budget["canary_requests"])
    )
    boundary = as_object(contract["claim_boundary"], where="claim_boundary")

    checks = {
        **predecessor_checks,
        "source_tree_matches": observed_tree == source["tree_sha"],
        "source_files_match": source_files_pass,
        **selection_checks,
        "all_selected_rows_resolve": len(resolved) == len(selection),
        "cached_reference_count_matches": reference["count"] == len(selection),
        "repeatability_subset_count_matches": len(repeatability_ids) == repeatability_count,
        "official_mode_count_matches": (
            official_mode["full_selection_count"] == len(selection)
        ),
        "hardened_mode_count_matches": (
            hardened_mode["full_selection_count"] == len(selection)
        ),
        "exactly_one_production_gate_mode": sum(
            int(as_object(value, where="mode")["production_gate"] is True)
            for value in modes.values()
        ) == 1,
        "primary_gate_mode_matches": (
            formula["primary_gate_mode"] == "hardened_production_template"
            and hardened_mode["production_gate"] is True
        ),
        "request_budget_matches": (
            expected_requests == budget["expected_total_classifier_requests"]
            and budget["full_selection_requests"] == 2 * len(selection)
            and budget["repeatability_requests"] == repeatability_count
            and budget["canary_requests"] == 2 * canaries["case_count"]
        ),
        "claim_boundary_preserved": all(
            boundary[key] is expected
            for key, expected in (
                ("harmbench_is_single_primary_judge", False),
                ("e1c_is_panel_external_validity", False),
                ("e1c_is_paper_result", False),
                ("cached_notebook_predictions_are_ground_truth", False),
                ("human_majority_labels_are_primary_reference", True),
            )
        ),
        "no_model_weight_download": True,
        "no_model_inference": True,
        "no_live_predictions": True,
        "no_new_attack_outputs": True,
    }
    passed = all(checks.values())
    gate = as_object(contract["decision_gate"], where="decision_gate")
    result: JsonObject = {
        "schema_version": "evaluator-panel-e1c-harmbench-live-contract-result-v1",
        "status": (
            "E1C_HARMBENCH_LIVE_CONTRACT_FREEZE_PASS"
            if passed
            else "E1C_HARMBENCH_LIVE_CONTRACT_FREEZE_FAIL"
        ),
        "operational_pass": passed,
        "paper_validity": False,
        "evidence_class": "PROTOCOL",
        "contract_sha256": sha256_file(config_path),
        "predecessor": {
            "result_sha256": sha256_file(predecessor_path),
            "manifest_sha256": sha256_file(manifest_path),
            "manifest_record_count": len(manifest),
        },
        "source": {
            "repository": source["repository"],
            "revision": source["revision"],
            "expected_tree_sha": source["tree_sha"],
            "observed_tree_sha": observed_tree,
            "files": source_files,
        },
        "selection": {
            "file_sha256": sha256_file(selection_path),
            "record_count": len(selection),
            "record_ids_sha256": canonical_sha256(
                [row.get("record_id") for row in selection]
            ),
            "raw_records_recorded": False,
        },
        "cached_reference": {
            **reference,
            "role": "NONINFERIORITY_REFERENCE_ONLY",
            "human_majority_is_primary_reference": True,
            "raw_text_recorded": False,
        },
        "frozen_live_thresholds": thresholds,
        "repeatability_subset": {
            "count": len(repeatability_ids),
            "record_ids_sha256": canonical_sha256(repeatability_ids),
            "raw_records_recorded": False,
        },
        "component": contract["component"],
        "published_reference": contract["published_reference"],
        "evaluation_modes": modes,
        "production_hardening": contract["production_hardening"],
        "execution_budget": budget,
        "claim_boundary": boundary,
        "injection_canaries": {
            "nonce_sha256": sha256_bytes(str(canaries["nonce"]).encode()),
            "transformation_count": len(
                cast(list[object], canaries["transformations"])
            ),
            "case_count": canaries["case_count"],
            "raw_canary_text_recorded": False,
        },
        "checks": checks,
        "model_weight_downloaded": False,
        "model_inference_performed": False,
        "harmbench_live_predictions_generated": False,
        "new_harmful_attack_outputs_generated": False,
        "semantic_only_stage_a_opened": False,
        "cross_regime_stage_a_opened": False,
        "prior_evaluation_opened": False,
        "heldout_opened": False,
        "causal_oracle_opened": False,
        "keep_only_oracle_opened": False,
        "wavelet_used": False,
        "next_authorized_operation": (
            "EXECUTE_E1C_HARMBENCH_LIVE_REPRODUCTION_AND_INJECTION_CANARIES"
            if passed
            else gate["on_operational_fail"]
        ),
    }
    safe_output.parent.mkdir(parents=True, exist_ok=True)
    safe_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze E1C HarmBench live contract")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run(
        args.root.resolve(),
        args.source_root.resolve(),
        args.config.resolve(),
        args.safe_output.resolve(),
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "operational_pass": result["operational_pass"],
                "cached_reference": result["cached_reference"],
                "frozen_live_thresholds": result["frozen_live_thresholds"],
                "next_authorized_operation": result["next_authorized_operation"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["operational_pass"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
