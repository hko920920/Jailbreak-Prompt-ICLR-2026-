from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
LOCAL_SOURCE_ROOT = PROJECT_ROOT / "src"
if str(LOCAL_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCAL_SOURCE_ROOT))

from jbspan.evaluator_panel_external_calibration import (  # noqa: E402
    file_sha256,
    source_locator_sha256,
)
from jbspan.evaluator_panel_external_data import (  # noqa: E402
    deduplicate_external_records,
    safe_manifest_record,
)
from jbspan.evaluator_panel_redesign import (  # noqa: E402
    SCORE_FORMULAS,
    ExistingSignalRecord,
    assign_behavior_group_folds,
    atomic_signal_audit,
    best_frontier_summaries,
    build_existing_signal_records,
    candidate_gate,
    candidate_metric_rows,
    canonical_json_bytes,
    canonical_jsonl_bytes,
    cross_validated_precision_frontier,
    enumerate_score_candidates,
    fold_summary,
    leave_one_source_out_frontier,
    pareto_frontier,
    sha256_bytes,
    stage_summary,
    staged_wildguard_assignment,
)

JsonObject = dict[str, Any]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--root", type=Path, default=Path("."))
    value.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluator_panel/calibration_redesign_e0f_v1.json"),
    )
    return value


def _object(value: object, *, where: str) -> JsonObject:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    return cast(JsonObject, value)


def _object_rows(value: object, *, where: str) -> list[JsonObject]:
    if not isinstance(value, list):
        raise TypeError(f"{where} must be a list")
    return [_object(item, where=f"{where} item") for item in value]


def _load_json(path: Path) -> JsonObject:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _object(value, where=str(path))


def _load_jsonl(path: Path) -> list[JsonObject]:
    rows: list[JsonObject] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value: object = json.loads(line)
        rows.append(_object(value, where=f"{path}:{line_number}"))
    return rows


def _rooted(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("configured path must be a nonempty string")
    return (root / value).resolve()


def _verify_file(path: Path, spec: Mapping[str, object]) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if "bytes" in spec and path.stat().st_size != int(spec["bytes"]):
        raise ValueError(f"file byte-size mismatch: {path}")
    if file_sha256(path) != str(spec["sha256"]):
        raise ValueError(f"file SHA-256 mismatch: {path}")


def _frozen_write(path: Path, payload: bytes) -> None:
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"refusing to overwrite nonidentical frozen artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _write_result(path: Path, value: JsonObject) -> JsonObject:
    result = dict(value)
    result["result_identity_scheme"] = (
        "SHA256_of_UTF8_canonical_sorted_compact_JSON_ensure_ascii_false_"
        "with_result_identity_sha256_omitted"
    )
    result["result_identity_sha256"] = hashlib.sha256(canonical_json_bytes(result)).hexdigest()
    payload = (json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    _frozen_write(path, payload)
    return result


def _validate_contract(root: Path, config_path: Path, contract: JsonObject) -> None:
    if contract.get("schema_version") != "jbspan-e0f-calibration-redesign-contract-v1":
        raise ValueError("unexpected E0F contract schema")
    if contract.get("status") != "FROZEN_E0F_ZERO_INFERENCE_AND_STAGED_REDESIGN_CONTRACT":
        raise ValueError("unexpected E0F contract status")
    if contract.get("frozen") is not True:
        raise ValueError("E0F contract is not frozen")
    if contract.get("new_model_inference_authorized_in_e0f_0") is not False:
        raise ValueError("E0F-0 contract must prohibit new inference")
    implementation = _object(contract.get("implementation"), where="implementation")
    expected = {
        "module": root / "src/jbspan/evaluator_panel_redesign.py",
        "script": Path(__file__).resolve(),
    }
    for name, path in expected.items():
        spec = _object(implementation.get(name), where=f"implementation.{name}")
        if _rooted(root, spec["path"]) != path:
            raise ValueError(f"E0F {name} path mismatch")
        _verify_file(path, spec)
    if config_path.resolve() != _rooted(root, contract["contract_path"]):
        raise ValueError("E0F contract self-path mismatch")


def _load_inputs(
    root: Path, contract: JsonObject
) -> tuple[list[JsonObject], list[JsonObject], JsonObject]:
    inputs = _object(contract.get("inputs"), where="inputs")
    calibration_spec = _object(inputs.get("calibration"), where="calibration input")
    calibration_path = _rooted(root, calibration_spec["path"])
    _verify_file(calibration_path, calibration_spec)
    calibration_rows = _load_jsonl(calibration_path)
    if len(calibration_rows) != int(calibration_spec["records"]):
        raise ValueError("calibration input record count mismatch")
    axis_rows: list[JsonObject] = []
    for spec in _object_rows(inputs.get("axis_files"), where="axis files"):
        path = _rooted(root, spec["path"])
        _verify_file(path, spec)
        rows = _load_jsonl(path)
        if len(rows) != int(spec["records"]):
            raise ValueError("axis input record count mismatch")
        axis_rows.extend(rows)
    source_result_spec = _object(inputs.get("e0b_source_result"), where="E0B source result")
    source_result_path = _rooted(root, source_result_spec["path"])
    _verify_file(source_result_path, source_result_spec)
    return calibration_rows, axis_rows, _load_json(source_result_path)


def _manifest_rows(
    records: Sequence[ExistingSignalRecord],
    folds: Mapping[str, int],
    stages: Mapping[str, str],
) -> tuple[list[JsonObject], list[JsonObject]]:
    fold_rows = [
        {
            "schema_version": "jbspan-e0f-calibration-fold-identity-v1",
            "record_id": record.record_id,
            "source_id": record.source_id,
            "behavior_group_sha256": record.behavior_group_sha256,
            "outer_fold": folds[record.record_id],
        }
        for record in records
    ]
    fold_rows.sort(key=lambda row: str(row["record_id"]))
    stage_order = {
        "E0F_1_SENTINEL": 0,
        "E0F_2_INTERMEDIATE": 1,
        "E0F_3_FULL": 2,
    }
    stage_rows = [
        {
            "schema_version": "jbspan-e0f-wildguard-stage-identity-v1",
            "record_id": record.record_id,
            "source_id": record.source_id,
            "behavior_group_sha256": record.behavior_group_sha256,
            "first_included_stage": stages[record.record_id],
        }
        for record in records
    ]
    stage_rows.sort(
        key=lambda row: (
            stage_order[str(row["first_included_stage"])],
            str(row["source_id"]),
            str(row["record_id"]),
        )
    )
    return fold_rows, stage_rows


def _primary_identity_manifests(
    root: Path, contract: JsonObject
) -> tuple[list[JsonObject], list[JsonObject], JsonObject]:
    heldout = _object(contract.get("heldout_boundary"), where="heldout boundary")
    input_spec = _object(heldout.get("identity_input"), where="heldout identity input")
    path = _rooted(root, input_spec["path"])
    _verify_file(path, input_spec)
    rows = _load_jsonl(path)
    if len(rows) != int(input_spec["records"]):
        raise ValueError("heldout identity count mismatch")
    forbidden = {"human_label", "human_annotation_count", "human_label_support_count"}
    if any(forbidden.intersection(row) for row in rows):
        raise ValueError("heldout identity manifest leaks human labels")
    exposed_source = str(heldout["historically_exposed_source"])
    primary = [row for row in rows if row.get("source_id") != exposed_source]
    exposed = [row for row in rows if row.get("source_id") == exposed_source]
    expected = _object(heldout.get("expected"), where="heldout expected")
    if len(primary) != int(expected["primary_records"]):
        raise ValueError("primary heldout identity count mismatch")
    if len(exposed) != int(expected["exposed_records"]):
        raise ValueError("exposed heldout identity count mismatch")
    primary_groups = len({str(row["behavior_group_sha256"]) for row in primary})
    exposed_groups = len({str(row["behavior_group_sha256"]) for row in exposed})
    if primary_groups != int(expected["primary_behavior_groups"]):
        raise ValueError("primary heldout behavior-group count mismatch")
    if exposed_groups != int(expected["exposed_behavior_groups"]):
        raise ValueError("exposed heldout behavior-group count mismatch")
    primary.sort(key=lambda row: (str(row["source_id"]), str(row["record_id"])))
    exposed.sort(key=lambda row: (str(row["source_id"]), str(row["record_id"])))
    return (
        primary,
        exposed,
        {
            "input_records": len(rows),
            "primary_records": len(primary),
            "primary_behavior_groups": primary_groups,
            "exposed_records": len(exposed),
            "exposed_behavior_groups": exposed_groups,
            "per_record_human_labels_written": False,
        },
    )


def _reconstruct_heldout_commitments(
    root: Path,
    contract: JsonObject,
    e0b_result: JsonObject,
    primary_identity_rows: Sequence[Mapping[str, object]],
    exposed_identity_rows: Sequence[Mapping[str, object]],
) -> JsonObject:
    import scripts.freeze_evaluator_panel_external_sources_e0b as e0b

    inputs = _object(contract.get("inputs"), where="inputs")
    source_contract_spec = _object(inputs.get("e0b_source_contract"), where="E0B source contract")
    source_contract_path = _rooted(root, source_contract_spec["path"])
    _verify_file(source_contract_path, source_contract_spec)
    source_contract = _load_json(source_contract_path)
    freeze_script_path = root / "scripts/freeze_evaluator_panel_external_sources_e0b.py"
    freeze_script_sha = str(
        _object(e0b_result["implementation"], where="E0B implementation")["freeze_script_sha256"]
    )
    if file_sha256(freeze_script_path) != freeze_script_sha:
        raise ValueError("E0B freeze implementation changed")
    specs = e0b._source_specs(source_contract)
    sources = (
        e0b._load_strongreject(root, specs["strongreject"]),
        e0b._load_jailbreakbench(root, specs["jailbreakbench"]),
        e0b._load_harmbench(root, specs["harmbench"]),
    )
    all_records = tuple(record for source in sources for record in source.records)
    deduplicated = deduplicate_external_records(all_records)
    split = _object(source_contract.get("split"), where="E0B split")
    split_seed = str(split["seed"])
    rows = [
        safe_manifest_record(record, split_seed=split_seed)
        for record in deduplicated.admitted_records
    ]
    rows.sort(key=lambda row: (row["partition"], row["source_id"], row["record_id"]))
    labeled_heldout = [row for row in rows if row["partition"] == "heldout"]
    full_payload = canonical_jsonl_bytes(labeled_heldout)
    frozen_full = _object(
        _object(e0b_result["safe_manifests"], where="E0B safe manifests").get(
            "heldout_labeled_commitment"
        ),
        where="E0B heldout commitment",
    )
    if len(full_payload) != int(frozen_full["bytes"]):
        raise ValueError("reconstructed full heldout labeled-byte size mismatch")
    if sha256_bytes(full_payload) != str(frozen_full["sha256"]):
        raise ValueError("reconstructed full heldout labeled commitment mismatch")
    primary = [row for row in labeled_heldout if row["source_id"] != "jailbreakbench"]
    exposed = [row for row in labeled_heldout if row["source_id"] == "jailbreakbench"]
    primary_ids = {str(row["record_id"]) for row in primary_identity_rows}
    exposed_ids = {str(row["record_id"]) for row in exposed_identity_rows}
    if {str(row["record_id"]) for row in primary} != primary_ids:
        raise ValueError("primary labeled/identity record sets differ")
    if {str(row["record_id"]) for row in exposed} != exposed_ids:
        raise ValueError("exposed labeled/identity record sets differ")
    primary_payload = canonical_jsonl_bytes(primary)
    exposed_payload = canonical_jsonl_bytes(exposed)
    return {
        "full_frozen_commitment_reconstructed_exactly": True,
        "full": {
            "records": len(labeled_heldout),
            "bytes": len(full_payload),
            "sha256": sha256_bytes(full_payload),
        },
        "primary_803": {
            "records": len(primary),
            "human_safe": sum(row["human_label"] == "SAFE" for row in primary),
            "human_harmful": sum(row["human_label"] == "HARMFUL" for row in primary),
            "bytes": len(primary_payload),
            "sha256": sha256_bytes(primary_payload),
            "labeled_rows_written": False,
        },
        "exposed_jailbreakbench_144": {
            "records": len(exposed),
            "human_safe": sum(row["human_label"] == "SAFE" for row in exposed),
            "human_harmful": sum(row["human_label"] == "HARMFUL" for row in exposed),
            "bytes": len(exposed_payload),
            "sha256": sha256_bytes(exposed_payload),
            "labeled_rows_written": False,
        },
        "raw_prompt_or_response_written": False,
        "per_record_human_label_written": False,
        "candidate_output_compared_with_primary_label": False,
    }


def _historical_exposure_audit(
    root: Path,
    contract: JsonObject,
    calibration_rows: Sequence[Mapping[str, object]],
    primary_identity_rows: Sequence[Mapping[str, object]],
    exposed_identity_rows: Sequence[Mapping[str, object]],
) -> JsonObject:
    exposure = _object(contract.get("historical_exposure"), where="exposure")
    design_spec = _object(exposure.get("design"), where="historical design")
    design_path = _rooted(root, design_spec["path"])
    _verify_file(design_path, design_spec)
    design = _load_jsonl(design_path)
    prediction_spec = _object(exposure.get("selection_predictions"), where="selection predictions")
    prediction_path = _rooted(root, prediction_spec["path"])
    _verify_file(prediction_path, prediction_spec)
    predictions = _load_jsonl(prediction_path)
    predicted_indices = {int(row["index"]) for row in predictions}
    if len(predicted_indices) != int(prediction_spec["records"]):
        raise ValueError("historical selection prediction identity count mismatch")
    calibration_locators = {
        str(row["source_locator_sha256"])
        for row in calibration_rows
        if row.get("source_id") == "jailbreakbench"
    }
    primary_locators = {
        str(row["source_locator_sha256"])
        for row in primary_identity_rows
        if row.get("source_id") == "jailbreakbench"
    }
    if primary_locators:
        raise ValueError("primary heldout must not contain JailbreakBench locators")
    exposed_locators = {str(row["source_locator_sha256"]) for row in exposed_identity_rows}
    counts: Counter[tuple[str, str, str]] = Counter()
    label_counts: Counter[tuple[str, str, int]] = Counter()
    heldout_prediction_exposed = 0
    heldout_label_only = 0
    for row in design:
        index = int(row["index"])
        subset = str(row["subset"])
        locator = source_locator_sha256("jailbreakbench", f"index:{index:06d}")
        partition = (
            "calibration"
            if locator in calibration_locators
            else "heldout"
            if locator in exposed_locators
            else "excluded"
        )
        prediction_executed = index in predicted_indices
        exposure_type = (
            "LABEL_AND_COMPONENT_PREDICTION"
            if prediction_executed
            else "LABEL_AND_FROZEN_DESIGN_ONLY"
        )
        counts[(subset, partition, exposure_type)] += 1
        label_counts[(subset, partition, int(row["human_majority"]))] += 1
        if partition == "heldout" and prediction_executed:
            heldout_prediction_exposed += 1
        if partition == "heldout" and not prediction_executed:
            heldout_label_only += 1
    expected = _object(exposure.get("expected"), where="exposure expected")
    if heldout_prediction_exposed != int(expected["heldout_prediction_exposed"]):
        raise ValueError("historical heldout prediction-exposure count mismatch")
    if heldout_label_only != int(expected["heldout_label_only"]):
        raise ValueError("historical heldout label-only count mismatch")
    return {
        "design_records": len(design),
        "completed_selection_predictions": len(predicted_indices),
        "counts": {"|".join(key): value for key, value in sorted(counts.items())},
        "aggregate_human_label_counts": {
            f"{subset}|{partition}|human_{label}": value
            for (subset, partition, label), value in sorted(label_counts.items())
        },
        "jailbreakbench_heldout": {
            "records": len(exposed_identity_rows),
            "label_and_component_prediction_exposed": heldout_prediction_exposed,
            "label_and_frozen_design_only": heldout_label_only,
            "completed_validation_predictions_found": False,
            "primary_qualification_eligible": False,
            "role": "HISTORICALLY_EXPOSED_SECONDARY_STRESS_TEST",
        },
        "primary_803_contains_jailbreakbench": False,
        "candidate_output_compared_with_primary_803": False,
    }


def _find_candidate(candidate_id: str, candidates: Sequence[Any]) -> Any:
    matches = [candidate for candidate in candidates if candidate.candidate_id == candidate_id]
    if len(matches) != 1:
        raise ValueError("candidate id does not resolve uniquely")
    return matches[0]


def audit(root: Path, config_path: Path) -> JsonObject:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    contract = _load_json(config_path)
    _validate_contract(root, config_path, contract)
    calibration_rows, axis_rows, e0b_result = _load_inputs(root, contract)
    records = build_existing_signal_records(calibration_rows, axis_rows)
    expected = _object(contract.get("expected_calibration"), where="expected calibration")
    if len(records) != int(expected["records"]):
        raise ValueError("E0F calibration count mismatch")
    if sum(record.human_label == "HARMFUL" for record in records) != int(expected["human_harmful"]):
        raise ValueError("E0F harmful denominator mismatch")
    if sum(record.human_label == "SAFE" for record in records) != int(expected["human_safe"]):
        raise ValueError("E0F safe denominator mismatch")

    candidate_contract = _object(contract.get("candidate_family"), where="candidate")
    formulas = [str(value) for value in cast(list[object], candidate_contract["formulas"])]
    if tuple(formulas) != SCORE_FORMULAS:
        raise ValueError("candidate formula family differs from implementation")
    candidates = enumerate_score_candidates(records, formulas)
    metric_rows = candidate_metric_rows(records, candidates)
    metric_payload = canonical_jsonl_bytes(metric_rows)
    frontier = pareto_frontier(metric_rows)
    final_gates = _object(contract.get("final_harmful_gates"), where="final gates")
    opening_gates = _object(contract.get("opening_harmful_gates"), where="opening gates")
    final_passes = [candidate_gate(records, candidate, final_gates) for candidate in candidates]
    final_passes = [row for row in final_passes if row["pass"] is True]
    opening_passes = [candidate_gate(records, candidate, opening_gates) for candidate in candidates]
    opening_passes = [row for row in opening_passes if row["pass"] is True]

    folds_contract = _object(contract.get("cross_validation"), where="CV")
    folds = assign_behavior_group_folds(
        records,
        fold_count=int(folds_contract["outer_folds"]),
        seed=str(folds_contract["seed"]),
    )
    stages_contract = _object(contract.get("staged_inference"), where="stages")
    stages = staged_wildguard_assignment(
        records,
        seed=str(stages_contract["seed"]),
        stage1_per_source_label=int(stages_contract["stage1_per_source_label"]),
        stage2_per_source_label=int(stages_contract["stage2_per_source_label"]),
    )
    fold_rows, stage_rows = _manifest_rows(records, folds, stages)

    recording = _object(contract.get("recording"), where="recording")
    fold_path = _rooted(root, recording["fold_manifest_path"])
    stage_path = _rooted(root, recording["stage_manifest_path"])
    fold_payload = canonical_jsonl_bytes(fold_rows)
    stage_payload = canonical_jsonl_bytes(stage_rows)
    _frozen_write(fold_path, fold_payload)
    _frozen_write(stage_path, stage_payload)

    primary_identity, exposed_identity, identity_summary = _primary_identity_manifests(
        root, contract
    )
    primary_path = _rooted(root, recording["primary_heldout_identity_path"])
    exposed_path = _rooted(root, recording["exposed_heldout_identity_path"])
    primary_payload = canonical_jsonl_bytes(primary_identity)
    exposed_payload = canonical_jsonl_bytes(exposed_identity)
    _frozen_write(primary_path, primary_payload)
    _frozen_write(exposed_path, exposed_payload)
    commitments = _reconstruct_heldout_commitments(
        root,
        contract,
        e0b_result,
        primary_identity,
        exposed_identity,
    )
    exposure = _historical_exposure_audit(
        root,
        contract,
        calibration_rows,
        primary_identity,
        exposed_identity,
    )

    selection = _object(candidate_contract.get("cv_selection"), where="CV selection")
    cv = cross_validated_precision_frontier(
        records,
        candidates,
        folds,
        precision_min=float(selection["precision_min"]),
        minimum_train_predicted_harmful=int(selection["minimum_train_predicted_harmful"]),
    )
    loso = leave_one_source_out_frontier(
        records,
        candidates,
        precision_min=float(selection["precision_min"]),
        minimum_train_predicted_harmful=int(selection["minimum_train_predicted_harmful"]),
    )
    summaries = best_frontier_summaries(
        metric_rows,
        precision_target=float(final_gates["harmful_precision_min"]),
        recall_target=float(final_gates["harmful_recall_min"]),
    )
    best_precision_id = _object(
        summaries["best_recall_at_or_above_precision_target"],
        where="best precision-constrained candidate",
    )["candidate_id"]
    best_recall_id = _object(
        summaries["best_precision_at_or_above_recall_target"],
        where="best recall-constrained candidate",
    )["candidate_id"]
    best_precision_gate = candidate_gate(
        records, _find_candidate(str(best_precision_id), candidates), final_gates
    )
    best_recall_gate = candidate_gate(
        records, _find_candidate(str(best_recall_id), candidates), final_gates
    )

    result: JsonObject = {
        "schema_version": "jbspan-e0f-zero-inference-audit-safe-v1",
        "status": "E0F_0_ZERO_INFERENCE_AUDIT_PASS_AUTHORIZE_AT_MOST_144_SENTINEL",
        "date": "2026-09-02",
        "evidence_class": "CALIBRATION_ONLY_ZERO_INFERENCE_POST_FAILURE_DEVELOPMENT",
        "paper_validity": False,
        "panel_qualified": False,
        "new_model_inference_performed": False,
        "contract": {
            "path": config_path.relative_to(root).as_posix(),
            "sha256": file_sha256(config_path),
        },
        "input_integrity": {
            "calibration_records": len(records),
            "human_safe": sum(record.human_label == "SAFE" for record in records),
            "human_harmful": sum(record.human_label == "HARMFUL" for record in records),
            "behavior_groups": len({record.behavior_group_sha256 for record in records}),
            "axis_rows": len(axis_rows),
            "record_family_axis_cells": len(axis_rows),
            "invalid_or_missing_axis_cells": 0,
            "raw_prompt_or_response_written": False,
        },
        "atomic_signal_audit": atomic_signal_audit(records),
        "b0_source_blind_frontier": {
            "candidate_formulas": formulas,
            "candidate_count": len(candidates),
            "all_metric_rows_sha256": sha256_bytes(metric_payload),
            "all_metric_rows_written": False,
            "pareto_frontier": frontier,
            **summaries,
            "best_precision_constrained_final_gate": best_precision_gate,
            "best_recall_constrained_final_gate": best_recall_gate,
            "candidates_passing_all_final_harmful_gates": final_passes,
            "candidates_passing_all_opening_harmful_gates": opening_passes,
            "b0_harmful_final_gate_pass": bool(final_passes),
            "b0_harmful_opening_margin_pass": bool(opening_passes),
            "safe_axis_resolved_without_wildguard": False,
            "b0_can_be_frozen_as_complete_panel": False,
        },
        "cross_validation": {
            "fold_summary": fold_summary(records, folds),
            "precision_constrained_out_of_fold": cv,
            "leave_one_source_out": loso,
        },
        "staged_wildguard": {
            "summary": stage_summary(records, stages),
            "stage1_authorized_calls": 144,
            "stage2_cumulative_calls": 300,
            "stage3_cumulative_calls": 889,
            "stage1_is_qualification": False,
            "stage1_role": "SCIENTIFIC_FUTILITY_SENTINEL_ONLY",
        },
        "historical_exposure": exposure,
        "heldout_boundary": {
            **identity_summary,
            "primary_identity_manifest": {
                "path": primary_path.relative_to(root).as_posix(),
                "bytes": len(primary_payload),
                "sha256": sha256_bytes(primary_payload),
                "human_labels_present": False,
            },
            "exposed_identity_manifest": {
                "path": exposed_path.relative_to(root).as_posix(),
                "bytes": len(exposed_payload),
                "sha256": sha256_bytes(exposed_payload),
                "human_labels_present": False,
            },
            "labeled_commitments": commitments,
            "primary_candidate_comparison_opened": False,
        },
        "safe_manifests": {
            "calibration_folds": {
                "path": fold_path.relative_to(root).as_posix(),
                "bytes": len(fold_payload),
                "sha256": sha256_bytes(fold_payload),
                "records": len(fold_rows),
            },
            "wildguard_stages": {
                "path": stage_path.relative_to(root).as_posix(),
                "bytes": len(stage_payload),
                "sha256": sha256_bytes(stage_payload),
                "records": len(stage_rows),
            },
        },
        "scientific_decision": {
            "existing_mistral_phi_b0_complete_panel_qualified": False,
            "wildguard_full_889_run_authorized": False,
            "wildguard_intermediate_300_run_authorized": False,
            "wildguard_sentinel_144_run_authorized": True,
            "heldout_run_authorized": False,
            "p3_rescore_authorized": False,
            "topology_authorized": False,
            "next_operation": "REVIEW_E0F_0_THEN_RUN_AT_MOST_144_WILDGUARD_SENTINEL",
        },
        "protected_boundary": {
            "heldout_candidate_outputs_generated": False,
            "heldout_candidate_metrics_computed": False,
            "p3_responses_opened": False,
            "topology_outcomes_opened": False,
        },
    }
    output_path = _rooted(root, recording["audit_result_path"])
    return _write_result(output_path, result)


def main() -> int:
    args = parser().parse_args()
    result = audit(args.root, args.config)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
