from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR.parent / "src"
for import_root in (SCRIPT_DIR, SOURCE_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import run_evaluator_panel_wildguard_cumulative_sentinel_e0f1b_v1_1 as storage  # type: ignore[import-not-found]  # noqa: E402
import run_evaluator_panel_wildguard_sentinel_e0f1 as base  # type: ignore[import-not-found]  # noqa: E402

from jbspan.evaluator_panel import sanitize_untrusted_text  # noqa: E402
from jbspan.evaluator_panel_redesign import ExistingSignalRecord  # noqa: E402
from jbspan.evaluator_panel_selective import (  # noqa: E402
    evaluate_selective_panel,
    select_safe_rule_on_development,
)
from jbspan.evaluator_panel_wildguard_sentinel import (  # noqa: E402
    SentinelRecord,
    build_sentinel_records,
    evaluate_sentinel,
)

JsonObject = dict[str, Any]

EXPECTED_SCHEMA = "jbspan-e0f2-prospective-selective-panel-contract-v1"
EXPECTED_STATUS = "FROZEN_BEFORE_ANY_E0F2_ADDITION_OUTPUT"
EXPECTED_ADOPTED_RECORDS = 144
EXPECTED_ADDITION_RECORDS = 156
EXPECTED_CUMULATIVE_RECORDS = 300
EXPECTED_PRIOR_UNOPENED_CALLS = 14
PER_CELL_ADDITIONS = 26
SOURCES = ("harmbench", "jailbreakbench", "strongreject")
LABELS = ("HARMFUL", "SAFE")
LOCKED_HARMFUL_CANDIDATE = "B5_wildguard_or_full_ga_precision_anchor"
LOCKED_SAFE_RULE = "S1_wildguard_unharmful_refusal"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    preflight_command = commands.add_parser("preflight")
    run_command = commands.add_parser("run")
    for command in (preflight_command, run_command):
        command.add_argument("--root", type=Path, default=Path("."))
        command.add_argument(
            "--contract",
            type=Path,
            default=Path(
                "configs/evaluator_panel/"
                "calibration_redesign_e0f2_prospective_confirmation_v1.json"
            ),
        )
    run_command.add_argument(
        "--confirm-reviewed-e0f2-preflight",
        action="store_true",
        help="Required guard against automatic execution after the zero-inference preflight.",
    )
    return value


def _dependency_path(
    root: Path,
    dependencies: Mapping[str, object],
    name: str,
) -> Path:
    return base.verify_file(root, dependencies[name], label=f"E0F-2 dependency {name}")


def _rank(seed: str, *parts: str) -> str:
    return hashlib.sha256("|".join((seed, *parts)).encode()).hexdigest()


def _metric(value: object, *, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{where} must be numeric")
    return float(value)


def _locked_harmful_spec(base_contract: Mapping[str, object]) -> JsonObject:
    candidates = base.object_rows(base_contract["candidate_specs"], where="candidate specs")
    matches = [row for row in candidates if row.get("candidate_id") == LOCKED_HARMFUL_CANDIDATE]
    if len(matches) != 1:
        raise ValueError("locked E0F-2 harmful candidate is not unique")
    return matches[0]


def _locked_safe_spec(contract: Mapping[str, object]) -> JsonObject:
    development = base.object_value(contract["development_lock"], where="development lock")
    candidates = base.object_rows(development["safe_rule_candidates"], where="safe candidates")
    matches = [row for row in candidates if row.get("safe_rule_id") == LOCKED_SAFE_RULE]
    if len(matches) != 1:
        raise ValueError("locked E0F-2 safe rule is not unique")
    return matches[0]


def validate_contract(
    root: Path,
    contract_path: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    contract = base.load_object(contract_path)
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unexpected E0F-2 contract schema")
    if contract.get("status") != EXPECTED_STATUS or contract.get("frozen") is not True:
        raise ValueError("E0F-2 contract is not frozen before addition outputs")
    if base.rooted(root, contract["contract_path"]) != contract_path.resolve():
        raise ValueError("E0F-2 contract self-path mismatch")
    expected_counts = {
        "adopted_scientific_records": EXPECTED_ADOPTED_RECORDS,
        "addition_scientific_records": EXPECTED_ADDITION_RECORDS,
        "cumulative_scientific_records": EXPECTED_CUMULATIVE_RECORDS,
        "new_completion_call_ceiling": EXPECTED_ADDITION_RECORDS,
    }
    for name, expected in expected_counts.items():
        if int(str(contract.get(name))) != expected:
            raise ValueError(f"unexpected E0F-2 count: {name}")
    if contract.get("automatic_execution_after_preflight") is not False:
        raise ValueError("E0F-2 must prohibit automatic execution")

    implementation = base.object_value(contract["implementation"], where="implementation")
    runner_path = base.verify_file(root, implementation["runner"], label="E0F-2 runner")
    selective_path = base.verify_file(
        root, implementation["selective_module"], label="selective module"
    )
    sentinel_path = base.verify_file(
        root, implementation["sentinel_module"], label="sentinel module"
    )
    parser_path = base.verify_file(root, implementation["parser_module"], label="parser module")
    storage_path = base.verify_file(
        root, implementation["minimal_storage_runner"], label="minimal storage runner"
    )
    if runner_path != Path(__file__).resolve():
        raise ValueError("unexpected E0F-2 runner path")
    if selective_path != (root / "src/jbspan/evaluator_panel_selective.py").resolve():
        raise ValueError("unexpected selective-panel module path")
    if sentinel_path != (root / "src/jbspan/evaluator_panel_wildguard_sentinel.py").resolve():
        raise ValueError("unexpected sentinel module path")
    if parser_path != (root / "src/jbspan/evaluator_panel.py").resolve():
        raise ValueError("unexpected parser module path")
    if storage_path != Path(storage.__file__).resolve():
        raise ValueError("unexpected minimal-storage runner path")

    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    for name in dependencies:
        _dependency_path(root, dependencies, name)

    base_contract_path = _dependency_path(root, dependencies, "e0f1_contract")
    base_contract = base.validate_contract(root, base_contract_path)
    if base.canonical_sha256(base_contract["candidate_specs"]) != str(
        contract["inherited_candidate_specs_sha256"]
    ):
        raise ValueError("E0F-2 candidate family differs from the pre-output E0F-1 family")
    if base.canonical_sha256(base_contract["calibration_population"]) != str(
        contract["inherited_calibration_population_sha256"]
    ):
        raise ValueError("E0F-2 calibration projection population changed")

    e0f_contract = base.load_object(_dependency_path(root, dependencies, "e0f_contract"))
    staged = base.object_value(e0f_contract["staged_inference"], where="staged inference")
    if int(str(staged["stage2_cumulative_total"])) != EXPECTED_CUMULATIVE_RECORDS:
        raise ValueError("original E0F-2 cumulative target changed")
    if int(str(staged["stage2_per_source_label"])) != 50:
        raise ValueError("original E0F-2 source/label quota changed")

    predecessor_result = base.load_object(
        _dependency_path(root, dependencies, "e0f1b_result")
    )
    base.verify_result_identity(predecessor_result, label="E0F-1B result")
    result_spec = base.object_value(dependencies["e0f1b_result"], where="E0F-1B result")
    if predecessor_result.get("result_identity_sha256") != result_spec.get(
        "result_identity_sha256"
    ):
        raise ValueError("E0F-1B result identity mismatch")
    if predecessor_result.get("status") != (
        "E0F1B_CUMULATIVE_PASS_AUTHORIZE_E0F2_300_DESIGN_REVIEW"
    ):
        raise ValueError("E0F-1B did not authorize E0F-2 design review")
    passing = base.object_value(
        predecessor_result["candidate_evaluation"], where="candidate evaluation"
    )["passing_candidate_ids"]
    if passing != [LOCKED_HARMFUL_CANDIDATE]:
        raise ValueError("E0F-2 harmful lock does not match the sole E0F-1B survivor")

    predecessor_contract = base.load_object(
        _dependency_path(root, dependencies, "e0f1b_contract")
    )
    if base.canonical_sha256(contract["runtime"]) != base.canonical_sha256(
        predecessor_contract["runtime"]
    ):
        raise ValueError("E0F-2 runtime differs from E0F-1B")
    if base.canonical_sha256(contract["inference"]) != base.canonical_sha256(
        predecessor_contract["inference"]
    ):
        raise ValueError("E0F-2 inference differs from E0F-1B")
    if contract.get("minimal_private_schema") != storage.PRIVATE_SCHEMA:
        raise ValueError("E0F-2 must reuse the no-raw V1.1 private schema")
    _locked_harmful_spec(base_contract)
    _locked_safe_spec(contract)
    return contract, base_contract, e0f_contract, predecessor_result


def _load_adopted_rows(
    root: Path,
    contract: Mapping[str, object],
    existing: Sequence[ExistingSignalRecord],
) -> tuple[list[JsonObject], set[str]]:
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    axis_path = _dependency_path(root, dependencies, "e0f1b_axis")
    rows = base.load_jsonl(axis_path)
    selected_ids = {str(row["record_id"]) for row in rows}
    if len(rows) != EXPECTED_ADOPTED_RECORDS or len(selected_ids) != len(rows):
        raise ValueError("E0F-2 adoption must contain exactly 144 unique records")
    build_sentinel_records(existing, rows, selected_record_ids=selected_ids)
    if base.integrity_summary(rows, EXPECTED_ADOPTED_RECORDS)["pass"] is not True:
        raise ValueError("E0F-1B adopted axis fails integrity")
    return rows, selected_ids


def _select_additions(
    root: Path,
    contract: Mapping[str, object],
    base_contract: Mapping[str, object],
    existing: Sequence[ExistingSignalRecord],
    adopted_ids: set[str],
) -> tuple[list[ExistingSignalRecord], list[JsonObject], JsonObject]:
    inputs = base.object_value(base_contract["inputs"], where="base inputs")
    stage_path = base.verify_file(root, inputs["stage_manifest"], label="stage manifest")
    stage_rows = base.load_jsonl(stage_path)
    stage_by_id = {str(row["record_id"]): str(row["first_included_stage"]) for row in stage_rows}
    target_ids = {
        record_id
        for record_id, stage in stage_by_id.items()
        if stage in {"E0F_1_SENTINEL", "E0F_2_INTERMEDIATE"}
    }
    if len(target_ids) != EXPECTED_CUMULATIVE_RECORDS:
        raise ValueError("original cumulative E0F-2 target is not exactly 300 records")
    if not adopted_ids.issubset(target_ids):
        raise ValueError("E0F-1B adoption falls outside the original cumulative E0F-2 target")
    existing_by_id = {record.record_id: record for record in existing}
    if not target_ids.issubset(existing_by_id):
        raise ValueError("E0F-2 target falls outside calibration")
    remaining = [existing_by_id[record_id] for record_id in target_ids - adopted_ids]
    if len(remaining) != EXPECTED_ADDITION_RECORDS:
        raise ValueError("E0F-2 identity complement is not exactly 156 records")

    selection = base.object_value(contract["addition_selection"], where="addition selection")
    seed = str(selection["execution_order_seed"])
    by_cell: dict[tuple[str, str], list[ExistingSignalRecord]] = defaultdict(list)
    for record in remaining:
        by_cell[(record.source_id, record.human_label)].append(record)
    for source in SOURCES:
        for label in LABELS:
            cell = by_cell[(source, label)]
            if len(cell) != PER_CELL_ADDITIONS:
                raise ValueError(f"E0F-2 complement imbalance for {source}:{label}")
            cell.sort(
                key=lambda record: (
                    _rank(seed, source, label, record.record_id),
                    record.record_id,
                )
            )

    ordered: list[ExistingSignalRecord] = []
    round_by_id: dict[str, int] = {}
    for round_index in range(PER_CELL_ADDITIONS):
        round_records = [
            by_cell[(source, label)][round_index] for source in SOURCES for label in LABELS
        ]
        round_records.sort(
            key=lambda record: _rank(seed, "within-round", str(round_index), record.record_id)
        )
        ordered.extend(round_records)
        round_by_id.update({record.record_id: round_index + 1 for record in round_records})

    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    prior_rows = base.load_jsonl(
        _dependency_path(root, dependencies, "e0f1_unopened_call_identities")
    )
    prior_ids = {str(row["record_id"]) for row in prior_rows}
    if len(prior_rows) != EXPECTED_PRIOR_UNOPENED_CALLS or len(prior_ids) != len(prior_rows):
        raise ValueError("prior unopened E0F-1 call identity count changed")
    if not prior_ids.issubset({record.record_id for record in ordered}):
        raise ValueError("prior unopened E0F-1 identities are not all in the E0F-2 complement")

    identity_rows = [
        {
            "schema_version": "jbspan-e0f2-addition-identity-v1",
            "record_id": record.record_id,
            "source_id": record.source_id,
            "behavior_group_sha256": record.behavior_group_sha256,
            "parent_first_included_stage": stage_by_id[record.record_id],
            "execution_round": round_by_id[record.record_id],
            "execution_order_sha256": _rank(seed, "selected", record.record_id),
            "previously_called_in_unopened_e0f1_v1": record.record_id in prior_ids,
            "predecessor_private_content_opened": False,
            "human_label_written": False,
        }
        for record in ordered
    ]
    cumulative_records = [existing_by_id[record_id] for record_id in adopted_ids] + ordered
    adopted_groups = {
        existing_by_id[record_id].behavior_group_sha256 for record_id in adopted_ids
    }
    addition_groups = {record.behavior_group_sha256 for record in ordered}
    cumulative_group_counts = Counter(
        record.behavior_group_sha256 for record in cumulative_records
    )
    summary: JsonObject = {
        "selection_rule": "exact identity complement of the original frozen cumulative-300 target",
        "target_records": len(target_ids),
        "adopted_records": len(adopted_ids),
        "addition_records": len(ordered),
        "addition_source_label_counts": dict(
            sorted(Counter(f"{r.source_id}:{r.human_label}" for r in ordered).items())
        ),
        "addition_parent_stage_counts": dict(
            sorted(Counter(stage_by_id[r.record_id] for r in ordered).items())
        ),
        "prior_unopened_e0f1_calls_in_addition": len(prior_ids),
        "addition_unique_behavior_groups": len(addition_groups),
        "addition_groups_overlapping_adopted": len(addition_groups & adopted_groups),
        "cumulative_unique_behavior_groups": len(cumulative_group_counts),
        "cumulative_maximum_records_per_behavior_group": max(cumulative_group_counts.values()),
        "execution_rounds": PER_CELL_ADDITIONS,
        "records_per_round": len(SOURCES) * len(LABELS),
        "selection_uses_e0f1b_predictions": False,
        "per_record_human_labels_written": False,
    }
    return ordered, identity_rows, summary


def _build_plan(
    root: Path,
    contract: Mapping[str, object],
    base_contract: Mapping[str, object],
    selected: Sequence[ExistingSignalRecord],
) -> tuple[list[base.ScientificPlanRecord], JsonObject]:
    texts = base.reconstruct_text_records(root, dict(base_contract))
    text_by_id = {record.record_id: record for record in texts}
    prompt_spec = base.object_value(
        base.object_value(base_contract["inputs"], where="base inputs")["prompt_template"],
        where="prompt template",
    )
    prompt_path = base.verify_file(root, prompt_spec, label="E0F-2 WildGuard prompt")
    template = prompt_path.read_text(encoding="utf-8")
    inference = base.object_value(contract["inference"], where="inference")
    nonce = str(inference["nonce"])
    max_characters = int(str(inference["max_untrusted_characters"]))
    plan: list[base.ScientificPlanRecord] = []
    truncations = 0
    counts: Counter[str] = Counter()
    for signal_record in selected:
        text_record = text_by_id[signal_record.record_id]
        request = sanitize_untrusted_text(text_record.question, max_characters=max_characters)
        response = sanitize_untrusted_text(text_record.response, max_characters=max_characters)
        classifier_input = template.format(
            nonce=nonce,
            prompt=request.text,
            response=response.text,
        )
        truncated = request.truncated or response.truncated
        truncations += truncated
        safe: JsonObject = {
            "schema_version": "jbspan-e0f2-wildguard-addition-plan-record-v1",
            "record_id": signal_record.record_id,
            "source_id": signal_record.source_id,
            "behavior_group_sha256": signal_record.behavior_group_sha256,
            "response_sha256": text_record.response_sha256,
            "question_sanitization": base.sanitization_metadata(request),
            "response_sanitization": base.sanitization_metadata(response),
            "source_input_truncated": truncated,
            "classifier_input_sha256": hashlib.sha256(classifier_input.encode()).hexdigest(),
            "classifier_input_utf8_bytes": len(classifier_input.encode("utf-8")),
            "human_label_written": False,
        }
        safe["judge_input_identity_sha256"] = base.canonical_sha256(safe)
        plan.append(
            base.ScientificPlanRecord(
                safe=safe,
                question=text_record.question,
                response=text_record.response,
                classifier_input=classifier_input,
            )
        )
        counts[f"{signal_record.source_id}:{signal_record.human_label}"] += 1
    expected_counts = {
        f"{source}:{label}": PER_CELL_ADDITIONS for source in SOURCES for label in LABELS
    }
    if dict(sorted(counts.items())) != dict(sorted(expected_counts.items())):
        raise ValueError("E0F-2 plan differs from the frozen source/label balance")
    if truncations:
        raise ValueError("E0F-2 plan contains source-input truncation")
    safe_rows = [record.safe for record in plan]
    return plan, {
        "records": len(plan),
        "source_label_counts": dict(sorted(counts.items())),
        "source_input_truncation_count": truncations,
        "plan_identity_sha256": base.canonical_sha256(safe_rows),
        "maximum_classifier_input_utf8_bytes": max(
            int(row["classifier_input_utf8_bytes"]) for row in safe_rows
        ),
        "raw_text_written_to_safe_plan": False,
    }


def prepare_design(
    root: Path,
    contract_path: Path,
) -> tuple[
    JsonObject,
    JsonObject,
    tuple[ExistingSignalRecord, ...],
    list[JsonObject],
    list[base.ScientificPlanRecord],
    list[JsonObject],
    JsonObject,
    JsonObject,
]:
    contract, base_contract, _, predecessor_result = validate_contract(root, contract_path)
    existing = base.load_existing_records(root, base_contract)
    adopted_rows, adopted_ids = _load_adopted_rows(root, contract, existing)
    selected, identity_rows, selection_summary = _select_additions(
        root,
        contract,
        base_contract,
        existing,
        adopted_ids,
    )
    plan, plan_summary = _build_plan(root, contract, base_contract, selected)
    if [str(record.safe["record_id"]) for record in plan] != [
        str(row["record_id"]) for row in identity_rows
    ]:
        raise ValueError("E0F-2 identity and scientific-plan orders differ")
    return (
        contract,
        base_contract,
        existing,
        adopted_rows,
        plan,
        identity_rows,
        {"selection": selection_summary, "plan": plan_summary},
        predecessor_result,
    )


def _development_lock(
    root: Path,
    contract: Mapping[str, object],
    base_contract: Mapping[str, object],
    existing: Sequence[ExistingSignalRecord],
    adopted_rows: Sequence[Mapping[str, object]],
) -> JsonObject:
    selected_ids = {str(row["record_id"]) for row in adopted_rows}
    records = build_sentinel_records(existing, adopted_rows, selected_record_ids=selected_ids)
    harmful_spec = _locked_harmful_spec(base_contract)
    development = base.object_value(contract["development_lock"], where="development lock")
    safe_specs = base.object_rows(development["safe_rule_candidates"], where="safe rules")
    selection = select_safe_rule_on_development(
        records,
        harmful_spec=harmful_spec,
        safe_specs=safe_specs,
        selection_gates=base.object_value(development["selection_gates"], where="selection gates"),
    )
    if selection["selected_safe_rule_id"] != LOCKED_SAFE_RULE:
        raise ValueError("development safe-rule selection differs from the frozen lock")
    panel = evaluate_selective_panel(
        records,
        harmful_spec=harmful_spec,
        safe_spec=_locked_safe_spec(contract),
        population=base.object_value(base_contract["calibration_population"], where="population"),
        gates=base.object_value(contract["e0f2_confirmation_gates"], where="E0F-2 gates"),
        integrity_pass=True,
    )
    expected = base.object_value(development["expected_selected_counts"], where="expected counts")
    pooled = base.object_value(panel["pooled"], where="development pooled metrics")
    for key, value in expected.items():
        if pooled.get(key) != value:
            raise ValueError(f"development-lock count changed: {key}")
    result: JsonObject = {
        "schema_version": "jbspan-e0f2-development-panel-lock-safe-v1",
        "status": "E0F2_DEVELOPMENT_LOCK_COMPLETE_NO_NEW_INFERENCE",
        "evidence_class": "POST_E0F1B_144_RECORD_DEVELOPMENT_ONLY_NOT_CONFIRMATION",
        "contract_sha256": base.file_sha256(base.rooted(root, contract["contract_path"])),
        "development_records": len(records),
        "harmful_candidate_lock": harmful_spec,
        "safe_rule_development": selection,
        "selected_panel_e0f2_gate_diagnostic": panel,
        "selection_used_only_e0f1b_development_records": True,
        "e0f2_addition_outputs_observed": False,
        "new_model_inference_performed": False,
        "per_record_human_labels_written": False,
        "raw_prompt_or_response_written": False,
        "panel_qualified": False,
        "paper_validity": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
    }
    outputs = base.object_value(contract["outputs"], where="outputs")
    return cast(
        JsonObject,
        base.write_frozen_result(base.rooted(root, outputs["development_lock_path"]), result),
    )


def preflight(root: Path, contract_path: Path) -> JsonObject:
    (
        contract,
        base_contract,
        existing,
        adopted_rows,
        plan,
        identity_rows,
        design_summary,
        predecessor_result,
    ) = prepare_design(root, contract_path)
    outputs = base.object_value(contract["outputs"], where="outputs")
    identity_path = base.rooted(root, outputs["addition_identity_path"])
    plan_path = base.rooted(root, outputs["addition_plan_path"])
    base.frozen_write_jsonl(identity_path, identity_rows)
    base.frozen_write_jsonl(plan_path, [record.safe for record in plan])
    development_result = _development_lock(
        root,
        contract,
        base_contract,
        existing,
        adopted_rows,
    )
    runtime = base.runtime_identity(root, contract)
    result: JsonObject = {
        "schema_version": "jbspan-e0f2-prospective-confirmation-preflight-safe-v1",
        "status": "E0F2_PREFLIGHT_PASS_READY_FOR_SEPARATE_156_CALL_REVIEW",
        "evidence_class": "ZERO_NEW_INFERENCE_PROSPECTIVE_CONFIRMATION_FREEZE",
        "contract_sha256": base.file_sha256(contract_path),
        "runtime": runtime,
        "design_summary": design_summary,
        "development_lock": {
            "path": str(
                base.rooted(root, outputs["development_lock_path"]).relative_to(root)
            ),
            "bytes": base.rooted(root, outputs["development_lock_path"]).stat().st_size,
            "sha256": base.file_sha256(base.rooted(root, outputs["development_lock_path"])),
            "result_identity_sha256": development_result["result_identity_sha256"],
            "selected_harmful_candidate": LOCKED_HARMFUL_CANDIDATE,
            "selected_safe_rule": LOCKED_SAFE_RULE,
        },
        "addition_identity": {
            "path": str(identity_path.relative_to(root)),
            "records": len(identity_rows),
            "bytes": identity_path.stat().st_size,
            "sha256": base.file_sha256(identity_path),
        },
        "scientific_plan": {
            "path": str(plan_path.relative_to(root)),
            "records": len(plan),
            "bytes": plan_path.stat().st_size,
            "sha256": base.file_sha256(plan_path),
            "plan_identity_sha256": design_summary["plan"]["plan_identity_sha256"],
        },
        "predecessor_result_identity_sha256": predecessor_result["result_identity_sha256"],
        "confirmation_primary_sample": "E0F2_ADDITION_156_ONLY",
        "cumulative_300_role": "DESCRIPTIVE_SECONDARY",
        "locked_panel_only_can_determine_pass": True,
        "new_completion_call_ceiling": EXPECTED_ADDITION_RECORDS,
        "operational_ceiling_seconds": contract["operational_ceiling_seconds"],
        "runtime_projection_checkpoint_records": contract[
            "runtime_projection_checkpoint_records"
        ],
        "minimal_private_schema": storage.PRIVATE_SCHEMA,
        "new_model_inference_performed": False,
        "automatic_execution_started": False,
        "explicit_post_preflight_authorization_required": True,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "panel_qualified": False,
        "paper_validity": False,
        "next_operation": "REVIEW_PREFLIGHT_THEN_RUN_AT_MOST_156_NEW_COMPLETIONS",
    }
    return cast(
        JsonObject,
        base.write_frozen_result(base.rooted(root, outputs["preflight_path"]), result),
    )


def _panel_group_sensitivity(
    records: Sequence[SentinelRecord],
    *,
    harmful_spec: Mapping[str, object],
    safe_spec: Mapping[str, object],
    population: Mapping[str, Mapping[str, object]],
    gates: Mapping[str, object],
) -> JsonObject:
    groups = sorted({record.existing.behavior_group_sha256 for record in records})
    full = evaluate_selective_panel(
        records,
        harmful_spec=harmful_spec,
        safe_spec=safe_spec,
        population=population,
        gates=gates,
        integrity_pass=True,
    )
    rows: list[JsonObject] = []
    invalid = 0
    for group in groups:
        selected = tuple(
            record for record in records if record.existing.behavior_group_sha256 != group
        )
        try:
            rows.append(
                evaluate_selective_panel(
                    selected,
                    harmful_spec=harmful_spec,
                    safe_spec=safe_spec,
                    population=population,
                    gates=gates,
                    integrity_pass=True,
                )
            )
        except (TypeError, ValueError):
            invalid += 1

    def metric_values(section: str, name: str) -> tuple[float, list[float]]:
        full_value = _metric(
            base.object_value(full[section], where=section)[name], where=f"full {name}"
        )
        values = [
            _metric(base.object_value(row[section], where=section)[name], where=name)
            for row in rows
        ]
        return full_value, values

    summaries: JsonObject = {}
    for key, section, name in (
        ("harmful_recall", "pooled", "harmful_recall"),
        (
            "projected_harmful_precision",
            "full_calibration_projection",
            "projected_harmful_precision",
        ),
        ("safe_precision", "pooled", "safe_precision"),
        ("decided_coverage", "pooled", "decided_coverage"),
        ("minimum_source_harmful_recall", "root", "minimum_source_harmful_recall"),
    ):
        if section == "root":
            full_value = _metric(full[name], where=f"full {name}")
            values = [_metric(row[name], where=name) for row in rows]
        else:
            full_value, values = metric_values(section, name)
        summaries[key] = {
            "full": full_value,
            "leave_one_group_out_min": min(values),
            "leave_one_group_out_max": max(values),
            "maximum_absolute_shift": max(abs(value - full_value) for value in values),
        }
    return {
        "evidence_role": "DESCRIPTIVE_DEPENDENCE_SENSITIVITY_NOT_A_PASS_GATE",
        "records": len(records),
        "unique_behavior_groups": len(groups),
        "valid_group_exclusions": len(rows),
        "invalid_group_exclusions": invalid,
        "metric_summaries": summaries,
    }


def _fold_stability(
    root: Path,
    contract: Mapping[str, object],
    records: Sequence[SentinelRecord],
    *,
    harmful_spec: Mapping[str, object],
    safe_spec: Mapping[str, object],
    population: Mapping[str, Mapping[str, object]],
    gates: Mapping[str, object],
) -> list[JsonObject]:
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    fold_rows = base.load_jsonl(_dependency_path(root, dependencies, "e0f_fold_manifest"))
    fold_by_id = {str(row["record_id"]): int(str(row["outer_fold"])) for row in fold_rows}
    if not {record.record_id for record in records}.issubset(fold_by_id):
        raise ValueError("E0F-2 records are missing frozen fold assignments")
    summaries: list[JsonObject] = []
    for fold in range(5):
        selected = tuple(record for record in records if fold_by_id[record.record_id] == fold)
        result = evaluate_selective_panel(
            selected,
            harmful_spec=harmful_spec,
            safe_spec=safe_spec,
            population=population,
            gates=gates,
            integrity_pass=True,
        )
        summaries.append(
            {
                "outer_fold": fold,
                "records": len(selected),
                "behavior_groups": len(
                    {record.existing.behavior_group_sha256 for record in selected}
                ),
                "panel_evaluation": result,
                "evidence_role": "DESCRIPTIVE_FROZEN_GROUP_FOLD_STABILITY_NOT_OOF_TRAINING",
            }
        )
    return summaries


def finalize(
    root: Path,
    contract_path: Path,
    contract: JsonObject,
    base_contract: JsonObject,
    existing: Sequence[ExistingSignalRecord],
    adopted_rows: list[JsonObject],
    addition_rows: list[JsonObject],
    execution: JsonObject,
) -> JsonObject:
    outputs = base.object_value(contract["outputs"], where="outputs")
    cumulative_rows = [*adopted_rows, *addition_rows]
    cumulative_axis_path = base.rooted(root, outputs["cumulative_axis_path"])
    base.frozen_write_jsonl(cumulative_axis_path, cumulative_rows)
    addition_ids = {str(row["record_id"]) for row in addition_rows}
    cumulative_ids = {str(row["record_id"]) for row in cumulative_rows}
    addition_records = build_sentinel_records(
        existing, addition_rows, selected_record_ids=addition_ids
    )
    cumulative_records = build_sentinel_records(
        existing, cumulative_rows, selected_record_ids=cumulative_ids
    )
    candidates = base.object_rows(base_contract["candidate_specs"], where="candidates")
    population = base.object_value(base_contract["calibration_population"], where="population")
    gates = base.object_value(contract["e0f2_confirmation_gates"], where="E0F-2 gates")
    harmful_spec = _locked_harmful_spec(base_contract)
    safe_spec = _locked_safe_spec(contract)
    addition_integrity = base.integrity_summary(addition_rows, EXPECTED_ADDITION_RECORDS)
    cumulative_integrity = base.integrity_summary(cumulative_rows, EXPECTED_CUMULATIVE_RECORDS)
    addition_panel = evaluate_selective_panel(
        addition_records,
        harmful_spec=harmful_spec,
        safe_spec=safe_spec,
        population=population,
        gates=gates,
        integrity_pass=addition_integrity["pass"] is True,
    )
    cumulative_panel = evaluate_selective_panel(
        cumulative_records,
        harmful_spec=harmful_spec,
        safe_spec=safe_spec,
        population=population,
        gates=gates,
        integrity_pass=cumulative_integrity["pass"] is True,
    )
    addition_candidates = evaluate_sentinel(
        addition_records,
        candidates,
        population=population,
        gates=gates,
        integrity_pass=addition_integrity["pass"] is True,
    )
    cumulative_candidates = evaluate_sentinel(
        cumulative_records,
        candidates,
        population=population,
        gates=gates,
        integrity_pass=cumulative_integrity["pass"] is True,
    )
    passed = addition_panel["pass"] is True
    addition_axis_path = base.rooted(root, outputs["addition_axis_path"])
    result: JsonObject = {
        "schema_version": "jbspan-e0f2-prospective-selective-panel-result-safe-v1",
        "status": (
            "E0F2_PROSPECTIVE_PASS_AUTHORIZE_E0F3_DESIGN_REVIEW"
            if passed
            else "E0F2_PROSPECTIVE_FAIL_STOP_EXACT_PANEL_PATH"
        ),
        "evidence_class": "PROSPECTIVE_156_RECORD_CALIBRATION_CONFIRMATION_NOT_QUALIFICATION",
        "contract_sha256": base.file_sha256(contract_path),
        "runtime": execution["runtime"],
        "execution": execution,
        "primary_confirmation": {
            "sample": "E0F2_ADDITION_156_ONLY",
            "panel_evaluation": addition_panel,
            "integrity": addition_integrity,
            "frozen_candidate_comparators": addition_candidates,
        },
        "secondary_cumulative_300": {
            "role": "DESCRIPTIVE_NOT_THE_PASS_SAMPLE",
            "panel_evaluation": cumulative_panel,
            "integrity": cumulative_integrity,
            "frozen_candidate_comparators": cumulative_candidates,
        },
        "dependence_diagnostics": {
            "addition_leave_one_behavior_group_out": _panel_group_sensitivity(
                addition_records,
                harmful_spec=harmful_spec,
                safe_spec=safe_spec,
                population=population,
                gates=gates,
            ),
            "addition_frozen_group_fold_stability": _fold_stability(
                root,
                contract,
                addition_records,
                harmful_spec=harmful_spec,
                safe_spec=safe_spec,
                population=population,
                gates=gates,
            ),
        },
        "addition_axis_artifact": {
            "path": str(addition_axis_path.relative_to(root)),
            "records": len(addition_rows),
            "bytes": addition_axis_path.stat().st_size,
            "sha256": base.file_sha256(addition_axis_path),
        },
        "cumulative_axis_artifact": {
            "path": str(cumulative_axis_path.relative_to(root)),
            "records": len(cumulative_rows),
            "bytes": cumulative_axis_path.stat().st_size,
            "sha256": base.file_sha256(cumulative_axis_path),
        },
        "scientific_decision": {
            "e0f2_prospective_confirmation_pass": passed,
            "only_locked_panel_can_determine_pass": True,
            "e0f3_full_889_design_may_be_frozen_after_review": passed,
            "automatic_e0f3_execution_started": False,
            "heldout_authorized": False,
            "p3_rescore_authorized": False,
            "topology_authorized": False,
            "next_operation": (
                "REVIEW_E0F2_THEN_FREEZE_E0F3_FULL_889_DESIGN"
                if passed
                else "STOP_EXACT_B5_SELECTIVE_PANEL_WITHOUT_HELDOUT"
            ),
        },
        "new_model_calls": EXPECTED_ADDITION_RECORDS,
        "cumulative_records": EXPECTED_CUMULATIVE_RECORDS,
        "prior_unopened_e0f1_outputs_used": False,
        "per_record_human_labels_written": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "panel_qualified": False,
        "paper_validity": False,
    }
    return cast(
        JsonObject,
        base.write_frozen_result(base.rooted(root, outputs["result_path"]), result),
    )


def _write_runtime_interruption(
    root: Path,
    contract: Mapping[str, object],
    *,
    completed_records: int,
    new_calls: int,
    cache_hits: int,
    elapsed_seconds: float,
    projected_total_seconds: float,
    reason: str,
) -> JsonObject:
    outputs = base.object_value(contract["outputs"], where="outputs")
    result: JsonObject = {
        "schema_version": "jbspan-e0f2-operational-interruption-safe-v1",
        "status": "E0F2_OPERATIONAL_STOP_PRESERVE_MINIMAL_CACHE_NO_METRICS",
        "evidence_class": "OPERATIONAL_RUNTIME_ONLY_NOT_SCIENTIFIC_RESULT",
        "contract_sha256": base.file_sha256(base.rooted(root, contract["contract_path"])),
        "stop_reason": reason,
        "completed_private_records": completed_records,
        "new_completion_calls_this_invocation": new_calls,
        "cache_hits": cache_hits,
        "elapsed_seconds": elapsed_seconds,
        "projected_total_seconds": projected_total_seconds,
        "operational_ceiling_seconds": contract["operational_ceiling_seconds"],
        "safe_axis_written": False,
        "scientific_result_written": False,
        "candidate_metrics_opened": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "panel_qualified": False,
        "paper_validity": False,
        "next_operation": "AUDIT_RUNTIME_BEFORE_ANY_RESUME_OR_AMENDMENT",
    }
    return cast(
        JsonObject,
        base.write_frozen_result(
            base.rooted(root, outputs["operational_interruption_path"]), result
        ),
    )


def run(root: Path, contract_path: Path, *, confirmed: bool) -> JsonObject:
    (
        contract,
        base_contract,
        existing,
        adopted_rows,
        plan,
        _,
        _,
        _,
    ) = prepare_design(root, contract_path)
    outputs = base.object_value(contract["outputs"], where="outputs")
    result_path = base.rooted(root, outputs["result_path"])
    if result_path.is_file():
        result = base.load_object(result_path)
        base.verify_result_identity(result, label="existing E0F-2 result")
        return cast(JsonObject, result)
    if not confirmed:
        raise PermissionError("E0F-2 requires --confirm-reviewed-e0f2-preflight")
    preflight_path = base.rooted(root, outputs["preflight_path"])
    if not preflight_path.is_file():
        raise FileNotFoundError("E0F-2 preflight must pass before execution")
    preflight_result = base.load_object(preflight_path)
    base.verify_result_identity(preflight_result, label="E0F-2 preflight")
    if preflight_result.get("status") != "E0F2_PREFLIGHT_PASS_READY_FOR_SEPARATE_156_CALL_REVIEW":
        raise ValueError("E0F-2 preflight status mismatch")
    if preflight_result.get("contract_sha256") != base.file_sha256(contract_path):
        raise ValueError("E0F-2 contract changed after preflight")

    addition_axis_path = base.rooted(root, outputs["addition_axis_path"])
    cumulative_axis_path = base.rooted(root, outputs["cumulative_axis_path"])
    execution_path = base.rooted(root, outputs["execution_path"])
    terminal = (addition_axis_path, cumulative_axis_path, execution_path)
    if any(path.is_file() for path in terminal):
        if not all(path.is_file() for path in terminal):
            raise ValueError("partial E0F-2 terminal artifacts require audit")
        addition_rows = base.load_jsonl(addition_axis_path)
        if base.load_jsonl(cumulative_axis_path) != [*adopted_rows, *addition_rows]:
            raise ValueError("existing E0F-2 cumulative axis mismatch")
        execution = base.load_object(execution_path)
        base.verify_result_identity(execution, label="E0F-2 execution")
        return finalize(
            root,
            contract_path,
            contract,
            base_contract,
            existing,
            adopted_rows,
            addition_rows,
            execution,
        )

    runtime = base.runtime_identity(root, contract)
    runtime_spec = base.object_value(contract["runtime"], where="runtime")
    server_path = base.rooted(
        root, base.object_value(runtime_spec["server"], where="server")["path"]
    )
    model_path = base.rooted(
        root, base.object_value(runtime_spec["model"], where="model")["path"]
    )
    inference = base.object_value(contract["inference"], where="inference")
    implementation = base.object_value(contract["implementation"], where="implementation")
    artifact_root = base.rooted(root, outputs["private_artifact_root"])
    private_dir = artifact_root / "private_records"
    private_dir.mkdir(parents=True, exist_ok=True)
    contract_sha = base.file_sha256(contract_path)
    started = time.monotonic()
    addition_rows: list[JsonObject] = []
    cache_hits = 0
    new_calls = 0
    failures = 0
    with base.local_server(
        server_path=server_path,
        model_path=model_path,
        port=int(str(runtime_spec["port"])),
        inference=inference,
        log_path=artifact_root / "server_logs/wildguard.log",
    ) as (server_url, startup_seconds):
        for index, plan_record in enumerate(plan, 1):
            safe, cache_hit, new_completion, _ = storage.execute_minimal_record(
                plan=plan_record,
                server_url=server_url,
                private_dir=private_dir,
                contract_sha256=contract_sha,
                implementation=implementation,
                model_sha256=str(runtime["model_sha256"]),
                inference=inference,
            )
            addition_rows.append(safe)
            cache_hits += cache_hit
            new_calls += new_completion
            failures += safe["eligible_measurement"] is not True
            if index % 6 == 0 or index == len(plan):
                elapsed = time.monotonic() - started
                print(
                    "E0F2_PROGRESS "
                    f"completed={index}/{len(plan)} new_calls={new_calls} "
                    f"cache_hits={cache_hits} integrity_failures={failures} "
                    f"elapsed_seconds={elapsed:.1f}",
                    flush=True,
                )
                checkpoint = int(str(contract["runtime_projection_checkpoint_records"]))
                observed = [
                    _metric(row["first_execution_elapsed_seconds"], where="record elapsed")
                    for row in addition_rows
                ]
                projected = startup_seconds + (sum(observed) / len(observed)) * len(plan)
                ceiling = float(str(contract["operational_ceiling_seconds"]))
                if index == checkpoint and projected > ceiling:
                    return _write_runtime_interruption(
                        root,
                        contract,
                        completed_records=index,
                        new_calls=new_calls,
                        cache_hits=cache_hits,
                        elapsed_seconds=elapsed,
                        projected_total_seconds=projected,
                        reason="CHECKPOINT_PROJECTION_EXCEEDS_FROZEN_OPERATIONAL_CEILING",
                    )
                if elapsed > ceiling and index < len(plan):
                    return _write_runtime_interruption(
                        root,
                        contract,
                        completed_records=index,
                        new_calls=new_calls,
                        cache_hits=cache_hits,
                        elapsed_seconds=elapsed,
                        projected_total_seconds=projected,
                        reason="INVOCATION_ELAPSED_TIME_EXCEEDS_FROZEN_OPERATIONAL_CEILING",
                    )
    if new_calls + cache_hits != EXPECTED_ADDITION_RECORDS:
        raise RuntimeError("E0F-2 completion/cache accounting mismatch")
    base.frozen_write_jsonl(addition_axis_path, addition_rows)
    base.frozen_write_jsonl(cumulative_axis_path, [*adopted_rows, *addition_rows])
    execution: JsonObject = {
        "schema_version": "jbspan-e0f2-execution-safe-v1",
        "status": "E0F2_156_ADDITION_AND_300_CUMULATIVE_EXECUTION_COMPLETE",
        "contract_sha256": contract_sha,
        "runtime": runtime,
        "server_startup_seconds": startup_seconds,
        "addition_scientific_records": len(addition_rows),
        "adopted_e0f1b_records": len(adopted_rows),
        "cumulative_scientific_records": len(adopted_rows) + len(addition_rows),
        "new_completion_calls_this_invocation": new_calls,
        "minimal_cache_hits": cache_hits,
        "prior_unopened_e0f1_outputs_reused": False,
        "prior_unopened_e0f1_identities_rerun": EXPECTED_PRIOR_UNOPENED_CALLS,
        "separate_canary_completion_calls": 0,
        "addition_integrity": base.integrity_summary(addition_rows, EXPECTED_ADDITION_RECORDS),
        "cumulative_integrity": base.integrity_summary(
            [*adopted_rows, *addition_rows], EXPECTED_CUMULATIVE_RECORDS
        ),
        "addition_axis_path": str(addition_axis_path.relative_to(root)),
        "addition_axis_bytes": addition_axis_path.stat().st_size,
        "addition_axis_sha256": base.file_sha256(addition_axis_path),
        "cumulative_axis_path": str(cumulative_axis_path.relative_to(root)),
        "cumulative_axis_bytes": cumulative_axis_path.stat().st_size,
        "cumulative_axis_sha256": base.file_sha256(cumulative_axis_path),
        "elapsed_seconds": time.monotonic() - started,
        "operational_ceiling_seconds": contract["operational_ceiling_seconds"],
        "cpu_only": True,
        "raw_fields_stored_in_private_cache": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
    }
    execution_result = base.write_frozen_result(execution_path, execution)
    return finalize(
        root,
        contract_path,
        contract,
        base_contract,
        existing,
        adopted_rows,
        addition_rows,
        execution_result,
    )


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    contract_path = base.rooted(root, args.contract)
    if args.command == "preflight":
        result = preflight(root, contract_path)
    else:
        result = run(
            root,
            contract_path,
            confirmed=bool(args.confirm_reviewed_e0f2_preflight),
        )
    print(
        "E0F2_COMMAND_RESULT "
        f"status={result['status']} identity={result['result_identity_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
