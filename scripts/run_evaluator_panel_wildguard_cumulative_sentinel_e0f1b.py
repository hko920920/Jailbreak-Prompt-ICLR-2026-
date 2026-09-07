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

import run_evaluator_panel_wildguard_micro_sentinel_e0f1a as micro  # type: ignore[import-not-found]  # noqa: E402
import run_evaluator_panel_wildguard_sentinel_e0f1 as base  # type: ignore[import-not-found]  # noqa: E402

from jbspan.evaluator_panel import sanitize_untrusted_text  # noqa: E402
from jbspan.evaluator_panel_redesign import (  # type: ignore[import-untyped]  # noqa: E402
    ExistingSignalRecord,
)
from jbspan.evaluator_panel_wildguard_sentinel import (  # type: ignore[import-untyped]  # noqa: E402
    SentinelRecord,
    build_sentinel_records,
    evaluate_candidate,
    evaluate_sentinel,
)

JsonObject = dict[str, Any]

EXPECTED_SCHEMA = "jbspan-e0f1b-wildguard-cumulative-sentinel-contract-v1"
EXPECTED_STATUS = "FROZEN_BEFORE_ANY_E0F1B_ADDITION_OUTPUT"
EXPECTED_ADOPTED_RECORDS = 72
EXPECTED_NEW_RECORDS = 72
EXPECTED_CUMULATIVE_RECORDS = 144
EXPECTED_V1_EXCLUSIONS = 14
CELL_COUNT = 6
PER_CELL_ADDITIONS = 12
SOURCES = ("harmbench", "jailbreakbench", "strongreject")
LABELS = ("HARMFUL", "SAFE")


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
                "configs/evaluator_panel/calibration_redesign_e0f1b_cumulative_sentinel_v1.json"
            ),
        )
    run_command.add_argument(
        "--confirm-reviewed-frozen-preflight",
        action="store_true",
        help="Required guard against automatic execution after preflight.",
    )
    return value


def derived_selection_seed(
    *,
    micro_result_identity: str,
    interruption_result_identity: str,
) -> str:
    material = (
        "jbspan-e0f1b-cumulative-additions-v1|"
        f"{micro_result_identity}|{interruption_result_identity}"
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _dependency_path(
    root: Path,
    dependencies: Mapping[str, object],
    name: str,
) -> Path:
    return base.verify_file(root, dependencies[name], label=f"E0F-1B dependency {name}")


def validate_contract(
    root: Path,
    contract_path: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    contract = base.load_object(contract_path)
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unexpected E0F-1B contract schema")
    if contract.get("status") != EXPECTED_STATUS or contract.get("frozen") is not True:
        raise ValueError("E0F-1B contract is not frozen before addition output")
    if base.rooted(root, contract["contract_path"]) != contract_path.resolve():
        raise ValueError("E0F-1B contract self-path mismatch")
    if int(str(contract.get("new_scientific_completion_call_ceiling"))) != EXPECTED_NEW_RECORDS:
        raise ValueError("E0F-1B may perform at most 72 new scientific completions")
    if int(str(contract.get("cumulative_scientific_records"))) != EXPECTED_CUMULATIVE_RECORDS:
        raise ValueError("E0F-1B must evaluate exactly 144 cumulative records")
    if contract.get("automatic_execution_after_preflight") is not False:
        raise ValueError("E0F-1B must prohibit automatic execution after preflight")
    if contract.get("execution_requires_post_preflight_user_authorization") is not True:
        raise ValueError("E0F-1B must require explicit post-preflight authorization")

    implementation = base.object_value(contract["implementation"], where="implementation")
    module_path = base.verify_file(root, implementation["module"], label="E0F-1B module")
    runner_path = base.verify_file(root, implementation["runner"], label="E0F-1B runner")
    base_runner_path = base.verify_file(
        root,
        implementation["base_runner"],
        label="E0F-1 base runner",
    )
    micro_runner_path = base.verify_file(
        root,
        implementation["micro_runner"],
        label="E0F-1A micro runner",
    )
    if module_path != (root / "src/jbspan/evaluator_panel_wildguard_sentinel.py").resolve():
        raise ValueError("unexpected E0F-1B module path")
    if runner_path != Path(__file__).resolve():
        raise ValueError("unexpected E0F-1B runner path")
    if base_runner_path != Path(base.__file__).resolve():
        raise ValueError("unexpected E0F-1 base runner path")
    if micro_runner_path != Path(micro.__file__).resolve():
        raise ValueError("unexpected E0F-1A micro runner path")

    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    for name in dependencies:
        _dependency_path(root, dependencies, name)

    base_contract_path = _dependency_path(root, dependencies, "base_e0f1_contract")
    base_contract = base.validate_contract(root, base_contract_path)
    micro_contract_path = _dependency_path(root, dependencies, "e0f1a_contract")
    micro_contract, validated_base_contract = micro.validate_contract(root, micro_contract_path)
    if base.file_sha256(base_contract_path) != base.file_sha256(
        base.rooted(
            root,
            base.object_value(
                base.object_value(micro_contract["dependencies"], where="micro dependencies")[
                    "base_e0f1_contract"
                ],
                where="micro base dependency",
            )["path"],
        )
    ):
        raise ValueError("E0F-1B and E0F-1A do not inherit the same base contract")
    if base.canonical_sha256(base_contract) != base.canonical_sha256(validated_base_contract):
        raise ValueError("independently validated E0F-1 base contracts differ")

    micro_result_path = _dependency_path(root, dependencies, "e0f1a_result")
    micro_result = base.load_object(micro_result_path)
    base.verify_result_identity(micro_result, label="E0F-1A result")
    micro_result_spec = base.object_value(dependencies["e0f1a_result"], where="micro result")
    if micro_result.get("result_identity_sha256") != micro_result_spec.get(
        "result_identity_sha256"
    ):
        raise ValueError("E0F-1A result identity differs from the frozen dependency")
    if micro_result.get("status") != "E0F1A_MICRO_PASS_AUTHORIZE_E0F1_144_REVIEW":
        raise ValueError("E0F-1A did not authorize cumulative-sentinel review")
    micro_decision = base.object_value(
        micro_result["scientific_decision"], where="micro scientific decision"
    )
    if micro_decision.get("micro_sentinel_pass") is not True:
        raise ValueError("E0F-1A micro pass flag is false")
    if any(
        micro_result.get(field) is not False
        for field in ("heldout_opened", "p3_opened", "topology_opened", "panel_qualified")
    ):
        raise ValueError("E0F-1A protected boundary was not preserved")

    interruption_path = _dependency_path(root, dependencies, "e0f1_v1_interruption")
    interruption = base.load_object(interruption_path)
    base.verify_result_identity(interruption, label="E0F-1 V1 interruption")
    interruption_spec = base.object_value(
        dependencies["e0f1_v1_interruption"], where="V1 interruption"
    )
    if interruption.get("result_identity_sha256") != interruption_spec.get(
        "result_identity_sha256"
    ):
        raise ValueError("V1 interruption identity differs from frozen dependency")
    if interruption.get("status") != (
        "E0F1_V1_OPERATIONAL_STOP_PRESERVE_14_PRIVATE_CHECKPOINTS_NO_METRICS"
    ):
        raise ValueError("unexpected E0F-1 V1 interruption status")
    if interruption.get("wildguard_labels_or_candidate_metrics_opened_for_redesign") is not False:
        raise ValueError("V1 outputs were opened for redesign")

    if (
        base.canonical_sha256(base_contract["candidate_specs"])
        != contract["inherited_candidate_specs_sha256"]
    ):
        raise ValueError("E0F-1B candidate family changed after E0F-1A")
    if (
        base.canonical_sha256(base_contract["calibration_population"])
        != contract["inherited_calibration_population_sha256"]
    ):
        raise ValueError("E0F-1B calibration population changed")
    if (
        base.canonical_sha256(base_contract["futility_gates"])
        != contract["inherited_futility_gates_sha256"]
    ):
        raise ValueError("E0F-1B futility gates changed after E0F-1A")

    inference = base.object_value(contract["inference"], where="inference")
    micro_inference = base.object_value(micro_contract["inference"], where="micro inference")
    if base.canonical_sha256(inference) != base.canonical_sha256(micro_inference):
        raise ValueError("E0F-1B inference differs from the completed E0F-1A inference")
    runtime = base.object_value(contract["runtime"], where="runtime")
    micro_runtime = base.object_value(micro_contract["runtime"], where="micro runtime")
    if base.canonical_sha256(runtime) != base.canonical_sha256(micro_runtime):
        raise ValueError("E0F-1B runtime differs from the completed E0F-1A runtime")

    expected_seed = derived_selection_seed(
        micro_result_identity=str(micro_result["result_identity_sha256"]),
        interruption_result_identity=str(interruption["result_identity_sha256"]),
    )
    selection = base.object_value(contract["selection"], where="selection")
    if selection.get("derived_seed_sha256") != expected_seed:
        raise ValueError("E0F-1B selection seed is not identity-derived")
    if selection.get("wildguard_or_existing_signal_predictions_used") is not False:
        raise ValueError("E0F-1B additions must not be selected using model predictions")
    return contract, base_contract, micro_contract, micro_result


def _v1_execution_identity(
    *,
    plan: base.ScientificPlanRecord,
    base_contract: JsonObject,
    base_contract_sha256: str,
) -> str:
    implementation = base.object_value(base_contract["implementation"], where="implementation")
    runtime = base.object_value(base_contract["runtime"], where="runtime")
    model = base.object_value(runtime["model"], where="model")
    inference = base.object_value(base_contract["inference"], where="inference")
    identity: JsonObject = {
        "contract_sha256": base_contract_sha256,
        "module_sha256": base.object_value(implementation["module"], where="module")["sha256"],
        "runner_sha256": base.object_value(implementation["runner"], where="runner")["sha256"],
        "model_sha256": model["sha256"],
        "record_id": plan.safe["record_id"],
        "judge_input_identity_sha256": plan.safe["judge_input_identity_sha256"],
        "inference": dict(inference),
    }
    return base.canonical_sha256(identity)


def derive_v1_called_identity_rows_without_opening_private(
    root: Path,
    contract: JsonObject,
    base_contract: JsonObject,
    base_plan: Sequence[base.ScientificPlanRecord],
) -> tuple[JsonObject, ...]:
    exclusion = base.object_value(contract["v1_exclusion"], where="V1 exclusion")
    private_dir = base.rooted(root, exclusion["private_record_directory"])
    if not private_dir.is_dir():
        raise FileNotFoundError("E0F-1 V1 private-record directory is missing")
    private_files = sorted(
        path for path in private_dir.iterdir() if path.is_file() and path.suffix == ".json"
    )
    if len(private_files) != EXPECTED_V1_EXCLUSIONS:
        raise ValueError("E0F-1B expected exactly 14 preserved V1 private filenames")
    if any(path.stem != path.name.removesuffix(".json") for path in private_files):
        raise ValueError("unexpected V1 private cache filename")

    base_contract_path = base.rooted(root, base_contract["contract_path"])
    contract_sha = base.file_sha256(base_contract_path)
    plan_by_execution_identity = {
        _v1_execution_identity(
            plan=plan,
            base_contract=base_contract,
            base_contract_sha256=contract_sha,
        ): plan
        for plan in base_plan
    }
    private_identities = {path.stem for path in private_files}
    if not private_identities.issubset(plan_by_execution_identity):
        raise ValueError("a preserved V1 filename cannot be mapped to the frozen safe plan")

    rows: list[JsonObject] = []
    for execution_identity in sorted(private_identities):
        plan = plan_by_execution_identity[execution_identity]
        rows.append(
            {
                "schema_version": "jbspan-e0f1b-v1-called-exclusion-identity-v1",
                "record_id": plan.safe["record_id"],
                "source_id": plan.safe["source_id"],
                "behavior_group_sha256": plan.safe["behavior_group_sha256"],
                "v1_execution_identity_sha256": execution_identity,
                "private_record_content_opened": False,
                "human_label_written": False,
            }
        )
    if len({str(row["record_id"]) for row in rows}) != EXPECTED_V1_EXCLUSIONS:
        raise ValueError("V1 called identities are not unique")
    return tuple(rows)


def load_adopted_rows(
    root: Path,
    contract: JsonObject,
    micro_contract: JsonObject,
    micro_result: JsonObject,
    existing: Sequence[ExistingSignalRecord],
) -> tuple[list[JsonObject], set[str]]:
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    axis_path = _dependency_path(root, dependencies, "e0f1a_axis")
    axis_rows = base.load_jsonl(axis_path)
    axis_spec = base.object_value(micro_result["axis_artifact"], where="micro axis")
    if axis_spec.get("sha256") != base.file_sha256(axis_path):
        raise ValueError("E0F-1A result and adopted axis hash differ")
    adopted_ids = set(micro.selected_record_ids(root, micro_contract))
    if len(adopted_ids) != EXPECTED_ADOPTED_RECORDS:
        raise ValueError("E0F-1B must adopt exactly 72 E0F-1A records")
    build_sentinel_records(existing, axis_rows, selected_record_ids=adopted_ids)
    integrity = base.integrity_summary(axis_rows, EXPECTED_ADOPTED_RECORDS)
    if integrity["pass"] is not True:
        raise ValueError("E0F-1A adopted axis does not retain exact complete integrity")
    return axis_rows, adopted_ids


def _rank(seed: str, *parts: str) -> str:
    return hashlib.sha256("|".join((seed, *parts)).encode("utf-8")).hexdigest()


def _choose_cell_records(
    records: Sequence[ExistingSignalRecord],
    *,
    adopted_group_counts: Mapping[str, int],
    seed: str,
    source: str,
    label: str,
) -> list[ExistingSignalRecord]:
    by_group: dict[str, list[ExistingSignalRecord]] = defaultdict(list)
    for record in records:
        by_group[record.behavior_group_sha256].append(record)
    group_order = sorted(
        by_group,
        key=lambda group: (
            int(adopted_group_counts.get(group, 0) > 0),
            int(adopted_group_counts.get(group, 0)),
            _rank(seed, source, label, "group", group),
        ),
    )
    chosen: list[ExistingSignalRecord] = []
    for group in group_order:
        candidate = min(
            by_group[group],
            key=lambda record: _rank(seed, source, label, "record", record.record_id),
        )
        chosen.append(candidate)
        if len(chosen) == PER_CELL_ADDITIONS:
            return chosen

    selected_ids = {record.record_id for record in chosen}
    selected_group_counts = Counter(record.behavior_group_sha256 for record in chosen)
    remaining = [record for record in records if record.record_id not in selected_ids]
    while len(chosen) < PER_CELL_ADDITIONS:
        if not remaining:
            raise ValueError(f"insufficient untouched records for {source}:{label}")
        candidate = min(
            remaining,
            key=lambda record: (
                selected_group_counts[record.behavior_group_sha256],
                adopted_group_counts.get(record.behavior_group_sha256, 0),
                _rank(seed, source, label, "fill", record.record_id),
            ),
        )
        chosen.append(candidate)
        selected_group_counts[candidate.behavior_group_sha256] += 1
        remaining.remove(candidate)
    return chosen


def select_additions(
    root: Path,
    contract: JsonObject,
    base_contract: JsonObject,
    existing: Sequence[ExistingSignalRecord],
    *,
    adopted_ids: set[str],
    v1_called_ids: set[str],
) -> tuple[list[ExistingSignalRecord], list[JsonObject], JsonObject]:
    inputs = base.object_value(base_contract["inputs"], where="base inputs")
    stage_path = base.verify_file(root, inputs["stage_manifest"], label="stage manifest")
    stage_rows = base.load_jsonl(stage_path)
    stage_by_id = {str(row["record_id"]): str(row["first_included_stage"]) for row in stage_rows}
    if len(stage_by_id) != len(stage_rows):
        raise ValueError("stage manifest record ids are not unique")

    existing_by_id = {record.record_id: record for record in existing}
    if not adopted_ids.issubset(existing_by_id) or not v1_called_ids.issubset(existing_by_id):
        raise ValueError("adopted or V1-excluded identity is outside calibration")
    if adopted_ids & v1_called_ids:
        raise ValueError("E0F-1A adopted identities overlap interrupted V1 calls")
    if any(stage_by_id[record_id] != "E0F_2_INTERMEDIATE" for record_id in adopted_ids):
        raise ValueError("E0F-1A adoption is not entirely from the E0F-2 pool")
    if any(stage_by_id[record_id] != "E0F_1_SENTINEL" for record_id in v1_called_ids):
        raise ValueError("a V1 exclusion is outside the original E0F-1 pool")

    selection = base.object_value(contract["selection"], where="selection")
    seed = str(selection["derived_seed_sha256"])
    adopted_group_counts = Counter(
        existing_by_id[record_id].behavior_group_sha256 for record_id in adopted_ids
    )
    original_untouched = [
        record
        for record in existing
        if stage_by_id.get(record.record_id) == "E0F_1_SENTINEL"
        and record.record_id not in v1_called_ids
        and record.record_id not in adopted_ids
    ]
    by_cell: dict[tuple[str, str], list[ExistingSignalRecord]] = defaultdict(list)
    for record in original_untouched:
        by_cell[(record.source_id, record.human_label)].append(record)

    selected_by_cell: dict[tuple[str, str], list[ExistingSignalRecord]] = {}
    available_counts: JsonObject = {}
    for source in SOURCES:
        for label in LABELS:
            cell = (source, label)
            available_counts[f"{source}:{label}"] = len(by_cell[cell])
            selected_by_cell[cell] = _choose_cell_records(
                by_cell[cell],
                adopted_group_counts=adopted_group_counts,
                seed=seed,
                source=source,
                label=label,
            )

    ordered: list[ExistingSignalRecord] = []
    rounds: dict[str, int] = {}
    for round_index in range(PER_CELL_ADDITIONS):
        round_records = [
            selected_by_cell[(source, label)][round_index] for source in SOURCES for label in LABELS
        ]
        round_records.sort(
            key=lambda record: _rank(seed, "execution", str(round_index), record.record_id)
        )
        ordered.extend(round_records)
        rounds.update({record.record_id: round_index + 1 for record in round_records})

    if len(ordered) != EXPECTED_NEW_RECORDS or len({r.record_id for r in ordered}) != len(ordered):
        raise ValueError("E0F-1B addition selection is not exactly 72 unique records")
    if {record.record_id for record in ordered} & (adopted_ids | v1_called_ids):
        raise ValueError("E0F-1B additions overlap adopted or V1-called records")
    selected_counts = Counter(f"{record.source_id}:{record.human_label}" for record in ordered)
    expected_counts = {
        f"{source}:{label}": PER_CELL_ADDITIONS for source in SOURCES for label in LABELS
    }
    if dict(sorted(selected_counts.items())) != dict(sorted(expected_counts.items())):
        raise ValueError("E0F-1B addition source/label balance mismatch")

    identity_rows = [
        {
            "schema_version": "jbspan-e0f1b-addition-identity-v1",
            "record_id": record.record_id,
            "source_id": record.source_id,
            "behavior_group_sha256": record.behavior_group_sha256,
            "parent_first_included_stage": "E0F_1_SENTINEL",
            "execution_round": rounds[record.record_id],
            "selection_priority_sha256": _rank(
                seed,
                record.source_id,
                record.human_label,
                "selected",
                record.record_id,
            ),
            "interrupted_v1_call_excluded": True,
            "human_label_written": False,
        }
        for record in ordered
    ]
    cumulative_records = [existing_by_id[record_id] for record_id in adopted_ids] + ordered
    cumulative_group_counts = Counter(record.behavior_group_sha256 for record in cumulative_records)
    summary: JsonObject = {
        "available_original_e0f1_untouched_source_label_counts": dict(
            sorted(available_counts.items())
        ),
        "selected_source_label_counts": dict(sorted(selected_counts.items())),
        "addition_records": len(ordered),
        "addition_unique_behavior_groups": len(
            {record.behavior_group_sha256 for record in ordered}
        ),
        "adopted_unique_behavior_groups": len(adopted_group_counts),
        "cumulative_unique_behavior_groups": len(cumulative_group_counts),
        "cumulative_maximum_records_per_behavior_group": max(cumulative_group_counts.values()),
        "execution_rounds": PER_CELL_ADDITIONS,
        "records_per_round": CELL_COUNT,
        "selection_uses_wildguard_or_existing_signal_predictions": False,
        "per_record_human_labels_written": False,
    }
    return ordered, identity_rows, summary


def build_addition_plan(
    root: Path,
    contract: JsonObject,
    base_contract: JsonObject,
    selected: Sequence[ExistingSignalRecord],
) -> tuple[list[base.ScientificPlanRecord], JsonObject]:
    texts = base.reconstruct_text_records(root, base_contract)
    text_by_id = {record.record_id: record for record in texts}
    prompt_spec = base.object_value(
        base.object_value(base_contract["inputs"], where="base inputs")["prompt_template"],
        where="prompt template",
    )
    prompt_path = base.verify_file(root, prompt_spec, label="E0F-1B WildGuard prompt")
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
            "schema_version": "jbspan-e0f1b-wildguard-addition-plan-record-v1",
            "record_id": signal_record.record_id,
            "source_id": signal_record.source_id,
            "behavior_group_sha256": signal_record.behavior_group_sha256,
            "response_sha256": text_record.response_sha256,
            "question_sanitization": base.sanitization_metadata(request),
            "response_sanitization": base.sanitization_metadata(response),
            "source_input_truncated": truncated,
            "classifier_input_sha256": hashlib.sha256(classifier_input.encode("utf-8")).hexdigest(),
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
        raise ValueError("E0F-1B plan balance differs from frozen selection")
    if truncations:
        raise ValueError("E0F-1B plan contains source-input truncation")
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
    list[JsonObject],
    list[base.ScientificPlanRecord],
    tuple[JsonObject, ...],
    list[JsonObject],
    JsonObject,
    JsonObject,
]:
    contract, base_contract, micro_contract, micro_result = validate_contract(root, contract_path)
    base_plan, existing, _ = base.build_plan(root, base_contract)
    v1_exclusion_rows = derive_v1_called_identity_rows_without_opening_private(
        root,
        contract,
        base_contract,
        base_plan,
    )
    adopted_rows, adopted_ids = load_adopted_rows(
        root,
        contract,
        micro_contract,
        micro_result,
        existing,
    )
    selected, identity_rows, selection_summary = select_additions(
        root,
        contract,
        base_contract,
        existing,
        adopted_ids=adopted_ids,
        v1_called_ids={str(row["record_id"]) for row in v1_exclusion_rows},
    )
    plan, plan_summary = build_addition_plan(root, contract, base_contract, selected)
    return (
        contract,
        base_contract,
        adopted_rows,
        plan,
        v1_exclusion_rows,
        identity_rows,
        selection_summary,
        plan_summary,
    )


def _write_preflight_artifacts(
    root: Path,
    contract: JsonObject,
    *,
    plan: Sequence[base.ScientificPlanRecord],
    v1_exclusion_rows: Sequence[JsonObject],
    identity_rows: Sequence[JsonObject],
) -> JsonObject:
    outputs = base.object_value(contract["outputs"], where="outputs")
    exclusion_path = base.rooted(root, outputs["v1_exclusion_identity_path"])
    identity_path = base.rooted(root, outputs["addition_identity_path"])
    plan_path = base.rooted(root, outputs["addition_plan_path"])
    base.frozen_write_jsonl(exclusion_path, v1_exclusion_rows)
    base.frozen_write_jsonl(identity_path, identity_rows)
    base.frozen_write_jsonl(plan_path, [record.safe for record in plan])
    return {
        "v1_exclusion_identity": {
            "path": str(exclusion_path.relative_to(root)),
            "records": len(v1_exclusion_rows),
            "bytes": exclusion_path.stat().st_size,
            "sha256": base.file_sha256(exclusion_path),
            "private_record_content_opened": False,
        },
        "addition_identity": {
            "path": str(identity_path.relative_to(root)),
            "records": len(identity_rows),
            "bytes": identity_path.stat().st_size,
            "sha256": base.file_sha256(identity_path),
        },
        "addition_plan": {
            "path": str(plan_path.relative_to(root)),
            "records": len(plan),
            "bytes": plan_path.stat().st_size,
            "sha256": base.file_sha256(plan_path),
        },
    }


def preflight(root: Path, contract_path: Path) -> JsonObject:
    (
        contract,
        base_contract,
        adopted_rows,
        plan,
        v1_exclusion_rows,
        identity_rows,
        selection_summary,
        plan_summary,
    ) = prepare_design(root, contract_path)
    artifacts = _write_preflight_artifacts(
        root,
        contract,
        plan=plan,
        v1_exclusion_rows=v1_exclusion_rows,
        identity_rows=identity_rows,
    )
    runtime = base.runtime_identity(root, contract)
    outputs = base.object_value(contract["outputs"], where="outputs")
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    adopted_axis_spec = base.object_value(dependencies["e0f1a_axis"], where="adopted axis")
    result: JsonObject = {
        "schema_version": "jbspan-e0f1b-wildguard-cumulative-preflight-safe-v1",
        "status": "E0F1B_PREFLIGHT_PASS_READY_FOR_EXACTLY_72_NEW_COMPLETION_REVIEW",
        "evidence_class": "ZERO_NEW_SCIENTIFIC_INFERENCE_CUMULATIVE_FREEZE",
        "contract_sha256": base.file_sha256(contract_path),
        "implementation": contract["implementation"],
        "runtime": runtime,
        "adoption": {
            "records": len(adopted_rows),
            "axis_path": adopted_axis_spec["path"],
            "axis_sha256": adopted_axis_spec["sha256"],
            "source_result_identity_sha256": base.object_value(
                dependencies["e0f1a_result"], where="micro result"
            )["result_identity_sha256"],
            "adopted_axis_opened_previously": True,
            "independent_confirmation": False,
        },
        "selection": selection_summary,
        "scientific_plan": {**plan_summary, **artifacts["addition_plan"]},
        "safe_identity_artifacts": {
            "v1_exclusion_identity": artifacts["v1_exclusion_identity"],
            "addition_identity": artifacts["addition_identity"],
        },
        "candidate_count": len(
            base.object_rows(base_contract["candidate_specs"], where="candidates")
        ),
        "candidate_specs_sha256": base.canonical_sha256(base_contract["candidate_specs"]),
        "futility_gates_sha256": base.canonical_sha256(base_contract["futility_gates"]),
        "new_scientific_completion_call_ceiling": EXPECTED_NEW_RECORDS,
        "cumulative_scientific_records": EXPECTED_CUMULATIVE_RECORDS,
        "separate_canary_completion_calls_authorized": 0,
        "new_model_inference_performed": False,
        "v1_private_record_contents_opened": False,
        "v1_wildguard_labels_or_candidate_metrics_used": False,
        "addition_selection_used_wildguard_or_existing_signal_predictions": False,
        "automatic_execution_started": False,
        "explicit_post_preflight_authorization_required": True,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "next_operation": "REVIEW_FROZEN_PREFLIGHT_THEN_RUN_EXACTLY_72_NEW_COMPLETIONS",
    }
    return cast(
        JsonObject,
        base.write_frozen_result(base.rooted(root, outputs["preflight_path"]), result),
    )


def _number(value: object, *, where: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{where} is not numeric")
    return float(value)


def behavior_group_sensitivity(
    records: Sequence[SentinelRecord],
    candidate_specs: Sequence[Mapping[str, object]],
    *,
    population: Mapping[str, Mapping[str, object]],
    gates: Mapping[str, object],
    full_evaluation: Mapping[str, object],
) -> JsonObject:
    group_counts = Counter(record.existing.behavior_group_sha256 for record in records)
    by_source_groups = {
        source: len(
            {
                record.existing.behavior_group_sha256
                for record in records
                if record.source_id == source
            }
        )
        for source in SOURCES
    }
    full_rows = {
        str(row["candidate_id"]): row
        for row in base.object_rows(full_evaluation["candidate_results"], where="candidate results")
    }
    candidate_summaries: list[JsonObject] = []
    for spec in candidate_specs:
        candidate_id = str(spec["candidate_id"])
        leave_one_group: list[JsonObject] = []
        for group in sorted(group_counts):
            subset = [
                record for record in records if record.existing.behavior_group_sha256 != group
            ]
            evaluated = evaluate_candidate(
                subset,
                spec,
                population=population,
                gates=gates,
                integrity_pass=True,
            )
            leave_one_group.append(
                {
                    "pooled_recall": _number(
                        base.object_value(evaluated["pooled"], where="pooled")["recall"],
                        where="pooled recall",
                    ),
                    "projected_precision": _number(
                        base.object_value(
                            evaluated["full_calibration_projection"], where="projection"
                        )["projected_harmful_precision"],
                        where="projected precision",
                    ),
                    "minimum_source_recall": _number(
                        evaluated["minimum_source_harmful_recall"],
                        where="minimum source recall",
                    ),
                }
            )
        full = full_rows[candidate_id]
        full_metrics = {
            "pooled_recall": _number(
                base.object_value(full["pooled"], where="full pooled")["recall"],
                where="full pooled recall",
            ),
            "projected_precision": _number(
                base.object_value(full["full_calibration_projection"], where="full projection")[
                    "projected_harmful_precision"
                ],
                where="full projected precision",
            ),
            "minimum_source_recall": _number(
                full["minimum_source_harmful_recall"],
                where="full minimum source recall",
            ),
        }
        summary: JsonObject = {"candidate_id": candidate_id}
        for field, full_value in full_metrics.items():
            values = [_number(row[field], where=field) for row in leave_one_group]
            summary[field] = {
                "full": full_value,
                "leave_one_group_out_min": min(values),
                "leave_one_group_out_max": max(values),
                "maximum_absolute_shift": max(abs(value - full_value) for value in values),
            }
        candidate_summaries.append(summary)
    return {
        "evidence_role": "DESCRIPTIVE_DEPENDENCE_SENSITIVITY_NOT_A_PASS_GATE",
        "records": len(records),
        "unique_behavior_groups": len(group_counts),
        "maximum_records_per_behavior_group": max(group_counts.values()),
        "unique_behavior_groups_by_source": by_source_groups,
        "leave_one_behavior_group_out_candidate_summaries": candidate_summaries,
    }


def finalize(
    root: Path,
    contract_path: Path,
    contract: JsonObject,
    base_contract: JsonObject,
    adopted_rows: list[JsonObject],
    new_rows: list[JsonObject],
    execution: JsonObject,
) -> JsonObject:
    outputs = base.object_value(contract["outputs"], where="outputs")
    combined_rows = [*adopted_rows, *new_rows]
    combined_path = base.rooted(root, outputs["cumulative_axis_path"])
    base.frozen_write_jsonl(combined_path, combined_rows)
    existing = base.load_existing_records(root, base_contract)
    selected_ids = {str(row["record_id"]) for row in combined_rows}
    if len(selected_ids) != EXPECTED_CUMULATIVE_RECORDS:
        raise ValueError("E0F-1B cumulative axis does not have 144 unique identities")
    sentinel = build_sentinel_records(existing, combined_rows, selected_record_ids=selected_ids)
    integrity = base.integrity_summary(combined_rows, EXPECTED_CUMULATIVE_RECORDS)
    candidates = base.object_rows(base_contract["candidate_specs"], where="candidates")
    population = base.object_value(base_contract["calibration_population"], where="population")
    gates = base.object_value(base_contract["futility_gates"], where="gates")
    evaluation = evaluate_sentinel(
        sentinel,
        candidates,
        population=population,
        gates=gates,
        integrity_pass=integrity["pass"] is True,
    )
    sensitivity = behavior_group_sensitivity(
        sentinel,
        candidates,
        population=population,
        gates=gates,
        full_evaluation=evaluation,
    )
    passed = evaluation["sentinel_pass"] is True
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    addition_axis_path = base.rooted(root, outputs["addition_axis_path"])
    result: JsonObject = {
        "schema_version": "jbspan-e0f1b-wildguard-cumulative-result-safe-v1",
        "status": (
            "E0F1B_CUMULATIVE_PASS_AUTHORIZE_E0F2_300_DESIGN_REVIEW"
            if passed
            else "E0F1B_CUMULATIVE_FAIL_STOP_WILDGUARD_EXPANSION"
        ),
        "evidence_class": "CALIBRATION_ONLY_CUMULATIVE_SCIENTIFIC_FUTILITY_SENTINEL",
        "contract_sha256": base.file_sha256(contract_path),
        "runtime": execution["runtime"],
        "execution": execution,
        "integrity": integrity,
        "candidate_evaluation": evaluation,
        "behavior_group_sensitivity": sensitivity,
        "adoption": {
            "records": len(adopted_rows),
            "axis_path": base.object_value(dependencies["e0f1a_axis"], where="adopted axis")[
                "path"
            ],
            "axis_sha256": base.object_value(dependencies["e0f1a_axis"], where="adopted axis")[
                "sha256"
            ],
            "source_result_identity_sha256": base.object_value(
                dependencies["e0f1a_result"], where="micro result"
            )["result_identity_sha256"],
            "independent_confirmation": False,
        },
        "addition_axis_artifact": {
            "path": str(addition_axis_path.relative_to(root)),
            "records": len(new_rows),
            "bytes": addition_axis_path.stat().st_size,
            "sha256": base.file_sha256(addition_axis_path),
        },
        "cumulative_axis_artifact": {
            "path": str(combined_path.relative_to(root)),
            "records": len(combined_rows),
            "bytes": combined_path.stat().st_size,
            "sha256": base.file_sha256(combined_path),
        },
        "scientific_decision": {
            "e0f1b_cumulative_sentinel_pass": passed,
            "e0f2_300_design_may_be_frozen_after_review": passed,
            "automatic_e0f2_300_execution_started": False,
            "e0f3_889_authorized": False,
            "heldout_authorized": False,
            "p3_rescore_authorized": False,
            "topology_authorized": False,
            "next_operation": (
                "REVIEW_E0F1B_THEN_FREEZE_E0F2_300_DESIGN"
                if passed
                else "STOP_WILDGUARD_PATH_WITHOUT_HELDOUT"
            ),
        },
        "e0f1a_outcome_seen_before_extension": True,
        "addition_selection_depended_on_e0f1a_candidate_predictions": False,
        "cumulative_result_is_independent_confirmation": False,
        "v1_private_record_contents_opened": False,
        "v1_wildguard_labels_or_candidate_metrics_used": False,
        "new_scientific_completion_call_ceiling": EXPECTED_NEW_RECORDS,
        "cumulative_scientific_records": EXPECTED_CUMULATIVE_RECORDS,
        "separate_canary_completion_calls_performed": 0,
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


def run(root: Path, contract_path: Path, *, confirmed: bool) -> JsonObject:
    (
        contract,
        base_contract,
        adopted_rows,
        plan,
        v1_exclusion_rows,
        identity_rows,
        _,
        plan_summary,
    ) = prepare_design(root, contract_path)
    outputs = base.object_value(contract["outputs"], where="outputs")
    result_path = base.rooted(root, outputs["result_path"])
    if result_path.is_file():
        result = base.load_object(result_path)
        base.verify_result_identity(result, label="existing E0F-1B result")
        print(
            f"E0F1B_ALREADY_COMPLETE status={result['status']} "
            f"identity={result['result_identity_sha256']}",
            flush=True,
        )
        return cast(JsonObject, result)
    if not confirmed:
        raise PermissionError("E0F-1B execution requires --confirm-reviewed-frozen-preflight")

    artifacts = _write_preflight_artifacts(
        root,
        contract,
        plan=plan,
        v1_exclusion_rows=v1_exclusion_rows,
        identity_rows=identity_rows,
    )
    preflight_path = base.rooted(root, outputs["preflight_path"])
    if not preflight_path.is_file():
        raise FileNotFoundError("E0F-1B preflight must pass before inference")
    preflight_result = base.load_object(preflight_path)
    base.verify_result_identity(preflight_result, label="E0F-1B preflight")
    if preflight_result.get("status") != (
        "E0F1B_PREFLIGHT_PASS_READY_FOR_EXACTLY_72_NEW_COMPLETION_REVIEW"
    ):
        raise ValueError("E0F-1B preflight does not match the reviewed status")
    if preflight_result.get("contract_sha256") != base.file_sha256(contract_path):
        raise ValueError("E0F-1B contract changed after preflight")
    if preflight_result.get("new_model_inference_performed") is not False:
        raise ValueError("E0F-1B preflight incorrectly reports new inference")
    if preflight_result.get("automatic_execution_started") is not False:
        raise ValueError("E0F-1B preflight reports an automatic execution")
    scientific_plan = base.object_value(preflight_result["scientific_plan"], where="preflight plan")
    if scientific_plan.get("plan_identity_sha256") != plan_summary["plan_identity_sha256"]:
        raise ValueError("E0F-1B plan changed after preflight")
    for name, artifact in artifacts.items():
        preflight_artifact = (
            scientific_plan
            if name == "addition_plan"
            else base.object_value(
                base.object_value(
                    preflight_result["safe_identity_artifacts"], where="identity artifacts"
                )[name],
                where=name,
            )
        )
        if preflight_artifact.get("sha256") != artifact["sha256"]:
            raise ValueError(f"E0F-1B {name} changed after preflight")

    addition_axis_path = base.rooted(root, outputs["addition_axis_path"])
    cumulative_axis_path = base.rooted(root, outputs["cumulative_axis_path"])
    execution_path = base.rooted(root, outputs["execution_path"])
    if any(path.is_file() for path in (addition_axis_path, cumulative_axis_path, execution_path)):
        if not all(
            path.is_file() for path in (addition_axis_path, cumulative_axis_path, execution_path)
        ):
            raise ValueError("partial safe E0F-1B terminal artifacts require audit")
        new_rows = base.load_jsonl(addition_axis_path)
        combined_rows = base.load_jsonl(cumulative_axis_path)
        if combined_rows != [*adopted_rows, *new_rows]:
            raise ValueError("existing E0F-1B cumulative axis adoption mismatch")
        execution = base.load_object(execution_path)
        base.verify_result_identity(execution, label="E0F-1B execution")
        return finalize(
            root,
            contract_path,
            contract,
            base_contract,
            adopted_rows,
            new_rows,
            execution,
        )

    runtime = base.runtime_identity(root, contract)
    runtime_spec = base.object_value(contract["runtime"], where="runtime")
    server_path = base.rooted(
        root, base.object_value(runtime_spec["server"], where="server")["path"]
    )
    model_path = base.rooted(root, base.object_value(runtime_spec["model"], where="model")["path"])
    inference = base.object_value(contract["inference"], where="inference")
    artifact_root = base.rooted(root, outputs["private_artifact_root"])
    private_dir = artifact_root / "private_records"
    private_dir.mkdir(parents=True, exist_ok=True)
    contract_sha = base.file_sha256(contract_path)
    started = time.monotonic()
    new_rows: list[JsonObject] = []
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
        for index, record in enumerate(plan, 1):
            safe, cache_hit, new_completion = base.execute_record(
                plan=record,
                server_url=server_url,
                private_dir=private_dir,
                contract_sha256=contract_sha,
                implementation=base.object_value(
                    contract["implementation"], where="implementation"
                ),
                model_sha256=str(runtime["model_sha256"]),
                inference=inference,
            )
            safe["schema_version"] = "jbspan-e0f1-safe-wildguard-record-v1"
            new_rows.append(safe)
            cache_hits += cache_hit
            new_calls += new_completion
            failures += safe["eligible_measurement"] is not True
            if index % CELL_COUNT == 0 or index == len(plan):
                print(
                    "E0F1B_WILDGUARD_PROGRESS "
                    f"new_completed={index}/{len(plan)} cumulative_completed="
                    f"{EXPECTED_ADOPTED_RECORDS + index}/{EXPECTED_CUMULATIVE_RECORDS} "
                    f"new_completion_calls={new_calls} cache_hits={cache_hits} "
                    f"integrity_failures={failures} "
                    f"elapsed_seconds={time.monotonic() - started:.1f}",
                    flush=True,
                )
    if new_calls + cache_hits > EXPECTED_NEW_RECORDS:
        raise RuntimeError("E0F-1B new scientific completion ceiling exceeded")
    base.frozen_write_jsonl(addition_axis_path, new_rows)
    base.frozen_write_jsonl(cumulative_axis_path, [*adopted_rows, *new_rows])
    new_integrity = base.integrity_summary(new_rows, EXPECTED_NEW_RECORDS)
    cumulative_integrity = base.integrity_summary(
        [*adopted_rows, *new_rows], EXPECTED_CUMULATIVE_RECORDS
    )
    elapsed = time.monotonic() - started
    execution_value: JsonObject = {
        "schema_version": "jbspan-e0f1b-wildguard-cumulative-execution-safe-v1",
        "status": "E0F1B_EXACT_72_NEW_AND_144_CUMULATIVE_EXECUTION_COMPLETE",
        "contract_sha256": contract_sha,
        "runtime": runtime,
        "server_startup_seconds": startup_seconds,
        "adopted_scientific_records": EXPECTED_ADOPTED_RECORDS,
        "planned_new_scientific_records": EXPECTED_NEW_RECORDS,
        "completed_new_scientific_records": len(new_rows),
        "cumulative_scientific_records": len(adopted_rows) + len(new_rows),
        "new_completion_calls_this_invocation": new_calls,
        "resumed_private_cache_records": cache_hits,
        "separate_canary_completion_calls": 0,
        "new_integrity": new_integrity,
        "cumulative_integrity": cumulative_integrity,
        "addition_axis_path": str(addition_axis_path.relative_to(root)),
        "addition_axis_bytes": addition_axis_path.stat().st_size,
        "addition_axis_sha256": base.file_sha256(addition_axis_path),
        "cumulative_axis_path": str(cumulative_axis_path.relative_to(root)),
        "cumulative_axis_bytes": cumulative_axis_path.stat().st_size,
        "cumulative_axis_sha256": base.file_sha256(cumulative_axis_path),
        "elapsed_seconds": elapsed,
        "operational_ceiling_seconds": int(str(contract["operational_ceiling_seconds"])),
        "operational_ceiling_met": elapsed <= int(str(contract["operational_ceiling_seconds"])),
        "cpu_only": True,
        "v1_private_record_contents_opened": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
    }
    execution = base.write_frozen_result(execution_path, execution_value)
    return finalize(
        root,
        contract_path,
        contract,
        base_contract,
        adopted_rows,
        new_rows,
        execution,
    )


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    contract_path = base.rooted(root, args.contract)
    result = (
        preflight(root, contract_path)
        if args.command == "preflight"
        else run(
            root,
            contract_path,
            confirmed=bool(args.confirm_reviewed_frozen_preflight),
        )
    )
    print(
        f"E0F1B_COMMAND_RESULT status={result['status']} "
        f"identity={result['result_identity_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
