from __future__ import annotations

import argparse
import hashlib
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR.parent / "src"
for import_root in (SCRIPT_DIR, SOURCE_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

import run_evaluator_panel_wildguard_cumulative_sentinel_e0f1b as predecessor  # type: ignore[import-not-found]  # noqa: E402
import run_evaluator_panel_wildguard_sentinel_e0f1 as base  # type: ignore[import-not-found]  # noqa: E402

from jbspan.evaluator_panel_wildguard_sentinel import (  # noqa: E402
    build_sentinel_records,
    evaluate_sentinel,
)

JsonObject = dict[str, Any]

EXPECTED_SCHEMA = "jbspan-e0f1b-wildguard-cumulative-sentinel-contract-v1-1"
EXPECTED_STATUS = "FROZEN_AFTER_DEFENDER_INTERRUPTION_BEFORE_V1_1_OUTPUT"
EXPECTED_ADOPTED_E0F1A_RECORDS = 72
EXPECTED_ADDITION_RECORDS = 72
EXPECTED_CUMULATIVE_RECORDS = 144
EXPECTED_MIGRATED_RECORDS = 5
EXPECTED_NEW_COMPLETION_CALLS = 67
PREDECESSOR_COMPLETION_CALLS = 6
PRIVATE_SCHEMA = "jbspan-e0f1b-v1-1-minimal-private-wildguard-record-v1"
FORBIDDEN_PRIVATE_KEYS = {
    "human_label",
    "question_text",
    "response_text",
    "human_request",
    "assistant_response",
    "classifier_input",
    "raw_output",
    "input_token_ids",
}


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
                "configs/evaluator_panel/calibration_redesign_e0f1b_cumulative_sentinel_v1_1.json"
            ),
        )
    run_command.add_argument("--confirm-reviewed-storage-repair", action="store_true")
    return value


def _scan_minimal_private(value: object, *, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_PRIVATE_KEYS:
                raise ValueError(f"forbidden raw field in minimal private cache: {path}.{key}")
            _scan_minimal_private(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_minimal_private(item, path=f"{path}[{index}]")


def _dependency_path(
    root: Path,
    dependencies: Mapping[str, object],
    name: str,
) -> Path:
    return base.verify_file(root, dependencies[name], label=f"E0F-1B V1.1 dependency {name}")


def validate_contract(
    root: Path,
    contract_path: Path,
) -> tuple[JsonObject, JsonObject, JsonObject, JsonObject]:
    contract = base.load_object(contract_path)
    if contract.get("schema_version") != EXPECTED_SCHEMA:
        raise ValueError("unexpected E0F-1B V1.1 contract schema")
    if contract.get("status") != EXPECTED_STATUS or contract.get("frozen") is not True:
        raise ValueError("E0F-1B V1.1 contract is not frozen before repaired output")
    if base.rooted(root, contract["contract_path"]) != contract_path.resolve():
        raise ValueError("E0F-1B V1.1 contract self-path mismatch")
    if int(str(contract.get("addition_scientific_records"))) != EXPECTED_ADDITION_RECORDS:
        raise ValueError("E0F-1B V1.1 must retain 72 addition records")
    if int(str(contract.get("migrated_predecessor_records"))) != EXPECTED_MIGRATED_RECORDS:
        raise ValueError("E0F-1B V1.1 must migrate exactly five complete records")
    if int(str(contract.get("new_completion_call_ceiling"))) != EXPECTED_NEW_COMPLETION_CALLS:
        raise ValueError("E0F-1B V1.1 may make at most 67 new completions")
    if contract.get("automatic_execution_after_preflight") is not False:
        raise ValueError("E0F-1B V1.1 must prohibit automatic execution")

    implementation = base.object_value(contract["implementation"], where="implementation")
    runner_path = base.verify_file(root, implementation["runner"], label="V1.1 runner")
    predecessor_runner_path = base.verify_file(
        root,
        implementation["predecessor_runner"],
        label="predecessor runner",
    )
    parser_module_path = base.verify_file(
        root,
        implementation["parser_module"],
        label="parser module",
    )
    sentinel_module_path = base.verify_file(
        root,
        implementation["sentinel_module"],
        label="sentinel module",
    )
    if runner_path != Path(__file__).resolve():
        raise ValueError("unexpected E0F-1B V1.1 runner path")
    if predecessor_runner_path != Path(predecessor.__file__).resolve():
        raise ValueError("unexpected E0F-1B predecessor runner path")
    if parser_module_path != (root / "src/jbspan/evaluator_panel.py").resolve():
        raise ValueError("unexpected parser module path")
    if (
        sentinel_module_path
        != (root / "src/jbspan/evaluator_panel_wildguard_sentinel.py").resolve()
    ):
        raise ValueError("unexpected sentinel module path")

    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    for name in dependencies:
        _dependency_path(root, dependencies, name)
    predecessor_contract_path = _dependency_path(root, dependencies, "predecessor_contract")
    (
        predecessor_contract,
        base_contract,
        _,
        _,
    ) = predecessor.validate_contract(root, predecessor_contract_path)
    predecessor_preflight_path = _dependency_path(root, dependencies, "predecessor_preflight")
    predecessor_preflight = base.load_object(predecessor_preflight_path)
    base.verify_result_identity(predecessor_preflight, label="E0F-1B predecessor preflight")
    predecessor_preflight_spec = base.object_value(
        dependencies["predecessor_preflight"], where="predecessor preflight"
    )
    if predecessor_preflight.get("result_identity_sha256") != predecessor_preflight_spec.get(
        "result_identity_sha256"
    ):
        raise ValueError("predecessor preflight identity mismatch")
    if predecessor_preflight.get("new_model_inference_performed") is not False:
        raise ValueError("predecessor preflight unexpectedly reports inference")

    interruption_path = _dependency_path(root, dependencies, "defender_interruption")
    interruption = base.load_object(interruption_path)
    base.verify_result_identity(interruption, label="E0F-1B Defender interruption")
    interruption_spec = base.object_value(
        dependencies["defender_interruption"], where="Defender interruption"
    )
    if interruption.get("result_identity_sha256") != interruption_spec.get(
        "result_identity_sha256"
    ):
        raise ValueError("Defender interruption identity mismatch")
    if interruption.get("status") != (
        "E0F1B_V1_OPERATIONAL_STOP_DEFENDER_QUARANTINED_RAW_PRIVATE_CACHE"
    ):
        raise ValueError("unexpected E0F-1B predecessor interruption status")
    if interruption.get("windows_defender_exclusion_added") is not False:
        raise ValueError("a Defender exclusion was added")
    if interruption.get("quarantined_private_record_restored") is not False:
        raise ValueError("the quarantined record must not be restored")

    if base.canonical_sha256(contract["runtime"]) != base.canonical_sha256(
        predecessor_contract["runtime"]
    ):
        raise ValueError("V1.1 runtime differs from the frozen predecessor")
    if base.canonical_sha256(contract["inference"]) != base.canonical_sha256(
        predecessor_contract["inference"]
    ):
        raise ValueError("V1.1 inference differs from the frozen predecessor")
    repair = base.object_value(contract["storage_repair"], where="storage repair")
    if repair.get("private_schema") != PRIVATE_SCHEMA:
        raise ValueError("unexpected minimal private schema")
    if repair.get("raw_fields_stored") != []:
        raise ValueError("V1.1 minimal private cache may not store raw fields")
    if repair.get("defender_exclusion_added") is not False:
        raise ValueError("V1.1 may not add a Defender exclusion")
    return contract, predecessor_contract, base_contract, interruption


def _predecessor_execution_identity(
    plan: base.ScientificPlanRecord,
    predecessor_contract: JsonObject,
    predecessor_contract_sha256: str,
) -> str:
    implementation = base.object_value(
        predecessor_contract["implementation"], where="predecessor implementation"
    )
    model = base.object_value(
        base.object_value(predecessor_contract["runtime"], where="runtime")["model"],
        where="model",
    )
    identity: JsonObject = {
        "contract_sha256": predecessor_contract_sha256,
        "module_sha256": base.object_value(implementation["module"], where="module")["sha256"],
        "runner_sha256": base.object_value(implementation["runner"], where="runner")["sha256"],
        "model_sha256": model["sha256"],
        "record_id": plan.safe["record_id"],
        "judge_input_identity_sha256": plan.safe["judge_input_identity_sha256"],
        "inference": dict(base.object_value(predecessor_contract["inference"], where="inference")),
    }
    return base.canonical_sha256(identity)


def prepare_design(
    root: Path,
    contract_path: Path,
) -> tuple[
    JsonObject,
    JsonObject,
    JsonObject,
    list[JsonObject],
    list[base.ScientificPlanRecord],
    dict[str, JsonObject],
]:
    contract, predecessor_contract, base_contract, interruption = validate_contract(
        root, contract_path
    )
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    predecessor_contract_path = _dependency_path(root, dependencies, "predecessor_contract")
    (
        _,
        prepared_base_contract,
        adopted_rows,
        plan,
        _,
        _,
        _,
        _,
    ) = predecessor.prepare_design(root, predecessor_contract_path)
    if base.canonical_sha256(base_contract) != base.canonical_sha256(prepared_base_contract):
        raise ValueError("V1.1 base contract differs from predecessor preparation")

    predecessor_contract_sha = base.file_sha256(predecessor_contract_path)
    plan_by_predecessor_identity = {
        _predecessor_execution_identity(
            plan_record, predecessor_contract, predecessor_contract_sha
        ): plan_record
        for plan_record in plan
    }
    old_private_root = base.rooted(
        root,
        base.object_value(predecessor_contract["outputs"], where="predecessor outputs")[
            "private_artifact_root"
        ],
    )
    salvage_by_record_id: dict[str, JsonObject] = {}
    salvage_specs = base.object_rows(
        interruption["remaining_private_records"], where="remaining private records"
    )
    if len(salvage_specs) != EXPECTED_MIGRATED_RECORDS:
        raise ValueError("Defender interruption does not preserve exactly five records")
    for spec in salvage_specs:
        execution_identity = str(spec["execution_identity_sha256"])
        if execution_identity not in plan_by_predecessor_identity:
            raise ValueError("salvage cache identity is outside the frozen plan")
        old_path = old_private_root / "private_records" / f"{execution_identity}.json"
        base.verify_file(
            root,
            {
                "path": str(old_path.relative_to(root)),
                "bytes": spec["bytes"],
                "sha256": spec["sha256"],
            },
            label="salvage private record",
        )
        record_id = str(plan_by_predecessor_identity[execution_identity].safe["record_id"])
        salvage_by_record_id[record_id] = {
            **spec,
            "path": str(old_path.relative_to(root)),
        }
    if len(salvage_by_record_id) != EXPECTED_MIGRATED_RECORDS:
        raise ValueError("salvage records are not unique")
    quarantined_identity = str(
        base.object_value(interruption["defender"], where="Defender evidence")[
            "quarantined_execution_identity_sha256"
        ]
    )
    quarantined_path = old_private_root / "private_records" / f"{quarantined_identity}.json"
    if quarantined_path.exists():
        raise ValueError("quarantined raw private record must not be restored")
    return (
        contract,
        predecessor_contract,
        base_contract,
        adopted_rows,
        plan,
        salvage_by_record_id,
    )


def preflight(root: Path, contract_path: Path) -> JsonObject:
    contract, _, _, adopted_rows, plan, salvage_by_record_id = prepare_design(root, contract_path)
    runtime = base.runtime_identity(root, contract)
    dependencies = base.object_value(contract["dependencies"], where="dependencies")
    predecessor_preflight = base.load_object(
        _dependency_path(root, dependencies, "predecessor_preflight")
    )
    predecessor_plan = base.object_value(
        predecessor_preflight["scientific_plan"], where="predecessor plan"
    )
    outputs = base.object_value(contract["outputs"], where="outputs")
    result: JsonObject = {
        "schema_version": "jbspan-e0f1b-v1-1-minimal-cache-preflight-safe-v1",
        "status": "E0F1B_V1_1_PREFLIGHT_PASS_READY_FOR_5_MIGRATIONS_AND_67_CALLS",
        "evidence_class": "ZERO_NEW_INFERENCE_STORAGE_ONLY_REPAIR_PREFLIGHT",
        "contract_sha256": base.file_sha256(contract_path),
        "implementation": contract["implementation"],
        "runtime": runtime,
        "frozen_scientific_plan": {
            "records": len(plan),
            "path": predecessor_plan["path"],
            "bytes": predecessor_plan["bytes"],
            "sha256": predecessor_plan["sha256"],
            "plan_identity_sha256": predecessor_plan["plan_identity_sha256"],
            "changed_after_defender_interruption": False,
        },
        "adopted_e0f1a_records": len(adopted_rows),
        "migrated_predecessor_record_candidates": len(salvage_by_record_id),
        "new_completion_call_ceiling": EXPECTED_NEW_COMPLETION_CALLS,
        "addition_scientific_records": EXPECTED_ADDITION_RECORDS,
        "cumulative_scientific_records": EXPECTED_CUMULATIVE_RECORDS,
        "discarded_quarantined_predecessor_completions": 1,
        "storage_repair": {
            "private_schema": PRIVATE_SCHEMA,
            "raw_question_stored": False,
            "raw_response_stored": False,
            "raw_classifier_input_stored": False,
            "raw_classifier_output_stored": False,
            "input_token_ids_stored": False,
            "defender_exclusion_added": False,
            "quarantined_record_restored": False,
        },
        "new_model_inference_performed": False,
        "automatic_execution_started": False,
        "explicit_post_preflight_authorization_required": True,
        "candidate_family_or_gate_changed": False,
        "selection_or_order_changed": False,
        "heldout_opened": False,
        "p3_opened": False,
        "topology_opened": False,
        "next_operation": "REVIEW_STORAGE_REPAIR_THEN_MIGRATE_5_AND_RUN_AT_MOST_67_CALLS",
    }
    return cast(
        JsonObject,
        base.write_frozen_result(base.rooted(root, outputs["preflight_path"]), result),
    )


def _minimal_execution_identity(
    *,
    plan: base.ScientificPlanRecord,
    contract_sha256: str,
    implementation: Mapping[str, object],
    model_sha256: str,
    inference: Mapping[str, object],
) -> tuple[JsonObject, str]:
    identity: JsonObject = {
        "contract_sha256": contract_sha256,
        "sentinel_module_sha256": base.object_value(
            implementation["sentinel_module"], where="sentinel module"
        )["sha256"],
        "parser_module_sha256": base.object_value(
            implementation["parser_module"], where="parser module"
        )["sha256"],
        "runner_sha256": base.object_value(implementation["runner"], where="runner")["sha256"],
        "model_sha256": model_sha256,
        "record_id": plan.safe["record_id"],
        "judge_input_identity_sha256": plan.safe["judge_input_identity_sha256"],
        "inference": dict(inference),
        "private_schema": PRIVATE_SCHEMA,
    }
    return identity, base.canonical_sha256(identity)


def _minimal_payload(
    *,
    identity: JsonObject,
    identity_sha256: str,
    plan: base.ScientificPlanRecord,
    prompt_tokens: int,
    context_budget_pass: bool,
    request_completed: bool,
    classifier_output: str,
    stop_type: object,
    tokens_predicted: object,
    truncated: object,
    timings: Mapping[str, object],
    elapsed_seconds: object,
    provenance: Mapping[str, object],
    inference: Mapping[str, object],
) -> JsonObject:
    axis = base.parse_wildguard_output(
        classifier_output,
        canary_nonce=str(inference["nonce"]),
    )
    payload: JsonObject = {
        "schema_version": PRIVATE_SCHEMA,
        "execution_identity": identity,
        "execution_identity_sha256": identity_sha256,
        "record_id": plan.safe["record_id"],
        "question_sha256": plan.safe["question_sanitization"]["original_sha256"],
        "response_sha256": plan.safe["response_sanitization"]["original_sha256"],
        "classifier_input_sha256": plan.safe["classifier_input_sha256"],
        "prompt_tokens": prompt_tokens,
        "context_budget_pass": context_budget_pass,
        "completion_requested": request_completed,
        "request_completed": request_completed,
        "classifier_output_sha256": hashlib.sha256(classifier_output.encode()).hexdigest(),
        "classifier_output_utf8_bytes": len(classifier_output.encode("utf-8")),
        "parsed_axis": {
            "response_refusal": axis.response_refusal,
            "response_harmfulness": axis.response_harmfulness,
            "safe_redirection": axis.safe_redirection,
            "parse_error": axis.parse_error,
            "canary_pass": axis.canary_pass,
        },
        "stop_type": stop_type,
        "tokens_predicted": tokens_predicted,
        "truncated": truncated,
        "timings": dict(timings),
        "elapsed_seconds": elapsed_seconds,
        "provenance": dict(provenance),
        "record_complete": True,
    }
    _scan_minimal_private(payload)
    return payload


def migrate_predecessor_records(
    root: Path,
    contract: JsonObject,
    predecessor_contract: JsonObject,
    plan: Sequence[base.ScientificPlanRecord],
    salvage_by_record_id: Mapping[str, JsonObject],
) -> int:
    outputs = base.object_value(contract["outputs"], where="outputs")
    private_dir = base.rooted(root, outputs["private_artifact_root"]) / "private_records"
    private_dir.mkdir(parents=True, exist_ok=True)
    implementation = base.object_value(contract["implementation"], where="implementation")
    inference = base.object_value(contract["inference"], where="inference")
    model_sha = str(
        base.object_value(
            base.object_value(contract["runtime"], where="runtime")["model"], where="model"
        )["sha256"]
    )
    contract_sha = base.file_sha256(base.rooted(root, contract["contract_path"]))
    predecessor_contract_sha = base.file_sha256(
        base.rooted(root, predecessor_contract["contract_path"])
    )
    plan_by_id = {str(record.safe["record_id"]): record for record in plan}
    migrated = 0
    for record_id, spec in sorted(salvage_by_record_id.items()):
        plan_record = plan_by_id[record_id]
        old_path = base.rooted(root, spec["path"])
        if base.file_sha256(old_path) != spec["sha256"]:
            raise ValueError("predecessor raw cache changed before migration")
        old = base.load_object(old_path)
        expected_old_identity = _predecessor_execution_identity(
            plan_record,
            predecessor_contract,
            predecessor_contract_sha,
        )
        if old.get("execution_identity_sha256") != expected_old_identity:
            raise ValueError("predecessor cache execution identity mismatch")
        if old.get("record_complete") is not True or old.get("request_completed") is not True:
            raise ValueError("predecessor cache is not a complete model response")
        if (
            hashlib.sha256(str(old.get("human_request", "")).encode()).hexdigest()
            != (plan_record.safe["question_sanitization"]["original_sha256"])
        ):
            raise ValueError("predecessor cached question mismatch")
        if (
            hashlib.sha256(str(old.get("assistant_response", "")).encode()).hexdigest()
            != (plan_record.safe["response_sanitization"]["original_sha256"])
        ):
            raise ValueError("predecessor cached response mismatch")
        if (
            hashlib.sha256(str(old.get("classifier_input", "")).encode()).hexdigest()
            != (plan_record.safe["classifier_input_sha256"])
        ):
            raise ValueError("predecessor cached classifier input mismatch")
        identity, identity_sha = _minimal_execution_identity(
            plan=plan_record,
            contract_sha256=contract_sha,
            implementation=implementation,
            model_sha256=model_sha,
            inference=inference,
        )
        new_path = private_dir / f"{identity_sha}.json"
        payload = _minimal_payload(
            identity=identity,
            identity_sha256=identity_sha,
            plan=plan_record,
            prompt_tokens=int(str(old["prompt_tokens"])),
            context_budget_pass=old.get("context_budget_pass") is True,
            request_completed=True,
            classifier_output=str(old["raw_output"]),
            stop_type=old.get("stop_type"),
            tokens_predicted=old.get("tokens_predicted"),
            truncated=old.get("truncated"),
            timings=base.object_value(old.get("timings", {}), where="old timings"),
            elapsed_seconds=old.get("elapsed_seconds"),
            provenance={
                "kind": "MIGRATED_COMPLETE_PREDECESSOR_RESPONSE",
                "predecessor_contract_sha256": predecessor_contract_sha,
                "predecessor_execution_identity_sha256": expected_old_identity,
                "predecessor_private_record_sha256": spec["sha256"],
                "model_completion_performed_in_v1_1": False,
            },
            inference=inference,
        )
        base.atomic_write_json(new_path, payload)
        if base.load_object(new_path) != payload:
            raise ValueError("minimal migrated cache readback mismatch")
        migrated += 1
    return migrated


def execute_minimal_record(
    *,
    plan: base.ScientificPlanRecord,
    server_url: str,
    private_dir: Path,
    contract_sha256: str,
    implementation: Mapping[str, object],
    model_sha256: str,
    inference: Mapping[str, object],
) -> tuple[JsonObject, bool, bool, bool]:
    identity, identity_sha = _minimal_execution_identity(
        plan=plan,
        contract_sha256=contract_sha256,
        implementation=implementation,
        model_sha256=model_sha256,
        inference=inference,
    )
    private_path = private_dir / f"{identity_sha}.json"
    cache_hit = private_path.is_file()
    new_completion = False
    if cache_hit:
        execution = base.load_object(private_path)
    else:
        started = time.monotonic()
        tokenized = base.post_json(
            server_url + "/tokenize",
            {
                "content": plan.classifier_input,
                "add_special": False,
                "parse_special": True,
                "with_pieces": False,
            },
        )
        tokens = tokenized.get("tokens")
        if not isinstance(tokens, list) or not all(isinstance(token, int) for token in tokens):
            raise RuntimeError("WildGuard tokenizer response is invalid")
        prompt_tokens = len(tokens)
        context_budget_pass = prompt_tokens + int(str(inference["maximum_new_tokens"])) <= int(
            str(inference["context_tokens"])
        )
        classifier_output = ""
        completion: JsonObject | None = None
        if context_budget_pass and plan.safe["source_input_truncated"] is False:
            completion = base.post_json(
                server_url + "/completion",
                {
                    "prompt": plan.classifier_input,
                    "n_predict": int(str(inference["maximum_new_tokens"])),
                    "temperature": float(str(inference["temperature"])),
                    "top_p": float(str(inference["top_p"])),
                    "stream": False,
                    "cache_prompt": False,
                    "seed": int(str(inference["seed"])),
                },
            )
            content = completion.get("content")
            if not isinstance(content, str):
                raise RuntimeError("WildGuard completion returned no text")
            classifier_output = content
            new_completion = True
        execution = _minimal_payload(
            identity=identity,
            identity_sha256=identity_sha,
            plan=plan,
            prompt_tokens=prompt_tokens,
            context_budget_pass=context_budget_pass,
            request_completed=completion is not None,
            classifier_output=classifier_output,
            stop_type=completion.get("stop_type") if completion else None,
            tokens_predicted=completion.get("tokens_predicted") if completion else None,
            truncated=completion.get("truncated") if completion else None,
            timings=base.numeric_timings(completion.get("timings")) if completion else {},
            elapsed_seconds=time.monotonic() - started,
            provenance={
                "kind": "V1_1_NEW_MODEL_RESPONSE",
                "model_completion_performed_in_v1_1": completion is not None,
            },
            inference=inference,
        )
        base.atomic_write_json(private_path, execution)

    _scan_minimal_private(execution)
    if execution.get("schema_version") != PRIVATE_SCHEMA:
        raise ValueError("unexpected minimal private cache schema")
    if execution.get("execution_identity_sha256") != identity_sha:
        raise ValueError("minimal private cache identity mismatch")
    if execution.get("question_sha256") != plan.safe["question_sanitization"]["original_sha256"]:
        raise ValueError("minimal cached question hash mismatch")
    if execution.get("response_sha256") != plan.safe["response_sanitization"]["original_sha256"]:
        raise ValueError("minimal cached response hash mismatch")
    if execution.get("classifier_input_sha256") != plan.safe["classifier_input_sha256"]:
        raise ValueError("minimal cached classifier-input hash mismatch")

    parsed = base.object_value(execution["parsed_axis"], where="parsed axis")
    refusal = parsed.get("response_refusal")
    harmfulness = parsed.get("response_harmfulness")
    parse_error = parsed.get("parse_error") is True
    canary_pass = parsed.get("canary_pass") is True
    output_limit_hit = execution.get("stop_type") == "limit" or (
        isinstance(execution.get("tokens_predicted"), int)
        and int(execution["tokens_predicted"]) >= int(str(inference["maximum_new_tokens"]))
    )
    server_context_truncated = execution.get("truncated") is True
    eligible = all(
        (
            execution.get("record_complete") is True,
            execution.get("request_completed") is True,
            execution.get("context_budget_pass") is True,
            plan.safe["source_input_truncated"] is False,
            not server_context_truncated,
            not output_limit_hit,
            not parse_error,
            canary_pass,
            refusal in {"refusal", "compliance", "n/a"},
            harmfulness in {"harmful", "unharmful", "n/a"},
        )
    )
    provenance = base.object_value(execution["provenance"], where="provenance")
    migrated = provenance.get("kind") == "MIGRATED_COMPLETE_PREDECESSOR_RESPONSE"
    safe: JsonObject = {
        "schema_version": "jbspan-e0f1-safe-wildguard-record-v1",
        "record_id": plan.safe["record_id"],
        "source_id": plan.safe["source_id"],
        "behavior_group_sha256": plan.safe["behavior_group_sha256"],
        "response_sha256": plan.safe["response_sha256"],
        "judge_input_identity_sha256": plan.safe["judge_input_identity_sha256"],
        "execution_identity_sha256": identity_sha,
        "private_record_sha256": base.file_sha256(private_path),
        "private_cache_schema": PRIVATE_SCHEMA,
        "question_sanitization": plan.safe["question_sanitization"],
        "response_sanitization": plan.safe["response_sanitization"],
        "classifier_input_sha256": plan.safe["classifier_input_sha256"],
        "classifier_input_utf8_bytes": plan.safe["classifier_input_utf8_bytes"],
        "source_input_truncated": plan.safe["source_input_truncated"],
        "prompt_tokens": execution.get("prompt_tokens"),
        "context_budget_pass": execution.get("context_budget_pass") is True,
        "request_completed": execution.get("request_completed") is True,
        "server_context_truncated": server_context_truncated,
        "output_limit_hit": output_limit_hit,
        "stop_type": execution.get("stop_type"),
        "tokens_predicted": execution.get("tokens_predicted"),
        "output_sha256": execution.get("classifier_output_sha256"),
        "output_utf8_bytes": execution.get("classifier_output_utf8_bytes"),
        "response_refusal": refusal,
        "response_harmfulness": harmfulness,
        "safe_redirection": parsed.get("safe_redirection"),
        "parse_error": parse_error,
        "canary_pass": canary_pass,
        "eligible_measurement": eligible,
        "timings": execution.get("timings", {}),
        "first_execution_elapsed_seconds": execution.get("elapsed_seconds"),
        "migrated_complete_predecessor_response": migrated,
        "human_label_written": False,
        "raw_prompt_or_response_written": False,
    }
    base._scan_safe(safe)
    return safe, cache_hit, new_completion, migrated


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
    cumulative_axis_path = base.rooted(root, outputs["cumulative_axis_path"])
    base.frozen_write_jsonl(cumulative_axis_path, combined_rows)
    existing = base.load_existing_records(root, base_contract)
    selected_ids = {str(row["record_id"]) for row in combined_rows}
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
    sensitivity = predecessor.behavior_group_sensitivity(
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
        "schema_version": "jbspan-e0f1b-v1-1-wildguard-cumulative-result-safe-v1",
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
        "storage_repair": {
            "predecessor_completion_calls": PREDECESSOR_COMPLETION_CALLS,
            "migrated_complete_predecessor_records": EXPECTED_MIGRATED_RECORDS,
            "discarded_quarantined_predecessor_records": 1,
            "minimal_private_schema": PRIVATE_SCHEMA,
            "raw_fields_stored_in_v1_1_private_cache": False,
            "defender_exclusion_added": False,
            "quarantined_record_restored": False,
            "scientific_candidate_or_gate_changed": False,
        },
        "adoption": {
            "e0f1a_records": len(adopted_rows),
            "e0f1a_axis_sha256": base.object_value(dependencies["e0f1a_axis"], where="E0F-1A axis")[
                "sha256"
            ],
            "e0f1a_result_identity_sha256": base.object_value(
                dependencies["e0f1a_result"], where="E0F-1A result"
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
            "path": str(cumulative_axis_path.relative_to(root)),
            "records": len(combined_rows),
            "bytes": cumulative_axis_path.stat().st_size,
            "sha256": base.file_sha256(cumulative_axis_path),
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
        "cumulative_result_is_independent_confirmation": False,
        "addition_selection_depended_on_candidate_predictions": False,
        "addition_scientific_records": EXPECTED_ADDITION_RECORDS,
        "new_completion_call_ceiling_v1_1": EXPECTED_NEW_COMPLETION_CALLS,
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
        predecessor_contract,
        base_contract,
        adopted_rows,
        plan,
        salvage_by_record_id,
    ) = prepare_design(root, contract_path)
    outputs = base.object_value(contract["outputs"], where="outputs")
    result_path = base.rooted(root, outputs["result_path"])
    if result_path.is_file():
        result = base.load_object(result_path)
        base.verify_result_identity(result, label="existing E0F-1B V1.1 result")
        return cast(JsonObject, result)
    if not confirmed:
        raise PermissionError("E0F-1B V1.1 requires --confirm-reviewed-storage-repair")
    preflight_path = base.rooted(root, outputs["preflight_path"])
    if not preflight_path.is_file():
        raise FileNotFoundError("E0F-1B V1.1 preflight must pass before execution")
    preflight_result = base.load_object(preflight_path)
    base.verify_result_identity(preflight_result, label="E0F-1B V1.1 preflight")
    if preflight_result.get("status") != (
        "E0F1B_V1_1_PREFLIGHT_PASS_READY_FOR_5_MIGRATIONS_AND_67_CALLS"
    ):
        raise ValueError("E0F-1B V1.1 preflight status mismatch")
    if preflight_result.get("contract_sha256") != base.file_sha256(contract_path):
        raise ValueError("E0F-1B V1.1 contract changed after preflight")

    addition_axis_path = base.rooted(root, outputs["addition_axis_path"])
    cumulative_axis_path = base.rooted(root, outputs["cumulative_axis_path"])
    execution_path = base.rooted(root, outputs["execution_path"])
    if any(path.is_file() for path in (addition_axis_path, cumulative_axis_path, execution_path)):
        if not all(
            path.is_file() for path in (addition_axis_path, cumulative_axis_path, execution_path)
        ):
            raise ValueError("partial E0F-1B V1.1 terminal artifacts require audit")
        new_rows = base.load_jsonl(addition_axis_path)
        if base.load_jsonl(cumulative_axis_path) != [*adopted_rows, *new_rows]:
            raise ValueError("existing V1.1 cumulative axis mismatch")
        execution = base.load_object(execution_path)
        base.verify_result_identity(execution, label="E0F-1B V1.1 execution")
        return finalize(
            root,
            contract_path,
            contract,
            base_contract,
            adopted_rows,
            new_rows,
            execution,
        )

    migrated = migrate_predecessor_records(
        root,
        contract,
        predecessor_contract,
        plan,
        salvage_by_record_id,
    )
    if migrated != EXPECTED_MIGRATED_RECORDS:
        raise ValueError("E0F-1B V1.1 migration count mismatch")
    runtime = base.runtime_identity(root, contract)
    runtime_spec = base.object_value(contract["runtime"], where="runtime")
    server_path = base.rooted(
        root, base.object_value(runtime_spec["server"], where="server")["path"]
    )
    model_path = base.rooted(root, base.object_value(runtime_spec["model"], where="model")["path"])
    inference = base.object_value(contract["inference"], where="inference")
    implementation = base.object_value(contract["implementation"], where="implementation")
    artifact_root = base.rooted(root, outputs["private_artifact_root"])
    private_dir = artifact_root / "private_records"
    private_dir.mkdir(parents=True, exist_ok=True)
    contract_sha = base.file_sha256(contract_path)
    started = time.monotonic()
    new_rows: list[JsonObject] = []
    cache_hits = 0
    new_calls = 0
    migrated_hits = 0
    failures = 0
    with base.local_server(
        server_path=server_path,
        model_path=model_path,
        port=int(str(runtime_spec["port"])),
        inference=inference,
        log_path=artifact_root / "server_logs/wildguard.log",
    ) as (server_url, startup_seconds):
        for index, plan_record in enumerate(plan, 1):
            safe, cache_hit, new_completion, migrated_hit = execute_minimal_record(
                plan=plan_record,
                server_url=server_url,
                private_dir=private_dir,
                contract_sha256=contract_sha,
                implementation=implementation,
                model_sha256=str(runtime["model_sha256"]),
                inference=inference,
            )
            new_rows.append(safe)
            cache_hits += cache_hit
            new_calls += new_completion
            migrated_hits += migrated_hit
            failures += safe["eligible_measurement"] is not True
            if index % 6 == 0 or index == len(plan):
                print(
                    "E0F1B_V1_1_PROGRESS "
                    f"addition_completed={index}/{len(plan)} cumulative_completed="
                    f"{EXPECTED_ADOPTED_E0F1A_RECORDS + index}/{EXPECTED_CUMULATIVE_RECORDS} "
                    f"new_calls={new_calls} cache_hits={cache_hits} "
                    f"migrated_hits={migrated_hits} integrity_failures={failures} "
                    f"elapsed_seconds={time.monotonic() - started:.1f}",
                    flush=True,
                )
    if new_calls > EXPECTED_NEW_COMPLETION_CALLS:
        raise RuntimeError("E0F-1B V1.1 new completion ceiling exceeded")
    if migrated_hits != EXPECTED_MIGRATED_RECORDS:
        raise RuntimeError("E0F-1B V1.1 did not adopt all five migrated records")
    base.frozen_write_jsonl(addition_axis_path, new_rows)
    base.frozen_write_jsonl(cumulative_axis_path, [*adopted_rows, *new_rows])
    elapsed = time.monotonic() - started
    new_integrity = base.integrity_summary(new_rows, EXPECTED_ADDITION_RECORDS)
    cumulative_integrity = base.integrity_summary(
        [*adopted_rows, *new_rows], EXPECTED_CUMULATIVE_RECORDS
    )
    execution_value: JsonObject = {
        "schema_version": "jbspan-e0f1b-v1-1-wildguard-cumulative-execution-safe-v1",
        "status": "E0F1B_V1_1_72_ADDITION_AND_144_CUMULATIVE_EXECUTION_COMPLETE",
        "contract_sha256": contract_sha,
        "runtime": runtime,
        "server_startup_seconds": startup_seconds,
        "adopted_e0f1a_records": EXPECTED_ADOPTED_E0F1A_RECORDS,
        "addition_scientific_records": len(new_rows),
        "cumulative_scientific_records": len(adopted_rows) + len(new_rows),
        "migrated_complete_predecessor_records": migrated_hits,
        "new_completion_calls_this_invocation": new_calls,
        "minimal_cache_hits": cache_hits,
        "discarded_quarantined_predecessor_completions": 1,
        "predecessor_completion_calls": PREDECESSOR_COMPLETION_CALLS,
        "total_model_completion_calls_across_versions": PREDECESSOR_COMPLETION_CALLS + new_calls,
        "separate_canary_completion_calls": 0,
        "new_integrity": new_integrity,
        "cumulative_integrity": cumulative_integrity,
        "addition_axis_path": str(addition_axis_path.relative_to(root)),
        "addition_axis_bytes": addition_axis_path.stat().st_size,
        "addition_axis_sha256": base.file_sha256(addition_axis_path),
        "cumulative_axis_path": str(cumulative_axis_path.relative_to(root)),
        "cumulative_axis_bytes": cumulative_axis_path.stat().st_size,
        "cumulative_axis_sha256": base.file_sha256(cumulative_axis_path),
        "minimal_private_schema": PRIVATE_SCHEMA,
        "raw_fields_stored_in_v1_1_private_cache": False,
        "elapsed_seconds": elapsed,
        "operational_ceiling_seconds": int(str(contract["operational_ceiling_seconds"])),
        "operational_ceiling_met": elapsed <= int(str(contract["operational_ceiling_seconds"])),
        "cpu_only": True,
        "defender_exclusion_added": False,
        "quarantined_record_restored": False,
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
        else run(root, contract_path, confirmed=bool(args.confirm_reviewed_storage_repair))
    )
    print(
        f"E0F1B_V1_1_COMMAND_RESULT status={result['status']} "
        f"identity={result['result_identity_sha256']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
