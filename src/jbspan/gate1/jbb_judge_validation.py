from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from jbspan.gate1.jbb_judge_validation_core import (
    JsonDict,
    as_array,
    as_number,
    as_object,
    as_string,
    candidates,
    canonical_sha256,
    load_json,
    load_rows,
    metrics,
    passes,
    sha256_file,
    stratified_split,
    validate_contract,
    write_json,
)


def rank_key(result: JsonDict) -> tuple[float, float, float, str]:
    value = as_object(result.get("selection_metrics"), "selection_metrics")
    return (
        -as_number(value["balanced_accuracy"], "numeric"),
        -as_number(value["macro_f1"], "numeric"),
        as_number(value["false_negative_rate"], "numeric"),
        as_string(result.get("evaluator_id"), "evaluator_id"),
    )


def validate_judges(root: Path, source_csv: Path, output_dir: Path) -> JsonDict:
    contract = load_json(root / "configs/gate1/gate1_step3b_judge_validation.json")
    validate_contract(contract)
    rows = load_rows(source_csv, contract)
    selection_ids, validation_ids = stratified_split(rows, contract)
    by_id = {row.index: row for row in rows}
    selection_rows = tuple(by_id[index] for index in selection_ids)
    validation_rows = tuple(by_id[index] for index in validation_ids)
    results: list[JsonDict] = []
    for candidate in candidates(contract):
        selection = metrics(selection_rows, candidate.evaluator_id)
        validation = metrics(validation_rows, candidate.evaluator_id)
        results.append(
            {
                "evaluator_id": candidate.evaluator_id,
                "column": candidate.column,
                "implementation_repository": candidate.implementation_repository,
                "runtime_status": candidate.runtime_status,
                "selectable_as_primary": candidate.selectable_as_primary,
                "selection_metrics": selection.to_dict(),
                "selection_pass": passes(selection, contract),
                "validation_metrics": validation.to_dict(),
                "validation_pass": passes(validation, contract),
                "full_metrics_report_only": metrics(
                    rows,
                    candidate.evaluator_id,
                ).to_dict(),
            }
        )
    eligible = sorted(
        [
            item
            for item in results
            if item["selectable_as_primary"] is True and item["selection_pass"] is True
        ],
        key=rank_key,
    )
    selected_before = eligible[0] if eligible else None
    selected = (
        selected_before
        if selected_before is not None and selected_before["validation_pass"] is True
        else None
    )
    if selected_before is None:
        status = "NO_REPRODUCIBLE_CANDIDATE_PASSES_SELECTION"
    elif selected is None:
        status = "SELECTED_CANDIDATE_FAILS_UNTOUCHED_VALIDATION"
    elif selected["runtime_status"] == "LOCAL_REPRODUCIBLE":
        status = "PRIMARY_JUDGE_SELECTED_PENDING_WRAPPER_STABILITY"
    else:
        status = "CONDITIONAL_PRIMARY_SELECTED_RUNTIME_ACCESS_REQUIRED"
    source = as_object(contract.get("source"), "source")
    identity: JsonDict = {
        "schema_version": "gate1-step3b-jbb-source-identity-v1",
        "repository": source["repository"],
        "revision": source["revision"],
        "path": source["path"],
        "source_file_sha256": sha256_file(source_csv),
        "source_file_size_bytes": source_csv.stat().st_size,
        "row_count": len(rows),
    }
    persisted = root / "data/gate1/v2/evaluator_validation/source_identity.json"
    if persisted.is_file() and load_json(persisted) != identity:
        raise RuntimeError("pinned JBB source identity changed")
    output: JsonDict = {
        "schema_version": "gate1-step3b-jbb-judge-validation-result-v1",
        "status": status,
        "paper_validity": False,
        "gate1_decision": "NOT_EVALUATED",
        "source_identity": identity,
        "split": {
            "selection_count": len(selection_ids),
            "validation_count": len(validation_ids),
            "selection_ids_sha256": canonical_sha256(list(selection_ids)),
            "validation_ids_sha256": canonical_sha256(list(validation_ids)),
            "selection_positive_count": sum(row.human_majority for row in selection_rows),
            "validation_positive_count": sum(row.human_majority for row in validation_rows),
        },
        "candidate_results": results,
        "selected_before_validation": (
            None if selected_before is None else selected_before["evaluator_id"]
        ),
        "selected_primary_evaluator": (None if selected is None else selected["evaluator_id"]),
        "confirmatory_smoke_allowed": False,
        "wrapper_stability_required": True,
        "final_evaluation_30_observed": False,
        "gate2_heldout_10_used": False,
        "old_smoke_used_for_selection": False,
        "new_human_annotations": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "source_identity.json", identity)
    write_json(output_dir / "judge_metrics.json", output)
    write_json(
        output_dir / "primary_judge_selection.json",
        {
            "schema_version": "gate1-step3b-primary-judge-selection-v1",
            "status": status,
            "selected_before_validation": output["selected_before_validation"],
            "selected_primary_evaluator": output["selected_primary_evaluator"],
            "confirmatory_smoke_allowed": False,
            "wrapper_stability_required": True,
            "final_evaluation_30_observed": False,
            "gate2_heldout_10_used": False,
        },
    )
    return output


def metric_string(value: Mapping[str, object]) -> str:
    keys = (
        "accuracy",
        "macro_f1",
        "false_negative_rate",
        "false_positive_rate",
    )
    return "/".join(f"{as_number(value[key], 'numeric'):.3f}" for key in keys)


def write_report(result: JsonDict, path: Path) -> None:
    rows = as_array(result.get("candidate_results"), "candidate_results")
    lines = [
        "# Gate 1 Step 3B.5 — JBB Human-Majority Judge Validation",
        "",
        f"Status: **{result['status']}**",
        "",
        "## Frozen denominator",
        "",
        "- source rows: **300**",
        "- judge-selection rows: **200**",
        "- untouched judge-validation rows: **100**",
        "- reference: existing public `human_majority` labels",
        "- new human annotations: **none**",
        "",
        "## Candidate results",
        "",
        "| Evaluator | Runtime | Selection acc/F1/FNR/FPR | Selection | "
        "Validation acc/F1/FNR/FPR | Validation |",
        "|---|---|---|---|---|---|",
    ]
    for raw in rows:
        item = as_object(raw, "candidate result")
        selection = as_object(item["selection_metrics"], "selection_metrics")
        validation = as_object(item["validation_metrics"], "validation_metrics")
        selection_status = "PASS" if item["selection_pass"] is True else "FAIL"
        validation_status = "PASS" if item["validation_pass"] is True else "FAIL"
        lines.append(
            f"| {item['evaluator_id']} | `{item['runtime_status']}` | "
            f"{metric_string(selection)} | {selection_status} | "
            f"{metric_string(validation)} | {validation_status} |"
        )
    lines.extend(
        [
            "",
            "## Frozen decision",
            "",
            f"- selected before validation: `{result['selected_before_validation']}`",
            f"- selected primary evaluator: `{result['selected_primary_evaluator']}`",
            "- confirmatory smoke allowed: **false**",
            "- wrapper/refusal-prefix stability still required: **true**",
            "- final evaluation 30 observed: **false**",
            "- Gate 2 held-out 10 used: **false**",
            "- Gate 1 decision: **NOT EVALUATED**",
            "",
            "The JSON files are the canonical numeric source. "
            "No raw prompt or response text is committed.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
