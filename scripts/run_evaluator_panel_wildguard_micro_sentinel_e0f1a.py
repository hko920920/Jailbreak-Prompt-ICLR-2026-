from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR.parent / "src"
for import_root in (SCRIPT_DIR, SOURCE_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import run_evaluator_panel_wildguard_sentinel_e0f1 as base  # type: ignore[import-not-found]  # noqa: E402

from jbspan.evaluator_panel import (  # type: ignore[import-untyped]  # noqa: E402
    sanitize_untrusted_text,
)
from jbspan.evaluator_panel_redesign import (  # type: ignore[import-untyped]  # noqa: E402
    ExistingSignalRecord,
)
from jbspan.evaluator_panel_wildguard_sentinel import (  # type: ignore[import-untyped]  # noqa: E402
    build_sentinel_records,
    evaluate_sentinel,
)

JsonObject = dict[str, Any]

EXPECTED_SCHEMA = "jbspan-e0f1a-wildguard-micro-sentinel-contract-v1"
EXPECTED_STATUS = "FROZEN_BEFORE_ANY_E0F1A_MICRO_SENTINEL_OUTPUT"
EXPECTED_RECORDS = 72


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    commands = value.add_subparsers(dest="command", required=True)
    for name in ("preflight", "run"):
        command = commands.add_parser(name)
        command.add_argument("--root", type=Path, default=Path("."))
        command.add_argument(
            "--contract",
            type=Path,
            default=Path(
                "configs/evaluator_panel/calibration_redesign_e0f1a_micro_sentinel_v1.json"
            ),
        )
    return value


def validate_contract(
    root: Path,
    contract_path: Path,
) -> tuple[JsonObject, JsonObject]:
    contract = base.load_object(contract_path)
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unexpected E0F-1A contract schema")
    if contract.get("status") != EXPECTED_STATUS or contract.get("frozen") is not True:
        raise ValueError("E0F-1A contract is not frozen before output")
    if base.rooted(root, contract["contract_path"]) != contract_path.resolve():
        raise ValueError("E0F-1A contract self-path mismatch")
    if contract.get("scientific_completion_call_ceiling") != EXPECTED_RECORDS:
        raise ValueError("E0F-1A scientific completion ceiling must be 72")
    if contract.get("automatic_expansion_after_micro_sentinel") is not False:
        raise ValueError("E0F-1A must prohibit automatic expansion")

    implementation = base.object_value(contract["implementation"], where="implementation")
    module_path = base.verify_file(root, implementation["module"], label="E0F-1A module")
    runner_path = base.verify_file(root, implementation["runner"], label="E0F-1A runner")
    base_runner_path = base.verify_file(
        root,
        implementation["base_runner"],
        label="E0F-1 base runner",
    )
    if module_path != (root / "src/jbspan/evaluator_panel_wildguard_sentinel.py").resolve():
        raise ValueError("unexpected E0F-1A module path")
    if runner_path != Path(__file__).resolve():
        raise ValueError("unexpected E0F-1A runner path")
    if base_runner_path != Path(base.__file__).resolve():
        raise ValueError("unexpected E0F-1 base runner path")

    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    for name, spec in dependencies.items():
        base.verify_file(root, spec, label=f"E0F-1A dependency {name}")
    base_contract_path = base.rooted(
        root,
        base.object_value(dependencies["base_e0f1_contract"], where="base contract")["path"],
    )
    base_contract = base.validate_contract(root, base_contract_path)
    if (
        base.canonical_sha256(base_contract["candidate_specs"])
        != contract["inherited_candidate_specs_sha256"]
    ):
        raise ValueError("E0F-1A inherited candidate family mismatch")
    if (
        base.canonical_sha256(base_contract["calibration_population"])
        != contract["inherited_calibration_population_sha256"]
    ):
        raise ValueError("E0F-1A calibration population mismatch")
    if (
        base.canonical_sha256(base_contract["futility_gates"])
        != contract["inherited_futility_gates_sha256"]
    ):
        raise ValueError("E0F-1A futility gates mismatch")

    interruption_path = base.rooted(
        root,
        base.object_value(dependencies["e0f1_v1_interruption"], where="interruption")["path"],
    )
    interruption = base.load_object(interruption_path)
    base.verify_result_identity(interruption, label="E0F-1 V1 interruption")
    if interruption.get("status") != contract["required_interruption_status"]:
        raise ValueError("E0F-1 V1 interruption status mismatch")
    if interruption.get("wildguard_labels_or_candidate_metrics_opened_for_redesign") is not False:
        raise ValueError("E0F-1 V1 outcomes were opened before the micro redesign")

    probe_path = base.rooted(
        root,
        base.object_value(dependencies["cpu_thread_probe"], where="thread probe")["path"],
    )
    probe = base.load_object(probe_path)
    base.verify_result_identity(probe, label="E0F-1 CPU thread probe")
    if probe.get("status") != contract["required_thread_probe_status"]:
        raise ValueError("CPU thread-probe status mismatch")
    if probe.get("byte_identical_across_threads") is not True:
        raise ValueError("CPU thread probe did not establish byte parity")

    inference = base.object_value(contract["inference"], where="inference")
    if inference.get("threads") != 16 or inference.get("threads_batch") != 16:
        raise ValueError("E0F-1A must use the qualified 16-thread amendment")
    base_inference = base.object_value(base_contract["inference"], where="base inference")
    if any(
        inference.get(field) != base_inference.get(field)
        for field in (
            "context_tokens",
            "maximum_new_tokens",
            "batch_size",
            "ubatch_size",
            "seed",
            "temperature",
            "top_p",
            "cache_prompt",
            "nonce",
            "max_untrusted_characters",
        )
    ):
        raise ValueError("E0F-1A changed a non-thread inference field")
    return contract, base_contract


def selected_record_ids(root: Path, contract: JsonObject) -> tuple[str, ...]:
    spec = base.object_value(contract["micro_identity_manifest"], where="micro manifest")
    path = base.verify_file(root, spec, label="E0F-1A micro identity manifest")
    rows = base.load_jsonl(path)
    if len(rows) != EXPECTED_RECORDS:
        raise ValueError("E0F-1A micro manifest must have 72 rows")
    selected: list[str] = []
    for row in rows:
        if row.get("schema_version") != "jbspan-e0f1a-micro-sentinel-identity-v1":
            raise ValueError("unexpected E0F-1A micro identity schema")
        if row.get("parent_first_included_stage") != "E0F_2_INTERMEDIATE":
            raise ValueError("E0F-1A must use only untouched E0F-2 identities")
        selected.append(str(row["record_id"]))
    if len(set(selected)) != EXPECTED_RECORDS:
        raise ValueError("E0F-1A micro identities are not unique")
    return tuple(selected)


def build_plan(
    root: Path,
    contract: JsonObject,
    base_contract: JsonObject,
) -> tuple[list[base.ScientificPlanRecord], tuple[ExistingSignalRecord, ...], JsonObject]:
    existing = base.load_existing_records(root, base_contract)
    existing_by_id = {record.record_id: record for record in existing}
    selected = selected_record_ids(root, contract)
    if not set(selected).issubset(existing_by_id):
        raise ValueError("E0F-1A micro selection is outside calibration")
    texts = base.reconstruct_text_records(root, base_contract)
    text_by_id = {record.record_id: record for record in texts}
    base_inputs = base.object_value(base_contract["inputs"], where="base inputs")
    prompt_spec = base.object_value(base_inputs["prompt_template"], where="prompt template")
    prompt_path = base.verify_file(root, prompt_spec, label="E0F-1A WildGuard prompt")
    template = prompt_path.read_text(encoding="utf-8")
    inference = base.object_value(contract["inference"], where="inference")
    nonce = str(inference["nonce"])
    max_characters = int(str(inference["max_untrusted_characters"]))
    plan: list[base.ScientificPlanRecord] = []
    counts: Counter[str] = Counter()
    truncations = 0
    for record_id in selected:
        text_record = text_by_id[record_id]
        signal_record = existing_by_id[record_id]
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
            "schema_version": "jbspan-e0f1a-wildguard-plan-record-v1",
            "record_id": record_id,
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
    expected = base.object_value(contract["expected_source_label_counts"], where="counts")
    expected_counts = {str(key): int(value) for key, value in sorted(expected.items())}
    if dict(sorted(counts.items())) != expected_counts:
        raise ValueError("E0F-1A source/label balance mismatch")
    if truncations:
        raise ValueError("E0F-1A plan has source-input truncation")
    safe_rows = [record.safe for record in plan]
    return (
        plan,
        existing,
        {
            "records": len(plan),
            "source_label_counts": dict(sorted(counts.items())),
            "source_input_truncation_count": truncations,
            "plan_identity_sha256": base.canonical_sha256(safe_rows),
            "maximum_classifier_input_utf8_bytes": max(
                int(row["classifier_input_utf8_bytes"]) for row in safe_rows
            ),
            "raw_text_written_to_safe_plan": False,
        },
    )


def preflight(root: Path, contract_path: Path) -> JsonObject:
    contract, base_contract = validate_contract(root, contract_path)
    plan, _, plan_summary = build_plan(root, contract, base_contract)
    runtime = base.runtime_identity(root, contract)
    outputs = base.object_value(contract["outputs"], where="outputs")
    plan_path = base.rooted(root, outputs["plan_path"])
    base.frozen_write_jsonl(plan_path, [record.safe for record in plan])
    result: JsonObject = {
        "schema_version": "jbspan-e0f1a-wildguard-micro-preflight-safe-v1",
        "status": "E0F1A_PREFLIGHT_PASS_AUTHORIZE_EXACTLY_72_SCIENTIFIC_COMPLETIONS",
        "evidence_class": "ZERO_SCIENTIFIC_INFERENCE_PREFLIGHT",
        "contract_sha256": base.file_sha256(contract_path),
        "implementation": contract["implementation"],
        "runtime": runtime,
        "scientific_plan": {
            **plan_summary,
            "path": str(plan_path.relative_to(root)),
            "bytes": plan_path.stat().st_size,
            "sha256": base.file_sha256(plan_path),
        },
        "candidate_count": len(
            base.object_rows(base_contract["candidate_specs"], where="candidates")
        ),
        "candidate_specs_sha256": base.canonical_sha256(base_contract["candidate_specs"]),
        "scientific_completion_call_ceiling": EXPECTED_RECORDS,
        "separate_canary_completion_calls_authorized": 0,
        "new_model_inference_performed": False,
        "prior_E0F1_V1_outputs_used_for_selection_or_metrics": False,
        "micro_identities_from_untouched_E0F2_pool": True,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "next_operation": "RUN_E0F1A_EXACT_72_WILDGUARD_MICRO_SENTINEL",
    }
    return cast(
        JsonObject,
        base.write_frozen_result(base.rooted(root, outputs["preflight_path"]), result),
    )


def finalize(
    root: Path,
    contract_path: Path,
    contract: JsonObject,
    base_contract: JsonObject,
    rows: list[JsonObject],
    execution: JsonObject,
) -> JsonObject:
    selected = set(selected_record_ids(root, contract))
    existing = base.load_existing_records(root, base_contract)
    sentinel = build_sentinel_records(existing, rows, selected_record_ids=selected)
    integrity = base.integrity_summary(rows, EXPECTED_RECORDS)
    evaluation = evaluate_sentinel(
        sentinel,
        base.object_rows(base_contract["candidate_specs"], where="candidates"),
        population=base.object_value(base_contract["calibration_population"], where="population"),
        gates=base.object_value(base_contract["futility_gates"], where="gates"),
        integrity_pass=integrity["pass"] is True,
    )
    passed = evaluation["sentinel_pass"] is True
    outputs = base.object_value(contract["outputs"], where="outputs")
    axis_path = base.rooted(root, outputs["axis_path"])
    result: JsonObject = {
        "schema_version": "jbspan-e0f1a-wildguard-micro-result-safe-v1",
        "status": (
            "E0F1A_MICRO_PASS_AUTHORIZE_E0F1_144_REVIEW"
            if passed
            else "E0F1A_MICRO_FAIL_STOP_WILDGUARD_EXPANSION"
        ),
        "evidence_class": "CALIBRATION_ONLY_SCIENTIFIC_FUTILITY_MICRO_SENTINEL",
        "contract_sha256": base.file_sha256(contract_path),
        "runtime": execution["runtime"],
        "execution": execution,
        "integrity": integrity,
        "candidate_evaluation": evaluation,
        "axis_artifact": {
            "path": str(axis_path.relative_to(root)),
            "records": len(rows),
            "bytes": axis_path.stat().st_size,
            "sha256": base.file_sha256(axis_path),
        },
        "scientific_decision": {
            "micro_sentinel_pass": passed,
            "original_144_sentinel_may_be_redesigned_and_frozen_after_review": passed,
            "automatic_144_or_300_execution_started": False,
            "e0f2_300_authorized": False,
            "e0f3_889_authorized": False,
            "heldout_authorized": False,
            "p3_rescore_authorized": False,
            "topology_authorized": False,
            "next_operation": (
                "REVIEW_E0F1A_THEN_FREEZE_CUMULATIVE_SENTINEL_ADOPTION"
                if passed
                else "STOP_WILDGUARD_PATH_WITHOUT_HELDOUT"
            ),
        },
        "scientific_completion_call_ceiling": EXPECTED_RECORDS,
        "separate_canary_completion_calls_performed": 0,
        "prior_E0F1_V1_outputs_used_for_selection_or_metrics": False,
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


def run(root: Path, contract_path: Path) -> JsonObject:
    contract, base_contract = validate_contract(root, contract_path)
    outputs = base.object_value(contract["outputs"], where="outputs")
    result_path = base.rooted(root, outputs["result_path"])
    if result_path.is_file():
        result = base.load_object(result_path)
        base.verify_result_identity(result, label="existing E0F-1A result")
        print(
            f"E0F1A_ALREADY_COMPLETE status={result['status']} "
            f"identity={result['result_identity_sha256']}",
            flush=True,
        )
        return cast(JsonObject, result)
    plan, _, plan_summary = build_plan(root, contract, base_contract)
    preflight_path = base.rooted(root, outputs["preflight_path"])
    if not preflight_path.is_file():
        raise FileNotFoundError("E0F-1A preflight must pass before inference")
    preflight_result = base.load_object(preflight_path)
    base.verify_result_identity(preflight_result, label="E0F-1A preflight")
    if preflight_result.get("status") != (
        "E0F1A_PREFLIGHT_PASS_AUTHORIZE_EXACTLY_72_SCIENTIFIC_COMPLETIONS"
    ):
        raise ValueError("E0F-1A preflight does not authorize execution")
    preflight_plan = base.object_value(preflight_result["scientific_plan"], where="plan")
    if preflight_plan.get("plan_identity_sha256") != plan_summary["plan_identity_sha256"]:
        raise ValueError("E0F-1A plan changed after preflight")
    base.verify_file(root, preflight_plan, label="E0F-1A safe plan")

    axis_path = base.rooted(root, outputs["axis_path"])
    execution_path = base.rooted(root, outputs["execution_path"])
    if axis_path.is_file() or execution_path.is_file():
        if not axis_path.is_file() or not execution_path.is_file():
            raise ValueError("partial safe E0F-1A terminal artifacts require audit")
        existing_rows = base.load_jsonl(axis_path)
        execution = base.load_object(execution_path)
        base.verify_result_identity(execution, label="E0F-1A execution")
        return finalize(
            root,
            contract_path,
            contract,
            base_contract,
            existing_rows,
            execution,
        )

    runtime = base.runtime_identity(root, contract)
    runtime_spec = base.object_value(contract["runtime"], where="runtime")
    server_path = base.rooted(
        root,
        base.object_value(runtime_spec["server"], where="server")["path"],
    )
    model_path = base.rooted(
        root,
        base.object_value(runtime_spec["model"], where="model")["path"],
    )
    inference = base.object_value(contract["inference"], where="inference")
    artifact_root = base.rooted(root, outputs["private_artifact_root"])
    private_dir = artifact_root / "private_records"
    private_dir.mkdir(parents=True, exist_ok=True)
    contract_sha = base.file_sha256(contract_path)
    started = time.monotonic()
    rows: list[JsonObject] = []
    cache_hits = 0
    new_calls = 0
    failures = 0
    with base.local_server(
        server_path=server_path,
        model_path=model_path,
        port=int(runtime_spec["port"]),
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
            rows.append(safe)
            cache_hits += cache_hit
            new_calls += new_completion
            failures += safe["eligible_measurement"] is not True
            if index % 6 == 0 or index == len(plan):
                print(
                    "E0F1A_WILDGUARD_PROGRESS "
                    f"completed={index}/{len(plan)} new_completion_calls={new_calls} "
                    f"cache_hits={cache_hits} integrity_failures={failures} "
                    f"elapsed_seconds={time.monotonic() - started:.1f}",
                    flush=True,
                )
    if new_calls + cache_hits > EXPECTED_RECORDS:
        raise RuntimeError("E0F-1A scientific completion ceiling exceeded")
    base.frozen_write_jsonl(axis_path, rows)
    integrity = base.integrity_summary(rows, EXPECTED_RECORDS)
    execution_value: JsonObject = {
        "schema_version": "jbspan-e0f1a-wildguard-micro-execution-safe-v1",
        "status": "E0F1A_EXACT_72_WILDGUARD_EXECUTION_COMPLETE",
        "contract_sha256": contract_sha,
        "runtime": runtime,
        "server_startup_seconds": startup_seconds,
        "planned_scientific_records": EXPECTED_RECORDS,
        "completed_scientific_records": len(rows),
        "new_completion_calls_this_invocation": new_calls,
        "resumed_private_cache_records": cache_hits,
        "scientific_completion_records_total": sum(
            row["request_completed"] is True for row in rows
        ),
        "separate_canary_completion_calls": 0,
        "integrity": integrity,
        "axis_path": str(axis_path.relative_to(root)),
        "axis_bytes": axis_path.stat().st_size,
        "axis_sha256": base.file_sha256(axis_path),
        "elapsed_seconds": time.monotonic() - started,
        "operational_ceiling_seconds": int(contract["operational_ceiling_seconds"]),
        "operational_ceiling_met": (
            time.monotonic() - started <= int(contract["operational_ceiling_seconds"])
        ),
        "cpu_only": True,
        "raw_prompt_or_response_written_to_safe_outputs": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
    }
    execution = base.write_frozen_result(execution_path, execution_value)
    return finalize(root, contract_path, contract, base_contract, rows, execution)


def main() -> int:
    args = parser().parse_args()
    root = args.root.resolve()
    contract_path = base.rooted(root, args.contract)
    result = (
        preflight(root, contract_path) if args.command == "preflight" else run(root, contract_path)
    )
    print(
        f"E0F1A_COMMAND_RESULT status={result['status']} "
        f"identity={result['result_identity_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
